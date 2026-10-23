"""The dial test: the ladder on consistent records against a 4k control (no network)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.engine import dial
from app.reader.reader import NODES_POSITIVE, FieldResult, ReadResult


def test_r1_closings_are_compared_with_the_control() -> None:
    control = {
        "N": {"status": "accepted", "value": "N1A"},
        NODES_POSITIVE: {"status": "accepted", "value": "3"},
    }
    assert dial.compare({"N": "N1A", NODES_POSITIVE: "2"}, control) == {
        "N": "agree",
        NODES_POSITIVE: "disagree",
    }
    assert dial.compare({"N": "N1"}, {"N": {"status": "rejected", "value": None}}) == {
        "N": "unconfirmed"
    }


def test_the_summary_scores_only_records_without_a_provider_failure() -> None:
    ok = {
        "provider_failure": False,
        "settled_at_r1": True,
        "agreement": {"N": "agree", NODES_POSITIVE: "agree"},
        "rungs": ["R1"],
        "ladder_tokens": 300,
        "control_tokens": 4200,
        "ladder_seconds": 5,
        "control_seconds": 80,
    }
    bad = {"provider_failure": True}
    unsafe = {**ok, "settled_at_r1": False, "agreement": {"N": "disagree"}, "rungs": ["R1", "R2"]}
    s = dial.summarise([ok, ok, unsafe, bad])
    assert s["scored"] == 3 and s["provider_failures"] == 1 and not s["void"]
    assert s["settled_at_r1"] == 2 and s["fields_closed_at_r1"] == 5 and s["fields_needing_r2"] == 1
    assert s["r1_vs_control"] == {"agree": 4, "disagree": 1, "unconfirmed": 0}
    assert s["r1_unsafe"] is True  # 1 of 5 closings contradicted > 10 %
    assert s["ladder_tokens"] == 900 and s["control_tokens"] == 12600
    assert dial.summarise([bad] * 11)["void"] is True


@pytest.mark.asyncio
async def test_one_record_runs_the_ladder_then_the_control(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = SimpleNamespace(case_id="TCGA-XX-0001", report_text="report")
    ladder = SimpleNamespace(
        run=SimpleNamespace(status="completed"),
        chunks=[{"rung": "R1", "usage": {"completion_tokens": 200}}],
        closed={"N": {"rung": "R1", "value": "N1A"}, NODES_POSITIVE: {"rung": "R1", "value": "2"}},
        open_fields=[],
    )
    seen: dict[str, Any] = {}

    async def fake_evidence(case_id: str):
        return evidence

    async def fake_climb(ev, *, run_id: str, provider: str):
        seen["provider"] = provider
        return ladder

    async def fake_read(case_id, report, *, provider, budget, run_id):
        seen["control"] = (provider, budget)
        fields = {
            "N": FieldResult("N", "accepted", "N1A"),
            NODES_POSITIVE: FieldResult(NODES_POSITIVE, "accepted", "2"),
        }
        return ReadResult(
            case_id,
            "m",
            "r",
            "nightshift",
            fields=fields,
            usage={"completion_tokens": 4100},
            signature="verified",
        )

    monkeypatch.setattr(dial, "load_evidence", fake_evidence)
    monkeypatch.setattr(dial, "climb", fake_climb)
    monkeypatch.setattr(dial, "read_report", fake_read)
    monkeypatch.setattr(dial, "write_trace", lambda *a, **k: None)
    row = await dial.run_one("TCGA-XX-0001", "t")
    assert seen == {"provider": "nightshift", "control": ("nightshift", 4000)}
    assert row["settled_at_r1"] and row["agreement"] == {"N": "agree", NODES_POSITIVE: "agree"}
    assert (
        row["ladder_tokens"] == 200
        and row["control_tokens"] == 4100
        and not row["provider_failure"]
    )
