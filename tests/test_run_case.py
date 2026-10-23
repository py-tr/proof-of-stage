"""store_ladder: what a completed ladder writes to Zetaris (fake inserts, no network)."""

from __future__ import annotations

import pytest

from app.engine import run_case as rc
from app.engine.markovian import EngineRun
from app.engine.rungs import R1, R2, R3, Ladder
from app.reader.quotes import Span
from app.reader.reader import FieldResult, ReadResult


def _ladder(status: str, closed: dict, open_fields: list[str]) -> Ladder:
    result = ReadResult(case_id="TCGA-AA-0001", model="m", receipt_id=None, provider="nvidia")
    closings = {
        name: (FieldResult(name, "accepted", info["value"], "q", Span(0, 5), "why"), result)
        for name, info in closed.items()
    }
    return Ladder(
        case_id="TCGA-AA-0001",
        run=EngineRun(record={"status": status, "chunks": []}, levels=[]),
        closed=closed,
        open_fields=open_fields,
        last_reasons={name: "R2:quote_not_in_report" for name in open_fields},
        closings=closings,
    )


@pytest.fixture
def writes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    seen: dict[str, list] = {"extractions": [], "flags": []}

    async def fake_extraction(**kwargs):  # type: ignore[no-untyped-def]
        seen["extractions"].append(kwargs)

    async def fake_flag(**kwargs):  # type: ignore[no-untyped-def]
        seen["flags"].append(kwargs)

    async def fake_existing(case_id):  # type: ignore[no-untyped-def]
        return {"NPOS": "1"}

    monkeypatch.setattr(rc, "insert_extraction", fake_extraction)
    monkeypatch.setattr(rc, "insert_flag", fake_flag)
    monkeypatch.setattr(rc, "existing_fields", fake_existing)
    return seen


@pytest.mark.asyncio
async def test_store_outcomes_per_field(writes: dict[str, list]) -> None:
    ladder = _ladder(
        "completed",
        {"N": {"rung": R2, "value": "N2A"}, "NPOS": {"rung": R1, "value": "4"}},
        [],
    )
    outcome = await rc.store_ladder(ladder)
    assert outcome == {"N": "stored", "NPOS": "kept-earlier: 1"}
    stored = [w for w in writes["extractions"] if w["field"] == "N"]
    assert stored and stored[0]["model"] == "m" and stored[0]["method"] == "nemotron_reader"


@pytest.mark.asyncio
async def test_scan_rung_is_logged_not_stored_and_open_fields_are_flagged(
    writes: dict[str, list],
) -> None:
    ladder = _ladder("completed", {"N": {"rung": R3, "value": "N1"}}, ["NPOS"])
    outcome = await rc.store_ladder(ladder)
    assert outcome == {"N": "scan-not-stored", "NPOS": "flagged"}
    assert writes["extractions"] == []
    assert (
        writes["flags"][0]["field"] == "NPOS"
        and "quote_not_in_report" in writes["flags"][0]["reason"]
    )


@pytest.mark.asyncio
async def test_an_unfinished_run_stores_nothing(writes: dict[str, list]) -> None:
    ladder = _ladder("aborted", {"N": {"rung": R1, "value": "N1"}}, ["NPOS"])
    outcome = await rc.store_ladder(ladder)
    assert outcome == {"N": "not-stored: run aborted"}
    assert writes["extractions"] == [] and writes["flags"] == []


def test_budget_honoured() -> None:
    off = {"budget": 0, "usage": {"completion_tokens_details": {"reasoning_tokens": 0}}}
    over = {"budget": 4000, "usage": {"completion_tokens_details": {"reasoning_tokens": 4100}}}
    assert rc.budget_honoured(off) is True and rc.budget_honoured(over) is False
    assert rc.budget_honoured({"budget": 0, "usage": {}}) is None


def test_budget_honoured_through_nightshift_uses_completion_tokens() -> None:
    # Nightshift's usage has no reasoning tokens: completion <= budget + the answer allowance
    assert rc.budget_honoured({"budget": 4000, "usage": {"completion_tokens": 4233}}) is True
    assert rc.budget_honoured({"budget": 0, "usage": {"completion_tokens": 804}}) is False
