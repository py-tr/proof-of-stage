"""RUNGS: one Markovian run per case climbs a ladder of independent evidence, one rung per chunk.

R1  Super, thinking OFF, on the report text. It may only CLEAR a field (an accepted value
    that agrees with the registry), never accuse one, and only when its own N and count are
    consistent under the count rule (live 10-23: thinking OFF read "4 positive nodes" yet
    answered N1A, matching a wrong registry N; the rule check sends that case up the ladder).
R2  Super, 4k thinking budget, on the report text, for the fields still open.
R3  Super, 4k thinking budget, on Nemotron Parse's reading of the original scan.

Our code writes the carryover after every rung: {case, need, consulted, ledger}. A rung's
model call sees only the fixed reader prompt and one document, never the carryover or an
earlier answer, so no reading can anchor the next. The run ends when `need` is empty
([TASK_COMPLETE]) or the ladder runs out (the open fields go to a person). Budgeted reads go
to NVIDIA directly: Nightshift currently overwrites the thinking switch and forwards no
budget (docs/evidence/nightshift-limits.md).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.engine.markovian import EngineRun, run_engine
from app.reader.reader import (
    NODES_POSITIVE,
    THINKING_BUDGET,
    THINKING_OFF,
    FieldResult,
    ReadResult,
    read_report,
)

R1, R2, R3 = "R1", "R2", "R3"
LADDER = (R1, R2, R3)
OPEN_FIELDS = ("N", NODES_POSITIVE)  # what fault_field needs
_MAIN_N = re.compile(r"N[0-9X]")
CHUNK_CONFIG = {"chunkSize": 8000, "maxChunks": 6, "carryoverTokens": 256, "overlapTokens": 0}

Reader = Callable[..., Awaitable[ReadResult]]


@dataclass
class CaseEvidence:
    case_id: str
    report_text: str
    recorded_n: str | None  # e.g. "N1A"
    registry_count: float | None  # positive nodes recorded
    scan_text: str | None = None  # Nemotron Parse's text of the original PDF, if available
    edition: str | None = None  # staging edition code, for the count rule


@dataclass
class Ladder:
    case_id: str
    run: EngineRun
    closed: dict[str, dict[str, Any]] = field(default_factory=dict)  # field -> {rung, value}
    open_fields: list[str] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)  # one log row per rung
    conflicts: dict[str, list[str]] = field(default_factory=dict)  # field -> accepted values
    last_reasons: dict[str, str] = field(default_factory=dict)  # open field -> last reason
    # not serialised: the FieldResult/ReadResult behind each closed field, for storing
    closings: dict[str, tuple[FieldResult, ReadResult]] = field(default_factory=dict, repr=False)


def main_n(value: str | None) -> str | None:
    match = _MAIN_N.search((value or "").upper())
    return match.group(0) if match else None


def rule_main_n(count: str | None, edition: str | None) -> str | None:
    """The main N category the paraphrased count rule gives for a positive-node count."""
    from app.web.evidence import count_rules

    outputs = {main_n(rule["output"]) for rule in count_rules(count, True, edition or "7")}
    outputs.discard(None)
    return outputs.pop() if len(outputs) == 1 else None


def self_consistent(result: ReadResult, edition: str | None) -> bool:
    """The reading's own N and its own verified count agree under the count rule."""
    n, count = result.fields["N"], result.fields[NODES_POSITIVE]
    if n.status != "accepted" or count.status != "accepted":
        return False
    expected = rule_main_n(count.value, edition)
    return expected is not None and expected == main_n(n.value)


def agrees_with_registry(name: str, fr: FieldResult, case: CaseEvidence) -> bool:
    if fr.status != "accepted" or fr.value is None:
        return False
    if name == "N":
        return main_n(fr.value) is not None and main_n(fr.value) == main_n(case.recorded_n)
    if name == NODES_POSITIVE:
        return case.registry_count is not None and float(fr.value) == case.registry_count
    return False


def _state_from(prompt: str) -> dict[str, Any] | None:
    if "[CARRYOVER STATE]" not in prompt:
        return None
    block = prompt.split("[CARRYOVER STATE]\n", 1)[1].split("\n\n", 1)[0]
    try:
        state = json.loads(block)
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) else None


def _initial_state(case: CaseEvidence) -> dict[str, Any]:
    return {"case": case.case_id, "need": list(OPEN_FIELDS), "consulted": [], "ledger": {}}


def _comparable(name: str, value: str) -> str:
    """N by its main category, a count as an integer: what decides the verdict."""
    if name == "N":
        return main_n(value) or value
    try:
        return str(int(float(value)))
    except ValueError:
        return value


def _ledger_entry(rung: str, fr: FieldResult) -> str:
    mark = "ok" if fr.status == "accepted" else fr.reason or fr.status
    return f"{rung}:{fr.value or '-'}:{mark}"[:40]


class RungsGenerator:
    """The engine's generator: each call executes the next rung for one case."""

    def __init__(
        self,
        case: CaseEvidence,
        *,
        reader: Reader = read_report,
        run_id: str,
        provider: str = "nvidia",
    ) -> None:
        self.case = case
        self.reader = reader
        self.run_id = run_id
        self.provider = provider
        self.closings: dict[str, tuple[FieldResult, ReadResult]] = {}
        self.accepted: dict[str, set[str]] = {}  # every accepted value per field, all rungs
        self.last_reasons: dict[str, str] = {}
        self.closed: dict[str, dict[str, Any]] = {}
        self.chunks: list[dict[str, Any]] = []

    def _next_rung(self, state: dict[str, Any]) -> str | None:
        for rung in LADDER:
            if rung in state["consulted"]:
                continue
            if rung == R3 and not self.case.scan_text:
                state["consulted"].append(f"{R3}:no-scan")
                continue
            return rung
        return None

    async def _read(self, rung: str) -> ReadResult:
        budget = THINKING_OFF if rung == R1 else THINKING_BUDGET
        document = self.case.scan_text if rung == R3 else self.case.report_text
        return await self.reader(
            self.case.case_id,
            document,
            provider=self.provider,
            budget=budget,
            run_id=f"{self.run_id}-{rung}",
        )

    async def __call__(self, step: int, prompt: str) -> str:
        state = _initial_state(self.case) if step == 1 else _state_from(prompt)
        if state is None:
            raise ValueError("the engine did not carry the ladder state")
        incoming = json.dumps(state, sort_keys=True)
        rung = self._next_rung(state)
        if rung is None:  # nothing left to try
            return self._finish(state, "ladder exhausted", step, incoming, None, None)
        started = time.monotonic()
        result = await self._read(rung)
        seconds = round(time.monotonic() - started, 2)
        still_open = []
        consistent = self_consistent(result, self.case.edition)
        # remember accepted values (closed fields included) for the conflict check; a fast read
        # that failed the rule check is not evidence, so it cannot create a conflict
        trusted = rung != R1 or consistent
        for name in OPEN_FIELDS if trusted else ():
            fr = result.fields[name]
            if fr.status == "accepted" and fr.value is not None:
                self.accepted.setdefault(name, set()).add(_comparable(name, fr.value))
        for name in state["need"]:
            fr = result.fields[name]
            state["ledger"].setdefault(name, []).append(_ledger_entry(rung, fr))
            closes = (
                agrees_with_registry(name, fr, self.case) and consistent
                if rung == R1
                else fr.status == "accepted"
            )
            if closes:
                self.closed[name] = {"rung": rung, "value": fr.value}
                self.closings[name] = (fr, result)
            else:
                still_open.append(name)
                self.last_reasons[name] = f"{rung}:{fr.reason or fr.status}"[:120]
        state["need"] = still_open
        state["consulted"].append(rung)
        log = {
            "case": self.case.case_id,
            "step": step,
            "rung": rung,
            "budget": result.budget,
            "incoming_carryover": incoming,
            "model": result.model,
            "receipt_id": result.receipt_id,
            "signature": result.signature,
            "from_cache": result.from_cache,
            "usage": result.usage,
            "seconds": seconds,
            "self_consistent": consistent,
            "fields": {
                name: {"status": fr.status, "value": fr.value, "reason": fr.reason[:80]}
                for name, fr in result.fields.items()
            },
        }
        verdict = f"{rung} {self.case.case_id}: closed {sorted(self.closed)} open {still_open}"
        return self._finish(state, verdict, step, incoming, log, rung)

    def _finish(
        self,
        state: dict[str, Any],
        verdict: str,
        step: int,
        incoming: str,
        log: dict[str, Any] | None,
        rung: str | None,
    ) -> str:
        exhausted = self._peek_exhausted(state)
        done = not state["need"] or exhausted
        if log is None:
            log = {
                "case": self.case.case_id,
                "step": step,
                "rung": None,
                "incoming_carryover": incoming,
            }
        log["outgoing_need"] = list(state["need"])
        log["done"] = done
        self.chunks.append(log)
        checkpoint = json.dumps(state, sort_keys=True, separators=(",", ":"))
        # [TASK_COMPLETE] must come BEFORE the checkpoint (the state marker captures to the end).
        head = "[TASK_COMPLETE]\n" if done else ""
        return f"{verdict}\n{head}[STATE_CHECKPOINT]\n{checkpoint}"

    def _peek_exhausted(self, state: dict[str, Any]) -> bool:
        consulted = {item.split(":", 1)[0] for item in state["consulted"]}
        remaining = [r for r in LADDER if r not in consulted]
        if remaining == [R3] and not self.case.scan_text:
            return True
        return not remaining


async def climb(
    case: CaseEvidence,
    *,
    run_id: str,
    reader: Reader = read_report,
    provider: str = "nvidia",
    abort_after: int | None = None,
) -> Ladder:
    """One Markovian run for one case: the engine drives the ladder until no field is open.

    Nothing is stored here. A field two rungs accepted with different values is a conflict:
    it is demoted to open, so the caller flags it for a person instead of storing either.
    """
    generator = RungsGenerator(case, reader=reader, run_id=run_id, provider=provider)
    goal = (
        f"Settle the N category and the positive-node count of case {case.case_id} "
        "with verbatim evidence, cheapest rung first."
    )
    run = await run_engine(goal, generator, chunk_config=CHUNK_CONFIG, abort_after=abort_after)
    closed = dict(generator.closed)
    conflicts = {
        name: sorted(values)
        for name, values in generator.accepted.items()
        if name in closed and len(values) > 1
    }
    last_reasons = dict(generator.last_reasons)
    for name, values in conflicts.items():
        closed.pop(name)
        last_reasons[name] = f"conflict: rungs accepted {', '.join(values)}"
    return Ladder(
        case_id=case.case_id,
        run=run,
        closed=closed,
        open_fields=[name for name in OPEN_FIELDS if name not in closed],
        chunks=generator.chunks,
        conflicts=conflicts,
        last_reasons={
            name: last_reasons.get(name, "") for name in OPEN_FIELDS if name not in closed
        },
        closings={name: generator.closings[name] for name in closed},
    )
