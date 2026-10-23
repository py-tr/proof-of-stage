"""Does an agent that reads only the semantic layer's descriptions use the verdict?

Pre-registered in docs/preregistration/agent-probe.md (the prompt, both schema texts and this
code frozen in agent-probe.json before the first call). Nemotron Super VL, through Nightshift
(pinned in the signed receipt, 4k thinking budget, no cache), gets the USL's tables and columns
with their descriptions and one question, and must answer with ONE SQL query. Two arms differ
only in the pointer sentences ("audited: ... stage_check.fault_field names the field the report
contradicts") on the four N / count columns. Each query runs unchanged through the read guard;
an error is a result, never retried. Measured: whether the query uses fault_field, and the
number it returns. Nothing is stored.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.providers import nightshift
from app.reader.reader import parse_answer, thinking_args

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "agent-probe.json"
SCHEMA_WITH = ROOT / "docs" / "preregistration" / "agent-schema-with.txt"
SCHEMA_WITHOUT = ROOT / "docs" / "preregistration" / "agent-schema-without.txt"
LOG = ROOT / "logs" / "agent-probe.jsonl"
RUNS_LOG = ROOT / "logs" / "agent-probe-runs.jsonl"
CALLS_PER_ARM = 5
BUDGET = 4000
VOID_FAILURES = 2  # more provider failures than this in an arm voids that arm
FROZEN_FILES = ("app/engine/agent_probe.py",)
POINTER = re.compile(r" \(audited: [^)]*fault_field[^)]*\)")
QUESTION = "How many patients are node-positive?"

PROMPT = (
    "You answer questions about a cancer registry by querying its semantic layer. You get the "
    "layer's tables and columns with their descriptions. Write ONE read-only SQL query (Spark "
    "SQL) that answers the question, using the fully qualified table names exactly as given. "
    "The query must return one row with one number.\n"
    'Return ONLY a JSON object: {"sql": "...", "why": "one sentence"}'
)


def sha16(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def schema_text(contract: dict[str, Any], fqn: str) -> str:
    """The layer's tables and columns with their descriptions, as the agent sees them."""
    lines = []
    for table in contract.get("tables") or []:
        name = table.get("name")
        head = f"TABLE {fqn}.{name}"
        if table.get("description"):
            head += f": {table['description']}"
        lines.append(head)
        for col in table.get("columnSpecs") or []:
            kind = str(col.get("dataType") or "").strip('"')
            desc = col.get("description") or ""
            lines.append(f"  - {col.get('name')} ({kind}): {desc}")
    return "\n".join(lines)


def without_pointers(text: str) -> str:
    return POINTER.sub("", text)


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    for key, path in (("schema_with", SCHEMA_WITH), ("schema_without", SCHEMA_WITHOUT)):
        if sha16(path.read_text(encoding="utf-8")) != record[f"{key}_sha256_16"]:
            changed.append(path.name)
    if record["prompt_sha256_16"] != sha16(PROMPT + QUESTION):
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


def uses(sql: str) -> dict[str, bool]:
    """Which evidence the query reads: the verdict, the N column, the count, the report reading."""
    low = sql.lower()
    return {
        "fault_field": "fault_field" in low,
        "n_column": bool(re.search(r"\b(recorded_n|recorded_n_main|pathologic_n)\b", low)),
        "count_column": "lymph_nodes_positive" in low,
        "report_reading": bool(re.search(r"\breport_n|report_nodes_positive|derived_stage", low)),
    }


async def ask(arm: str, schema: str, i: int, tag: str) -> dict[str, Any]:
    from app.usl.client import guard_select, select

    extra, max_tokens = thinking_args(BUDGET)
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"{schema}\n\nQuestion: {QUESTION}"},
    ]
    row: dict[str, Any] = {"arm": arm, "call": i, "run": tag}
    started = time.monotonic()
    try:
        text, receipt = await nightshift.chat(
            messages,
            config.NS_SUPER_VL,
            item_id=f"agent-{tag}-{arm}-{i}",
            require_model=config.NS_SUPER_VL,
            retry_on_mismatch=True,
            require_signature=True,
            pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
            allow_cache=False,
            max_tokens=max_tokens,
            **extra,
        )
    except Exception as exc:  # a provider failure: recorded, never re-run
        row["provider_failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return row
    row["seconds"] = round(time.monotonic() - started, 2)
    row["receipt_id"], row["signature"] = receipt.receipt_id, receipt.signature
    row["completion_tokens"] = (receipt.usage or {}).get("completion_tokens")
    answer = parse_answer(text) or {}
    sql = str(answer.get("sql") or "").strip().rstrip(";")
    row["sql"], row["why"] = sql, str(answer.get("why") or "")[:300]
    row["uses"] = uses(sql)
    try:
        guard_select(sql)
        result = await select(sql, limit=5)
        first = result.rows[0] if result.rows else None
        value = (list(first.values()) if isinstance(first, dict) else list(first or []))[:1]
        row["result"] = value[0] if value else None
    except Exception as exc:  # the query failed: a result, never retried
        row["sql_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ("with", "without"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        answered = [r for r in arm_rows if "provider_failure" not in r]
        failures = len(arm_rows) - len(answered)
        out[arm] = {
            "calls": len(arm_rows),
            "provider_failures": failures,
            "void": failures > VOID_FAILURES,
            "uses_fault_field": sum(r["uses"]["fault_field"] for r in answered),
            "uses_n_column": sum(r["uses"]["n_column"] for r in answered),
            "uses_count_column": sum(r["uses"]["count_column"] for r in answered),
            "sql_errors": sum("sql_error" in r for r in answered),
            "results": [r.get("result") for r in answered],
        }
    w, wo = out["with"], out["without"]
    out["pointer_changes_the_query"] = (
        not w["void"]
        and not wo["void"]
        and w["uses_fault_field"] >= 4
        and wo["uses_fault_field"] <= 1
    )
    return out


async def run_probe() -> dict[str, Any]:
    frozen()
    schemas = {
        "with": SCHEMA_WITH.read_text(encoding="utf-8"),
        "without": SCHEMA_WITHOUT.read_text(encoding="utf-8"),
    }
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, CALLS_PER_ARM + 1):
        for arm in ("with", "without"):  # interleaved, so both arms see the same load
            row = await ask(arm, schemas[arm], i, tag)
            rows.append(row)
            with LOG.open("a", encoding="utf-8") as log:
                log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
