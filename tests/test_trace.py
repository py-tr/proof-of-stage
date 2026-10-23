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


def test_a_scratchpad_shows_only_the_chosen_excerpts(tmp_path: Path) -> None:
    from app.web.scratchpad import scratchpad

    record = {
        "reasoning": "AAA garbled line BBB so the total is 2 CCC",
        "excerpts": [[4, 16], [21, 38]],
        "usage": {"completion_tokens_details": {"reasoning_tokens": 3999}},
        "provider": "nvidia direct",
    }
    (tmp_path / "TCGA-A2-A0CV.json").write_text(json.dumps(record), encoding="utf-8")
    s = scratchpad("TCGA-A2-A0CV", tmp_path)
    assert s["excerpts"] == ["garbled line", "so the total is 2"] and s["reasoning_tokens"] == 3999
    assert "reasoning" not in s  # never the whole text
    assert scratchpad("TCGA-OTHER", tmp_path) is None


def test_sample_mode_shows_no_scratchpad() -> None:
    client = TestClient(create_app(SampleData()))
    case_id = client.get("/api/queue").json()[0]["case_id"]
    assert client.get(f"/api/case/{case_id}/scratchpad").json() == {"scratchpad": None}


def test_the_scan_box_is_the_parse_block_holding_the_scan_rungs_quote(tmp_path: Path) -> None:
    from app.web.scanbox import scan_box

    case = tmp_path / "TCGA-A2-A0CV"
    case.mkdir()
    pages = [
        [
            {"x0": 0.1, "y0": 0.2, "x1": 0.9, "y1": 0.25, "text": "HEADER"},
            {
                "x0": 0.1,
                "y0": 0.6,
                "x1": 0.9,
                "y1": 0.68,
                "text": "METASTASIS IN TWO OF EIGHTEEN (2/18) NODES",
            },
        ]
    ]
    (case / "blocks.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")
    (case / "page-0.png").write_bytes(b"png")
    log = tmp_path / "chunks.jsonl"
    row = {
        "case": "TCGA-A2-A0CV",
        "rung": "R3",
        "fields": {
            "NPOS": {"status": "accepted", "value": "2", "quote": "TWO OF EIGHTEEN (2/18) NODES"}
        },
    }
    log.write_text(json.dumps(row) + chr(10), encoding="utf-8")
    found = scan_box("TCGA-A2-A0CV", tmp_path, log)
    assert found["page"] == 0 and found["field"] == "NPOS"
    assert [b["y0"] for b in found["boxes"]] == [0.6]
    assert scan_box("TCGA-OTHER", tmp_path, log) is None


def test_sample_mode_serves_no_scan() -> None:
    client = TestClient(create_app(SampleData()))
    case_id = client.get("/api/queue").json()[0]["case_id"]
    assert client.get(f"/api/case/{case_id}/scanbox").json() == {"scanbox": None}
    assert client.get(f"/api/case/{case_id}/scan/0.png").status_code == 404


def test_closed_takes_each_field_at_the_rung_it_left_the_need(tmp_path: Path) -> None:
    from app.web.trace import latest_trace

    log = tmp_path / "chunks.jsonl"
    rows = [
        {
            "case": "C",
            "run_id": "run-1",
            "rung": "R1",
            "step": 1,
            "outgoing_need": ["N"],
            "fields": {
                "N": {"status": "accepted", "value": "N1"},
                "NPOS": {"status": "accepted", "value": "3"},
            },
        },
        {
            "case": "C",
            "run_id": "run-1",
            "rung": "R2",
            "step": 2,
            "outgoing_need": [],
            "fields": {
                "N": {"status": "accepted", "value": "N1MI"},
                "NPOS": {"status": "accepted", "value": "4"},
            },
        },
    ]
    log.write_text("".join(json.dumps(r) + chr(10) for r in rows), encoding="utf-8")
    closed = latest_trace("C", log)["closed"]
    assert closed == {"NPOS": {"value": "3", "rung": "R1"}, "N": {"value": "N1MI", "rung": "R2"}}


def test_the_redteam_endpoint_serves_the_logged_v3_chains() -> None:
    client = TestClient(create_app(SampleData()))
    chains = client.get("/api/redteam").json()["chains"]
    assert [c["case"] for c in chains] == ["TCGA-E2-A10B", "TCGA-OL-A5RU", "TCGA-BH-A6R8"]
    assert all(len(c["steps"]) == 20 and c["accepts_wrong"] == 0 for c in chains)
