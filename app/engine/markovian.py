"""Run the vendored Meterless Markovian engine from Python through its Node sidecar.

The engine (unmodified, vendor/meterless-markovian) owns the chunk loop, the marker
protocol, the carryover cascade, completion, abort and the run record. Python supplies
the generator: for each chunk the sidecar sends the engine's prompt here, and
`generate(step, prompt)` returns the chunk text (with [STATE_CHECKPOINT] / [TASK_COMPLETE]).
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = Path(__file__).with_name("markovian_sidecar.ts")
CONFORMANCE = ROOT / "vendor" / "meterless-markovian" / "conformance" / "runner.ts"
NODE_FLAGS = ("--experimental-transform-types", "--no-warnings")
DEFAULT_CHUNKS = {"chunkSize": 8000, "maxChunks": 6, "carryoverTokens": 256, "overlapTokens": 0}
_LINE_LIMIT = 1 << 24

Generate = Callable[[int, str], Awaitable[str]]


class EngineError(RuntimeError):
    pass


@dataclass
class EngineRun:
    record: dict[str, Any]
    levels: list[str]
    prompts: list[str] = field(default_factory=list)  # what the engine sent per chunk

    @property
    def status(self) -> str:
        return str(self.record.get("status"))

    @property
    def chunks(self) -> list[dict[str, Any]]:
        return list(self.record.get("chunks") or [])


def node_path() -> str:
    node = shutil.which("node")
    if node is None:
        raise EngineError("Node.js >= 22.7 is required for the Markovian engine (node not found)")
    return node


async def run_engine(
    goal: str,
    generate: Generate,
    *,
    chunk_config: dict[str, int] | None = None,
    memory_context: str | None = None,
    abort_after: int | None = None,
) -> EngineRun:
    """One Markovian run. abort_after=k aborts the run after chunk k (tests, kill drills)."""
    process = await asyncio.create_subprocess_exec(
        node_path(),
        *NODE_FLAGS,
        str(SIDECAR),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=_LINE_LIMIT,
    )
    assert process.stdin is not None and process.stdout is not None
    stderr_lines: list[str] = []

    async def drain_stderr() -> None:  # never let a chatty sidecar block on a full pipe
        assert process.stderr is not None
        async for raw in process.stderr:
            stderr_lines.append(raw.decode("utf-8", "replace").rstrip())
            del stderr_lines[:-50]

    drainer = asyncio.create_task(drain_stderr())

    async def send(message: dict[str, Any]) -> None:
        process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        await process.stdin.drain()

    async def receive() -> dict[str, Any]:
        line = await process.stdout.readline()
        if not line:
            await asyncio.sleep(0.05)  # let the drainer collect the last stderr lines
            error = " | ".join(stderr_lines[-5:]).strip()
            raise EngineError(f"Markovian sidecar exited: {error[:300] or 'no output'}")
        return json.loads(line.decode("utf-8"))

    prompts: list[str] = []
    try:
        ready = await receive()
        if not ready.get("ready"):
            raise EngineError(f"Markovian sidecar did not start: {ready}")
        params: dict[str, Any] = {"goal": goal, "chunkConfig": chunk_config or DEFAULT_CHUNKS}
        if memory_context:
            params["memoryContext"] = memory_context
        await send({"id": 1, "method": "run", "params": params})
        while True:
            message = await receive()
            if message.get("cb") == "generate":
                step, prompt = int(message["step"]), str(message["prompt"])
                prompts.append(prompt)
                try:
                    text = await generate(step, prompt)
                except Exception as exc:  # the engine records it as an errored run
                    await send({"cb_id": message["cb_id"], "error": f"{type(exc).__name__}: {exc}"})
                    continue
                if abort_after is not None and step >= abort_after:
                    # Abort BEFORE handing back the text: the engine checks the signal right
                    # after it stores the chunk, so exactly `step` chunks are kept.
                    await send({"id": 1, "method": "abort"})
                await send({"cb_id": message["cb_id"], "text": text})
            elif "result" in message:
                result = message["result"]
                return EngineRun(
                    record=result["run"], levels=list(result["levels"]), prompts=prompts
                )
            elif "error" in message:
                raise EngineError(str(message["error"]))
    finally:
        if process.returncode is None:
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except TimeoutError:
                process.kill()
                await process.wait()
        drainer.cancel()


async def run_conformance() -> tuple[int, str]:
    """Run the vendored conformance suite on the vendored reference: (exit code, output)."""
    process = await asyncio.create_subprocess_exec(
        node_path(),
        *NODE_FLAGS,
        str(CONFORMANCE),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    return int(process.returncode or 0), output.decode("utf-8", "replace")
