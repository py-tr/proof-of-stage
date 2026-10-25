"""The agent probes on the /how page: real queries Nemotron wrote, from the logs.

Read from logs/agent-probe.jsonl and logs/agent-probe-2.jsonl (written by the pre-registered
probes) and docs/evidence/agent-probe-cases.json (the 6 patients the raw count misses and the 3
cases the verdict leaves to a person, exported read-only from the layer). Shown: one probe-1
query that returned 476, and the one probe-2 query that read the checked column (482), each
with its receipt. Logged runs, not replayed live; no model call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROBE1 = ROOT / "logs" / "agent-probe.jsonl"
PROBE2 = ROOT / "logs" / "agent-probe-2.jsonl"
PROBE3 = ROOT / "logs" / "agent-probe-3.jsonl"
CASES = ROOT / "docs" / "evidence" / "agent-probe-cases.json"
_KEEP = ("arm", "call", "sql", "why", "result", "receipt_id", "signature", "seconds")


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _pick(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return {k: row.get(k) for k in _KEEP} if row else None


def probe_story() -> dict[str, Any] | None:
    first, second = _rows(PROBE1), _rows(PROBE2)
    if not first or not second:
        return None
    raw = next((r for r in first if r.get("arm") == "with" and str(r.get("result")) == "476"), None)
    checked = next(
        (r for r in second if "positive_nodes_checked" in (r.get("sql") or "").lower()), None
    )
    written = [r for r in first + second if r.get("sql")]
    cases = json.loads(CASES.read_text(encoding="utf-8")) if CASES.exists() else {}
    return {
        "question": "How many patients are node-positive?",
        "raw_query": _pick(raw),
        "checked_query": _pick(checked),
        "queries_written": len(written),
        "read_raw_count": sum("lymph_nodes_positive" in r["sql"].lower() for r in written),
        "read_checked": sum("positive_nodes_checked" in r["sql"].lower() for r in written),
        "pointer_used": sum("fault_field" in r["sql"].lower() for r in written),
        "missed": cases.get("missed_by_raw_count") or [],
        "person": cases.get("left_to_a_person_but_raw_positive") or [],
        "probe3": _probe3(),
    }


def _probe3() -> dict[str, Any] | None:
    """The third probe (the layer's own DQ rules in the schema): codes per arm, from its log."""
    rows = _rows(PROBE3)
    if not rows:
        return None
    run = rows[0].get("run")
    rows = [r for r in rows if r.get("run") == run]
    arms = {}
    for arm in ("control", "treatment"):
        mine = [r for r in rows if r.get("arm") == arm]
        arms[arm] = {
            "calls": len(mine),
            "correct": sum(r.get("code") == "CORRECT" for r in mine),
            "raw": sum(r.get("code") == "RAW" for r in mine),
            "results": [r.get("result") for r in mine],
        }
    return {"run": run, **arms}
