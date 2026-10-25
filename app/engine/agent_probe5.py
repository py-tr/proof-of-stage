"""Agent probe 5: the same question as probes 1-3, with the layer's permissions changed.

Pre-registered in docs/preregistration/agent-probe-5.md (prompt, question, both schema texts and
this code frozen in agent-probe-5.json before the first call). Probes 1-3 asked "How many patients
are node-positive?" and every query the agent wrote counted the raw count column (476). Here the
treatment agent queries Zetaris with its own account, whose role `agent_reader` is granted SELECT
on one view only, `agent_view.node_status` (case_id, positive_nodes_checked, fault_field): the
checked values. Its schema text is that view and nothing else. The control replicates probe 3's
control arm (admin account, today's schema text, our read guard).

Same agent: Super VL through Nightshift, pinned, signed, no cache, 4k thinking budget, prompt and
question unchanged from probe 1. Treatment queries are sent to Zetaris unchanged under the agent
account (a write is never sent); a query on anything else is refused by Zetaris, which is a
result. Right by construction if it reads the view: the claim is where the fix lives (the layer's
permissions), not that the agent got better. Envelopes are kept (envelope_tap).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app import config
from app.engine.agent_probe import PROMPT, QUESTION
from app.engine.agent_probe4 import WRITE, ask
from app.engine.dial import sha16
from app.zetaris import SqlResult, ZetarisError, _columns_from, _error_message, _rows_from

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "agent-probe-5.json"
SCHEMA_CONTROL = ROOT / "docs" / "preregistration" / "agent-schema-p3-control.txt"
SCHEMA_AGENT = ROOT / "docs" / "preregistration" / "agent-schema-p5-view.txt"
LOG = ROOT / "logs" / "agent-probe-5.jsonl"
RUNS_LOG = ROOT / "logs" / "agent-probe-5-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "agent-probe-5-envelopes.jsonl"
CALLS = 5
CORRECT, RAW = "479", "476"
FROZEN_FILES = ("app/engine/agent_probe5.py",)
DENIED = re.compile(r"permission|privilege|not authori[sz]ed|access denied|denied|forbidden", re.I)


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        p
        for p, d in record["code_sha256_16"].items()
        if sha16((ROOT / p).read_text(encoding="utf-8")) != d
    ]
    for path, key in (
        (SCHEMA_CONTROL, "schema_control_sha256_16"),
        (SCHEMA_AGENT, "schema_agent_sha256_16"),
    ):
        if sha16(path.read_text(encoding="utf-8")) != record[key]:
            changed.append(path.name)
    if sha16(PROMPT + QUESTION) != record["prompt_sha256_16"]:
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


async def run_as_agent(sql: str, limit: int = 100) -> SqlResult:
    """The same REST call as app.zetaris.run_sql, under the agent account's key."""
    base = (config.getenv("ZETARIS_REST_URL") or "").rstrip("/")
    org_id = config.getenv("ZETARIS_AGENT_ORG_ID") or config.getenv("ZETARIS_ORG_ID")
    key = config.getenv("ZETARIS_AGENT_API_KEY")
    if not key:
        raise ZetarisError("ZETARIS_AGENT_API_KEY is not set")
    headers = {"Content-Type": "application/json", "X-Request-ID": str(uuid.uuid4())}
    if org_id:
        headers["X-Org-ID"] = org_id
    headers["Authorization"] = f"Bearer {key}"
    body = {"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{base}/sql-editor/sqls/run", headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise ZetarisError(f"Zetaris transport error: {type(exc).__name__}") from exc
    if not (200 <= response.status_code < 300):
        raise ZetarisError(_error_message(response))
    payload = response.json()
    if not isinstance(payload, dict):
        payload = {"data": payload}
    return SqlResult(rows=_rows_from(payload), columns=_columns_from(payload))


def number(result: SqlResult) -> str | None:
    if not result.rows:
        return None
    first = result.rows[0]
    cell = next(iter(first.values())) if isinstance(first, dict) else (first[0] if first else None)
    try:
        return str(int(float(cell)))
    except (TypeError, ValueError):
        return None


def code(value: str | None, *, refused_by: str | None, error: bool, sql: str) -> str:
    if not sql:
        return "NO_SQL"
    if refused_by == "write":
        return "WRITE_NOT_SENT"
    if refused_by == "zetaris":
        return "ZETARIS_REFUSED"
    if refused_by == "guard":
        return "GUARD_REFUSED"
    if error or value is None:
        return "SQL_ERROR"
    return {CORRECT: "CORRECT", RAW: "RAW"}.get(value, "OTHER")


async def execute(arm: str, sql: str) -> dict[str, Any]:
    from app.usl.client import guard_select, select

    out: dict[str, Any] = {"refused_by": None, "error": False, "value": None}
    if not sql:
        return out
    if WRITE.search(sql):
        out["refused_by"] = "write"
        return out
    try:
        if arm == "agent":
            result = await run_as_agent(sql)
        else:
            guard_select(sql)
            result = await select(sql, limit=100)
        out["value"] = number(result)
    except ZetarisError as exc:
        msg = str(exc)[:200]
        out["message"] = msg
        if arm == "agent" and DENIED.search(msg):
            out["refused_by"] = "zetaris"
        else:
            out["error"] = True
    except Exception as exc:  # our read guard (control arm) refused: never executed
        out["refused_by"], out["message"] = "guard", f"{type(exc).__name__}: {str(exc)[:160]}"
    return out


async def run_probe5() -> dict[str, Any]:
    frozen()
    schemas = {
        "agent": SCHEMA_AGENT.read_text(encoding="utf-8"),
        "control": SCHEMA_CONTROL.read_text(encoding="utf-8"),
    }
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, CALLS + 1):
        for arm in ("agent", "control"):  # interleaved
            item = f"agent-p5-{tag}-{arm}-{i}-{uuid.uuid4().hex[:6]}"
            row, calls = await ask(PROMPT, QUESTION, schemas[arm], item)
            row.update({"arm": arm, "call": i, "run": tag})
            for c in calls:
                with ENVELOPES.open("a", encoding="utf-8") as fh:
                    fh.write(
                        json.dumps({"run": tag, "arm": arm, "call": i, **c}, sort_keys=True) + "\n"
                    )
            if "provider_failure" not in row:
                sql = row.get("sql") or ""
                done = await execute(arm, sql)
                row.update(
                    {k: v for k, v in done.items() if k in ("value", "message", "refused_by")}
                )
                row["code"] = code(
                    done["value"], refused_by=done["refused_by"], error=done["error"], sql=sql
                )
            rows.append(row)
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary: dict[str, Any] = {"run": tag}
    for arm in ("agent", "control"):
        codes = [r.get("code", "PROVIDER_FAILURE") for r in rows if r["arm"] == arm]
        summary[arm] = {c: codes.count(c) for c in sorted(set(codes))}
    summary["claim_met"] = summary["agent"].get("CORRECT", 0) >= 4
    summary["control_replicates"] = summary["control"].get("RAW", 0) >= 4
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
