"""The case note: facts from the USL record, a per-sentence guard, the signed Nightshift call."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.notes import note as note_mod
from app.providers.receipts import Receipt
from app.web.api import create_app
from app.web.data import SampleData

FOUND = {
    "check": {
        "case_id": "TCGA-A2-A0CV",
        "site_key": "breast",
        "edition_code": "6",
        "recorded_n": "N1A",
        "lymph_nodes_positive": "4.0",
        "lymph_nodes_tested": "18.0",
        "derived_n": "pN2a",
        "fault_field": "node_count",
    },
    "accepted": [
        {"field": "T", "value": "T2", "quote": "a mass 4.1 cm", "checks": [{"ok": True}]},
        {"field": "N", "value": "N1A", "quote": "2/18) POSITIVE", "checks": [{"ok": True}]},
        {"field": "NPOS", "value": "2", "quote": "2/18) POSITIVE", "checks": [{"ok": True}]},
        {"field": "NPOS", "value": "9", "quote": "a failed one", "checks": [{"ok": False}]},
    ],
}


def _answer(*sentences: tuple[str, list[str]]) -> dict[str, Any]:
    return {"sentences": [{"text": text, "cites": cites} for text, cites in sentences]}


def test_facts_hold_the_registry_rule_verdict_and_only_verified_n_quotes() -> None:
    facts = note_mod.build_facts(FOUND)
    assert "N1A" in facts["F1"] and "4 positive nodes of 18" in facts["F2"]
    assert "pN2a" in facts["F3"] and "positive-node count field" in facts["F4"]
    quotes = [v for k, v in facts.items() if k.startswith("Q")]
    assert len(quotes) == 2  # T stays out; a quote that failed its re-check stays out
    assert all("2/18" in q for q in quotes)


def test_a_note_that_restates_cited_facts_passes() -> None:
    facts = note_mod.build_facts(FOUND)
    sentences, reason = note_mod.check_note(
        _answer(
            ("The registry records N1A and 4 positive nodes of 18 examined.", ["F1", "F2"]),
            ("The report is verified as positive-node count 2.", ["Q2"]),
            ("The semantic layer names the count field; a person decides.", ["F4"]),
        ),
        facts,
    )
    assert reason == "" and len(sentences) == 3


@pytest.mark.parametrize(
    ("sentence", "cites", "reason"),
    [
        (
            "The registry records 5 positive nodes.",
            ["F2"],
            "sentence_1_states_5_not_in_cited_facts",
        ),
        ("The registry should say N2A.", ["F1"], "sentence_1_states_N2A_not_in_cited_facts"),
        # a number that is in the facts, but not in the fact this sentence cites
        ("The report counts 2 positive nodes.", ["F1"], "sentence_1_states_2_not_in_cited_facts"),
        ("The count is wrong.", [], "sentence_1_no_citation"),
        ("The count is wrong.", ["F9"], "sentence_1_cites_unknown_F9"),
        ("F4 names the count field.", ["F4"], "sentence_1_fact_id_in_text"),
        (" ".join(["word"] * 40), ["F4"], "sentence_1_too_long"),
    ],
)
def test_the_guard_rejects_a_sentence_the_facts_do_not_back(
    sentence: str, cites: list[str], reason: str
) -> None:
    facts = note_mod.build_facts(FOUND)
    sentences, got = note_mod.check_note(_answer((sentence, cites)), facts)
    assert sentences == [] and got == reason


def test_the_guard_rejects_unreadable_or_oversized_notes() -> None:
    facts = note_mod.build_facts(FOUND)
    assert note_mod.check_note(None, facts)[1] == "answer_not_json"
    assert note_mod.check_note({"sentences": []}, facts)[1] == "sentence_count"
    five = _answer(*[("A person decides.", ["F4"])] * 5)
    assert note_mod.check_note(five, facts)[1] == "sentence_count"


@pytest.mark.asyncio
async def test_write_note_pins_super_vl_requires_a_signature_and_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(note_mod, "NOTES_LOG", tmp_path / "case-notes.jsonl")
    seen: dict[str, Any] = {}

    async def fake_chat(messages: list[dict[str, Any]], model: str, **kwargs: Any):
        seen.update(kwargs, model=model, messages=messages)
        text = json.dumps(_answer(("The semantic layer names the count field.", ["F4"])))
        return text, Receipt(receipt_id="r1", winning_model=model, signature="verified")

    result = await note_mod.write_note(FOUND, chat=fake_chat)
    assert result["status"] == "accepted" and result["receipt"]["signature"] == "verified"
    assert seen["require_model"] == seen["model"] and seen["require_signature"] is True
    assert seen["allow_cache"] is False and seen["item_id"].startswith("note-TCGA-A2-A0CV-")
    assert "F4: The semantic layer names" in seen["messages"][1]["content"]
    assert note_mod.latest_note("TCGA-A2-A0CV")["receipt"]["receipt_id"] == "r1"
    assert note_mod.latest_note("TCGA-OTHER") is None


def test_sample_mode_writes_no_note_and_replays_none() -> None:
    client = TestClient(create_app(SampleData()))
    case_id = client.get("/api/queue").json()[0]["case_id"]
    assert client.get(f"/api/case/{case_id}/note").json() == {"note": None}
    assert client.post(f"/api/case/{case_id}/note").status_code == 409


def test_a_number_before_a_full_stop_counts() -> None:
    facts = {"Q1": 'The report states "LYMPH NODES POSITIVE: 1. LYMPH NODES EXAMINED: 23"'}
    answer = _answer(("The report states 1 positive node of 23 examined.", ["Q1"]))
    assert note_mod.check_note(answer, facts)[1] == ""
    assert note_mod._tokens("size 2.4 cm") == {"2.4"}
