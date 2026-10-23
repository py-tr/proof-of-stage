"""The red-team chain on the real (vendored) engine, with a scripted fake model."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.engine import adversary as adv
from app.providers.receipts import Receipt

REPORT = (
    "A. Sentinel lymph node: metastatic carcinoma in one lymph node (1/1). "
    "B. Axillary: metastatic carcinoma in one lymph node (1/1). "
    "Tumor size 14 mm. Overall 2 lymph nodes are positive. Total number sampled: 9."
)
CASE = adv.Case("TCGA-XX-0001", true_count=2, start=0, end=len(REPORT))
ATTACKS = [
    {"N": 14, "quote": "Tumor size 14 mm"},  # niq: a size
    {"N": 1, "quote": "metastatic carcinoma in one lymph node (1/1)"},  # known limit
    {"N": 2, "quote": "Overall 2 lymph nodes are positive"},  # the true count
    {"N": 9, "quote": "Total number sampled: 9"},  # niq
]

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")


@needs_node
@pytest.mark.asyncio
async def test_a_chain_carries_the_code_written_ledger(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(adv, "LOG", tmp_path / "steps.jsonl")
    monkeypatch.setattr(adv, "RUNS_LOG", tmp_path / "runs.jsonl")
    sent: list[str] = []

    async def fake_chat(messages: list[dict[str, Any]], model: str, **kwargs: Any):
        sent.append(messages[1]["content"])
        assert kwargs["chat_template_kwargs"]["reasoning_budget"] == adv.THINKING_BUDGET
        step = len(sent)
        if step == 5:
            raise RuntimeError("provider_deadline")  # scored, never re-run
        attack = ATTACKS[(step - 1) % len(ATTACKS)]
        usage = {"prompt_tokens": 300, "completion_tokens": 900}
        return json.dumps(attack), Receipt(
            receipt_id=f"r{step}", winning_model=model, signature="verified", usage=usage
        )

    record = await adv.run_chain(CASE, REPORT, provider="nightshift", chat=fake_chat)
    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text().splitlines()]

    assert len(sent) == adv.STEPS and record["steps"] == adv.STEPS
    assert record["engine_chunks"] == adv.STEPS
    # from step 2 on, the model sees the engine's carryover, which is our ledger
    assert "none yet" in sent[0] and all(s["carryover_from_engine"] for s in steps[1:])
    assert '1 14 "Tumor size 14 mm" niq' in sent[1]
    assert set(record["engine_levels"]) == {"marker"}
    assert steps[1]["kind"] == "fraction_under" and steps[2]["verdict"] == "true_count"
    assert steps[4]["verdict"] == "call_failed" and "error" in steps[4]
    # the same attack again is a carryover failure, not a new bug
    assert steps[5]["repeat"] is True
    assert record["bugs"] == [] and [k["kind"] for k in record["known_limit_accepts"]] == [
        "fraction_under"
    ]
    assert record["ledger_over_budget_steps"] == 0 and record["unverified_receipts"] == 0
    assert record["tokens_saved_est"] > 0
    assert record["markovian_prompt_tokens_measured"] == 300 * (adv.STEPS - 1)


def test_the_ledger_line_is_short_and_coded() -> None:
    a = adv.Attempt(3, 14, 'Tumor size "14" mm and more', "count_not_in_quote", "x")
    assert a.ledger_line() == "3 14 \"Tumor size '14' mm\" niq"


def test_the_run_refuses_a_changed_pre_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen = json.loads(adv.PREREG.read_text(encoding="utf-8"))
    frozen["prompt_sha"] = "000000000000"
    frozen["cases"] = [{**frozen["cases"][0], "excerpt_sha256_16": "0" * 16}]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(frozen), encoding="utf-8")
    monkeypatch.setattr(adv, "PREREG", path)
    reports = {frozen["cases"][0]["case_id"]: "x" * 4000}
    with pytest.raises(RuntimeError, match="prompt changed.*excerpt changed"):
        adv.frozen_cases(reports)


@needs_node
@pytest.mark.asyncio
async def test_the_nvidia_generator_uses_the_pre_registered_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(adv, "LOG", tmp_path / "steps.jsonl")
    monkeypatch.setattr(adv, "RUNS_LOG", tmp_path / "runs.jsonl")
    seen: list[dict[str, Any]] = []

    async def fake_nv(messages: list[dict[str, Any]], model: str, **kwargs: Any):
        seen.append(kwargs)
        usage = {"prompt_tokens": 250, "completion_tokens": 400}
        return json.dumps(ATTACKS[0]), "served-model", usage

    record = await adv.run_chain(CASE, REPORT, nv_chat=fake_nv)
    assert record["provider"] == "nvidia" and record["steps"] == adv.STEPS
    kwargs = seen[0]["chat_template_kwargs"]
    assert kwargs == {"enable_thinking": True, "reasoning_budget": adv.THINKING_BUDGET}
    assert record["unverified_receipts"] == 0
    assert record["carryover_failures"] == adv.STEPS - 1  # the same attack every step
