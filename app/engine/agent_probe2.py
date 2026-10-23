"""Follow-up to the agent probe: does an agent use a value the layer has already checked?

Pre-registered in docs/preregistration/agent-probe-2.md (both schema texts, the expected number
and this code frozen in agent-probe-2.json before the first call). The first probe showed that a
pointer to the verdict in a column description was not used (0 of 10). Here the layer offers the
checked value itself: stage_check.positive_nodes_checked, beside the raw count, which stays in
the schema. Same model, prompt, question, budget and Nightshift rules as the first probe
(app/engine/agent_probe.py, reused unchanged). Two arms, interleaved: control = the first
probe's "with" text byte for byte; treatment = the same text plus the one line describing the
new column. Nothing is stored.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.engine.agent_probe import ROOT, ask, sha16

PREREG = ROOT / "docs" / "preregistration" / "agent-probe-2.json"
SCHEMA_CONTROL = ROOT / "docs" / "preregistration" / "agent-schema-with.txt"
SCHEMA_TREATMENT = ROOT / "docs" / "preregistration" / "agent-schema-checked.txt"
LOG = ROOT / "logs" / "agent-probe-2.jsonl"
RUNS_LOG = ROOT / "logs" / "agent-probe-2-runs.jsonl"
CALLS_PER_ARM = 5
VOID_FAILURES = 2
FROZEN_FILES = ("app/engine/agent_probe2.py", "app/engine/agent_probe.py")
CHECKED = re.compile(r"\bpositive_nodes_checked\b", re.I)


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


def summarise(rows: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    out: dict[str, Any] = {"expected_result": expected}
    for arm in ("control", "treatment"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        answered = [r for r in arm_rows if "provider_failure" not in r]
        failures = len(arm_rows) - len(answered)
        reads_checked = [bool(CHECKED.search(r.get("sql") or "")) for r in answered]
        on_target = [
            used and str(r.get("result")) == str(expected)
            for used, r in zip(reads_checked, answered, strict=True)
        ]
        out[arm] = {
            "calls": len(arm_rows),
            "provider_failures": failures,
            "void": failures > VOID_FAILURES,
            "reads_checked_column": sum(reads_checked),
            "reads_checked_and_returns_expected": sum(on_target),
            "uses_fault_field": sum(r["uses"]["fault_field"] for r in answered),
            "uses_raw_count": sum(r["uses"]["count_column"] for r in answered),
            "sql_errors": sum("sql_error" in r for r in answered),
            "results": [r.get("result") for r in answered],
        }
    c, t = out["control"], out["treatment"]
    out["checked_column_used"] = (
        not c["void"]
        and not t["void"]
        and t["reads_checked_and_returns_expected"] >= 4
        and c["uses_fault_field"] <= 1
    )
    return out


async def run_probe2() -> dict[str, Any]:
    record = frozen()
    schemas = {
        "control": SCHEMA_CONTROL.read_text(encoding="utf-8"),
        "treatment": SCHEMA_TREATMENT.read_text(encoding="utf-8"),
    }
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, CALLS_PER_ARM + 1):
        for arm in ("control", "treatment"):  # interleaved, as in the first probe
            row = await ask(arm, schemas[arm], i, f"p2-{tag}")
            rows.append(row)
            with LOG.open("a", encoding="utf-8") as log:
                log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows, record["expected_result"])}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
