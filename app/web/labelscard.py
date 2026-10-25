"""The /how card "Against the blind labels": the frozen scores, from logs/label-scores.json.

Scores come from `python -m app.cli labels score` against the frozen labels (sha16 in the log).
The sensitivity row (three labels the labeller later confirmed as mis-clicks, disclosed
2026-10-24) is copied from docs/evidence/baseline-m0-results.md; the frozen scores stand.
No model call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCORES = ROOT / "logs" / "label-scores.json"
SENSITIVITY = {"product": 20, "super_4k": 19, "super_off": 11, "rule": 9, "of": 25}


def labels_summary() -> dict[str, Any] | None:
    if not SCORES.exists():
        return None
    d = json.loads(SCORES.read_text(encoding="utf-8"))
    b, rb = d["baseline_all"], d["reader_bench"]
    return {
        "labels_sha16": d.get("labels_sha16"),
        "of": b["labelled"],
        "product": b["A0_ours"]["agree"],
        "super_4k": b["M0_4k"]["agree"],
        "super_off": b["M0_off"]["agree"],
        "rule": b["B0_rule_alone"]["agree"],
        "reader_bench": {
            m: {"correct": rb[m]["correct"], "wrong": rb[m]["wrong"]}
            for m in ("lightning", "super", "ultra")
        },
        "sensitivity": SENSITIVITY,
    }
