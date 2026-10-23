"""Nemotron's scratchpad on a case: excerpts of one recorded call's reasoning text.

Read from docs/evidence/scratchpads/<case>.json (made by scripts/record_scratchpad.py). Only
the excerpts a person chose are shown, with what the call was; the proof of a value stays
its quote and the guard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRATCHPADS = ROOT / "docs" / "evidence" / "scratchpads"


def scratchpad(case_id: str, folder: Path = SCRATCHPADS) -> dict[str, Any] | None:
    path = folder / f"{case_id}.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    reasoning = record.get("reasoning") or ""
    excerpts = [
        reasoning[start:end].strip()
        for start, end in record.get("excerpts") or []
        if 0 <= start < end <= len(reasoning)
    ]
    if not excerpts:
        return None
    usage = record.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "excerpts": excerpts,
        "recorded_at": record.get("recorded_at"),
        "provider": record.get("provider"),
        "served_model": record.get("served_model"),
        "thinking_budget": record.get("thinking_budget"),
        "reasoning_tokens": details.get("reasoning_tokens"),
        "reasoning_chars": len(reasoning),
        "guard": record.get("guard"),
        "file": f"docs/evidence/scratchpads/{case_id}.json",
    }
