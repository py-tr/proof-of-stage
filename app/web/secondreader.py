"""The shipped second reader: Nemotron Ultra's objections, read-only, from the pre-registered run.

The Ultra critic met its pre-registered ship line in v2 (docs/evidence/ultra-critic-results.md).
This module serves what it said, from the committed log of that run (logs/ultra-critic-v2.jsonl,
first completed run only, planted controls excluded): per case and field, whether Ultra agreed
with the stored value or objected with a verified quote. It never writes to the layer and never
accepts or changes a value; an objection only marks the case for a person.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "logs" / "ultra-critic-v2.jsonl"
RUNS = ROOT / "logs" / "ultra-critic-v2-runs.jsonl"
SCORE = ROOT / "logs" / "ultra-critic-v2-score.json"


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def _run_rows() -> list[dict[str, Any]]:
    runs = _lines(RUNS)
    if not runs:
        return []
    tag = runs[0]["run"]
    return [r for r in _lines(LOG) if r.get("run") == tag and not r.get("planted")]


def case_reading(case_id: str) -> dict[str, Any] | None:
    """Ultra's second reading of one case's stored values, or None if it was not read."""
    rows = [r for r in _run_rows() if r.get("case") == case_id]
    if not rows:
        return None
    fields = []
    for r in rows:
        objected = r.get("verdict") == "contradiction" and (r.get("check") or {}).get("verified")
        fields.append(
            {
                "field": r["field"],
                "stored": r.get("stored"),
                "verdict": "objects" if objected else r.get("verdict"),
                "objection": (r.get("check") or {}).get("value") if objected else None,
                "quote": r.get("quote") if objected else None,
                "reason": r.get("reason") if objected else None,
                "receipt_id": r.get("receipt_id"),
                "model": r.get("served"),
            }
        )
    return {
        "case": case_id,
        "objects": any(f["verdict"] == "objects" for f in fields),
        "fields": fields,
        "source": "logs/ultra-critic-v2.jsonl (pre-registered run, logged, not replayed live)",
    }


def objecting_cases() -> set[str]:
    """Cases where Ultra objected with a verified quote: the queue sends them to a person.

    Display only: the layer's verdict (`fault_field`) and every stored value stay as they are.
    """
    return {
        r["case"]
        for r in _run_rows()
        if r.get("verdict") == "contradiction" and (r.get("check") or {}).get("verified")
    }


def summary() -> dict[str, Any] | None:
    """The measured result, for /how."""
    if not SCORE.exists():
        return None
    score = json.loads(SCORE.read_text(encoding="utf-8"))
    return {
        "values": sum(score.get("classes", {}).values()),
        "objections": score.get("objections"),
        "right": score.get("right"),
        "wrong": score.get("wrong"),
        "missed": score.get("missed"),
        "plants": score.get("plants"),
        "ships": score.get("ships"),
        "objection_list": score.get("objection_list"),
    }
