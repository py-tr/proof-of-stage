"""Third agent probe: does an agent use the verdict when the layer hands over its own DQ rules?

Pre-registered in docs/preregistration/agent-probe-3.md (both schema texts, the expected integers
and this code frozen in agent-probe-3.json before the first call). The layer's contract (LOAD
USL) carries every registered data-quality rule at table level (name and SQL expression); the
first two probes never showed them to the agent. Same model, prompt, question, budget and
Nightshift rules as before (app/engine/agent_probe.py, reused unchanged). Two arms, interleaved:
control = today's schema text as the layer exports it; treatment = the same text plus, under each
table, its rules rendered mechanically as "name: expression". Nothing is stored.

Each answered call gets one frozen code from its SQL and the number it returned: CORRECT (uses
fault_field but not the checked column, returns a verdict-corrected count, and does not copy a
rule into the filter),
FILTER (copies a rule or its negation, or returns a rule-filtered count), CHECKED (479),
CHECKED_FALLBACK (482), RAW (476) or OTHER.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.engine.agent_probe import ROOT, ask, schema_text, sha16

PREREG = ROOT / "docs" / "preregistration" / "agent-probe-3.json"
SCHEMA_CONTROL = ROOT / "docs" / "preregistration" / "agent-schema-p3-control.txt"
SCHEMA_TREATMENT = ROOT / "docs" / "preregistration" / "agent-schema-p3-rules.txt"
LOG = ROOT / "logs" / "agent-probe-3.jsonl"
RUNS_LOG = ROOT / "logs" / "agent-probe-3-runs.jsonl"
FQN = "lightning.metastore.registry_audit.stage_audit"
CALLS_PER_ARM = 5
VOID_FAILURES = 2
FROZEN_FILES = ("app/engine/agent_probe3.py", "app/engine/agent_probe.py")
FAULT = re.compile(r"\bfault_field\b", re.I)
CHECKED = re.compile(r"\bpositive_nodes_checked\b", re.I)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def rules_of(contract: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """Table name -> [(rule name, expression)], in contract order, as LOAD USL returns them."""
    return {
        t["name"]: [(a["name"], _flat(a["expression"])) for a in t.get("dqAnnotations") or []]
        for t in contract.get("tables") or []
    }


def rules_text(contract: dict[str, Any], fqn: str = FQN) -> str:
    """The control text with each table's rules appended under it, nothing else added."""
    rules = rules_of(contract)
    lines: list[str] = []
    for line in schema_text(contract, fqn).split("\n"):
        if line.startswith("TABLE ") and lines:
            lines.extend(_rule_lines(rules, previous))
        if line.startswith("TABLE "):
            previous = line.split(":", 1)[0].rsplit(".", 1)[-1]
        lines.append(line)
    if lines:
        lines.extend(_rule_lines(rules, previous))
    return "\n".join(lines)


def _rule_lines(rules: dict[str, list[tuple[str, str]]], table: str) -> list[str]:
    found = rules.get(table) or []
    if not found:
        return []
    return ["  DATA QUALITY RULES:", *(f"    - {name}: {expr}" for name, expr in found)]


def copies_rule(sql: str, expressions: list[str]) -> bool:
    """True when the query contains a registered expression verbatim (case and spacing ignored)."""
    flat = _flat(sql).lower()
    return any(_flat(e).lower() in flat for e in expressions)


def code(sql: str, result: Any, record: dict[str, Any]) -> str:
    ints = record["integers"]
    value = str(result).split(".")[0] if result is not None else None
    expressions = [e for rules in record["rules"].values() for _, e in rules]
    if copies_rule(sql, expressions) or value in {str(v) for v in ints["filter"].values()}:
        return "FILTER"
    if FAULT.search(sql) and not CHECKED.search(sql) and value in {str(v) for v in ints["correct_set"]}:
        return "CORRECT"
    if CHECKED.search(sql) and value == str(ints["checked"]):
        return "CHECKED"
    if value == str(ints["checked_fallback"]):
        return "CHECKED_FALLBACK"
    if value == str(ints["raw"]):
        return "RAW"
    return "OTHER"


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    for key, path in (("control", SCHEMA_CONTROL), ("treatment", SCHEMA_TREATMENT)):
        if sha16(path.read_text(encoding="utf-8")) != record[f"schema_{key}_sha256_16"]:
            changed.append(path.name)
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


def summarise(rows: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ("control", "treatment"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        answered = [r for r in arm_rows if "provider_failure" not in r]
        failures = len(arm_rows) - len(answered)
        codes = [r["code"] for r in answered]
        out[arm] = {
            "calls": len(arm_rows),
            "provider_failures": failures,
            "void": failures > VOID_FAILURES,
            "codes": {c: codes.count(c) for c in sorted(set(codes))},
            "correct": codes.count("CORRECT"),
            "filter": codes.count("FILTER"),
            "sql_errors": sum("sql_error" in r for r in answered),
            "results": [r.get("result") for r in answered],
        }
    c, t = out["control"], out["treatment"]
    out["rules_change_the_query"] = (
        not c["void"]
        and not t["void"]
        and ((t["correct"] >= 4 and c["correct"] == 0) or (t["correct"] == 5 and c["correct"] <= 1))
    )
    return out


async def run_probe3() -> dict[str, Any]:
    record = frozen()
    schemas = {
        "control": SCHEMA_CONTROL.read_text(encoding="utf-8"),
        "treatment": SCHEMA_TREATMENT.read_text(encoding="utf-8"),
    }
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, CALLS_PER_ARM + 1):
        for arm in ("control", "treatment"):  # interleaved, as in the first two probes
            row = await ask(arm, schemas[arm], i, f"p3-{tag}")
            if "provider_failure" not in row:
                row["code"] = code(row.get("sql") or "", row.get("result"), record)
            rows.append(row)
            with LOG.open("a", encoding="utf-8") as log:
                log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows, record)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
