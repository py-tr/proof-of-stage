"""How a value was read: the latest ladder run per case, and the budget check."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.api import create_app
from app.web.data import SampleData
from app.web.trace import ANSWER_ALLOWANCE, budget_check, latest_trace


def _row(run: str, step: int, rung: str, budget: int, completion: int, receipt: str | None):
    return {
        "case": "TCGA-A2-A0CV",
        "run_id": run,
        "step": step,
        "rung": rung,
        "budget": budget,
        "receipt_id": receipt,
        "signature": "verified" if receipt else "absent",
        "seconds": 2.0,
        "usage": {"completion_tokens": completion},
        "fields": {
            "N": {"status": "accepted", "value": "N1A", "reason": "", "quote": "q"},
            "NPOS": {"status": "rejected", "value": "3", "reason": "count_not_in_quote"},
            "T": {"status": "accepted", "value": "T2"},
        },
    }


def test_the_latest_run_is_shown_rung_by_rung(tmp_path: Path) -> None:
    log = tmp_path / "chunks.jsonl"
    rows = [
        _row("run-old", 1, "R1", 0, 150, None),
        _row("run-new", 1, "R1", 0, 160, "rcpt_1"),
        _row("run-new", 2, "R2", 4000, 4190, "rcpt_2"),
    ]
    log.write_text("".join(json.dumps(r) + chr(10) for r in rows), encoding="utf-8")
    trace = latest_trace("TCGA-A2-A0CV", log)
    assert trace["run_id"] == "run-new" and [r["rung"] for r in trace["rungs"]] == ["R1", "R2"]
    assert (
        trace["rungs"][1]["provider"] == "nightshift"
        and trace["rungs"][1]["thinking"] == "4000 budget"
    )
    assert set(trace["rungs"][0]["fields"]) == {"N", "NPOS"}  # T is not audited
    assert "quote" not in trace["rungs"][0]["fields"]["N"]  # metadata and verdicts only
    assert trace["rungs"][0]["fields"]["N"]["reason"] == ""  # not the model's own sentence
    assert trace["rungs"][0]["fields"]["NPOS"]["reason"] == "count_not_in_quote"
    assert latest_trace("TCGA-OTHER", log) is None


def test_the_budget_check_uses_reasoning_tokens_when_reported() -> None:
    assert budget_check(4000, {"completion_tokens": 4000 + ANSWER_ALLOWANCE})["ok"] is True
    assert (
        budget_check(0, {"completion_tokens": 804})["ok"] is False
    )  # a thinking-off read that thought
    exact = budget_check(
        1000, {"completion_tokens": 1200, "completion_tokens_details": {"reasoning_tokens": 1023}}
    )
    assert exact["ok"] is False and "reasoning" in exact["how"]
    assert budget_check(1000, {})["ok"] is None


def test_sample_mode_shows_no_run() -> None:
    client = TestClient(create_app(SampleData()))
    case_id = client.get("/api/queue").json()[0]["case_id"]
    assert client.get(f"/api/case/{case_id}/trace").json() == {"trace": None}
