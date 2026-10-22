"""T1-T3: the vendored Markovian engine through the Node sidecar (no network, no model)."""

from __future__ import annotations

import json
import shutil

import pytest

from app.engine.markovian import run_conformance, run_engine

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")


def _chunk(state: dict[str, object], done: bool, verdict: str) -> str:
    # [TASK_COMPLETE] must precede the checkpoint: the state marker captures to the end.
    head = "[TASK_COMPLETE]\n" if done else ""
    return f"{verdict}\n{head}[STATE_CHECKPOINT]\n{json.dumps(state)}"


@pytest.mark.asyncio
async def test_t1_conformance_passes_on_the_vendored_files() -> None:
    code, output = await run_conformance()
    assert code == 0, output[-500:]
    assert "8/8 checks passed" in output


@pytest.mark.asyncio
async def test_t2_code_written_carryover_drives_the_chain() -> None:
    model_messages: list[str] = []

    async def fake_model(text: str) -> str:
        model_messages.append(text)
        return "ok"

    async def generate(step: int, prompt: str) -> str:
        if step > 1:
            assert "[CARRYOVER STATE]" in prompt
            state = json.loads(prompt.split("[CARRYOVER STATE]\n", 1)[1].split("\n\n", 1)[0])
            assert state["step_done"] == step - 1  # the engine carried our state
        await fake_model(f"read case part {step}")  # the model never sees the engine prompt
        state = {"step_done": step, "need": [] if step == 3 else ["N"], "note": "x" * 10}
        return _chunk(state, done=step == 3, verdict=f"rung {step} verdict")

    run = await run_engine("audit case TCGA-TEST-0001", generate)
    assert run.status == "completed"
    assert len(run.chunks) == 3
    assert run.levels == ["marker", "marker", "marker"]
    assert all("[STATE_CHECKPOINT]" not in chunk["content"] for chunk in run.chunks)
    assert not any("[CARRYOVER STATE]" in message for message in model_messages)
    assert run.record["chunkConfig"]["maxChunks"] == 6
    assert run.record["tokenLabel"] == "estimated"


@pytest.mark.asyncio
async def test_t3_abort_keeps_the_chunks_already_paid_for() -> None:
    async def generate(step: int, prompt: str) -> str:
        return _chunk({"step_done": step, "need": ["N"], "pad": "y" * 10}, False, f"v{step}")

    run = await run_engine("audit case TCGA-TEST-0002", generate, abort_after=2)
    assert run.status == "aborted"
    assert len(run.chunks) == 2


@pytest.mark.asyncio
async def test_a_generator_failure_ends_the_run_as_errored() -> None:
    async def generate(step: int, prompt: str) -> str:
        if step == 2:
            raise RuntimeError("provider down")
        return _chunk({"step_done": step, "need": ["N"], "pad": "z" * 10}, False, "v")

    run = await run_engine("audit case TCGA-TEST-0003", generate)
    assert run.status == "errored" and "provider down" in run.record.get("error", "")
    assert len(run.chunks) == 1
