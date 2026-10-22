"""RUNGS through the real Markovian engine (Node sidecar), with a fake reader: no network."""

from __future__ import annotations

import json
import shutil

import pytest

from app.engine.rungs import R1, R2, R3, CaseEvidence, climb
from app.reader.reader import NODES_POSITIVE, FieldResult, ReadResult

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")


def _result(case_id: str, budget: int, n: tuple[str, str | None], count: tuple[str, str | None]):
    fields = {
        "T": FieldResult("T", "abstained", reason="model_abstained"),
        "N": FieldResult(
            "N", n[0], n[1], reason="ok" if n[0] == "accepted" else "quote_not_in_report"
        ),
        NODES_POSITIVE: FieldResult(
            NODES_POSITIVE,
            count[0],
            count[1],
            reason="" if count[0] == "accepted" else "count_not_in_quote",
        ),
    }
    return ReadResult(
        case_id=case_id,
        model="private/nvidia/nemotron-3.5-super-120b-a12b",
        receipt_id=None,
        provider="nvidia",
        fields=fields,
        budget=budget,
        usage={"completion_tokens": 19 if budget == 0 else 1000},
    )


def _reader(script: dict[str, tuple], seen: list[dict[str, object]]):
    async def read(case_id, document, *, provider, budget, run_id):  # type: ignore[no-untyped-def]
        assert "[CARRYOVER STATE]" not in document  # the model never sees the carryover
        rung = run_id.rsplit("-", 1)[1]
        seen.append({"rung": rung, "budget": budget, "document": document[:12]})
        n, count = script[rung]
        return _result(case_id, budget, n, count)

    return read


CASE = CaseEvidence("TCGA-AA-0001", "REPORT TEXT", recorded_n="N1A", registry_count=4.0)


@pytest.mark.asyncio
async def test_r1_may_clear_but_never_accuse() -> None:
    # R1 agrees with the registry on N (clears it) but reads count 2 vs the registry's 4:
    # a cheap read cannot accuse, so the count climbs to R2, which accepts 2.
    seen: list[dict[str, object]] = []
    script = {
        R1: (("accepted", "N1A"), ("accepted", "2")),
        R2: (("accepted", "N1A"), ("accepted", "2")),
    }
    ladder = await climb(CASE, run_id="t1", reader=_reader(script, seen))
    assert ladder.run.status == "completed"
    assert [s["rung"] for s in seen] == [R1, R2] and [s["budget"] for s in seen] == [0, 4000]
    assert ladder.closed == {
        "N": {"rung": R1, "value": "N1A"},
        NODES_POSITIVE: {"rung": R2, "value": "2"},
    }
    assert ladder.open_fields == []
    assert ladder.run.levels == ["marker", "marker"]
    # every chunk logs the carryover it received, verbatim
    assert json.loads(ladder.chunks[1]["incoming_carryover"])["need"] == [NODES_POSITIVE]


@pytest.mark.asyncio
async def test_closes_at_rung_one_when_the_cheap_read_agrees() -> None:
    case = CaseEvidence("TCGA-AA-0002", "TEXT", recorded_n="N1", registry_count=2.0)
    script = {R1: (("accepted", "N1A"), ("accepted", "2"))}
    ladder = await climb(case, run_id="t2", reader=_reader(script, []))
    assert ladder.run.status == "completed" and len(ladder.run.chunks) == 1
    assert {v["rung"] for v in ladder.closed.values()} == {R1}


@pytest.mark.asyncio
async def test_climbs_to_the_scan_then_a_person() -> None:
    seen: list[dict[str, object]] = []
    case = CaseEvidence(
        "TCGA-AA-0003", "TEXT", recorded_n="N2", registry_count=1.0, scan_text="SCAN TEXT"
    )
    script = {
        R1: (("rejected", "N1"), ("rejected", "1")),
        R2: (("rejected", "N1"), ("accepted", "1")),
        R3: (("rejected", "N1"), ("accepted", "1")),
    }
    ladder = await climb(case, run_id="t3", reader=_reader(script, seen))
    assert [s["rung"] for s in seen] == [R1, R2, R3]
    assert seen[2]["document"] == "SCAN TEXT"  # R3 reads Parse's text of the scan
    assert ladder.closed[NODES_POSITIVE]["rung"] == R2
    assert ladder.open_fields == ["N"]  # the ladder ran out: a person decides
    assert ladder.run.status == "completed" and ladder.chunks[-1]["done"] is True


@pytest.mark.asyncio
async def test_without_a_scan_the_ladder_ends_after_r2() -> None:
    script = {
        R1: (("rejected", None), ("abstained", None)),
        R2: (("rejected", None), ("abstained", None)),
    }
    ladder = await climb(CASE, run_id="t4", reader=_reader(script, []))
    assert len(ladder.run.chunks) == 2 and ladder.open_fields == ["N", NODES_POSITIVE]


@pytest.mark.asyncio
async def test_on_close_is_called_once_per_closed_field() -> None:
    closed: list[tuple[str, str]] = []

    async def on_close(name, rung, fr, result):  # type: ignore[no-untyped-def]
        closed.append((name, rung))

    script = {
        R1: (("accepted", "N1A"), ("rejected", "9")),
        R2: (("accepted", "N1A"), ("accepted", "2")),
    }
    await climb(CASE, run_id="t5", reader=_reader(script, []), on_close=on_close)
    # R1's count was rejected, so its N is not self-consistent: it cannot clear N either.
    assert closed == [("N", R2), (NODES_POSITIVE, R2)]


@pytest.mark.asyncio
async def test_a_self_contradictory_cheap_read_cannot_clear_a_contradictory_record() -> None:
    # Live 10-23 (TCGA-A1-A0SN shape): the registry says N1 and 4 positive nodes; thinking
    # OFF read "4 positive nodes" yet answered N1A, agreeing with BOTH registry fields.
    # 4 nodes is N2 under the count rule, so R1 is not self-consistent and both fields climb.
    seen: list[dict[str, object]] = []
    case = CaseEvidence("TCGA-AA-0006", "TEXT", recorded_n="N1", registry_count=4.0, edition="6")
    script = {
        R1: (("accepted", "N1A"), ("accepted", "4")),
        R2: (("accepted", "N2A"), ("accepted", "4")),
    }
    ladder = await climb(case, run_id="t6", reader=_reader(script, seen))
    assert [s["rung"] for s in seen] == [R1, R2]
    assert ladder.chunks[0]["self_consistent"] is False
    assert ladder.closed == {
        "N": {"rung": R2, "value": "N2A"},
        NODES_POSITIVE: {"rung": R2, "value": "4"},
    }
