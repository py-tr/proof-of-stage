"""`python -m app.cli run --case X [--store]`: one case through the RUNGS ladder, with a trace.

Evidence: the registry row from the Zetaris USL (stage_check), the report text, and Nemotron
Parse's reading of the original scan when it has been parsed (data/scans/<case>/blocks.json).
Every run appends its engine record to logs/markovian-runs.jsonl and one row per rung to
logs/markovian-chunks.jsonl.

With --store, and only after a COMPLETED run, each field gets one recorded outcome:
- stored: appended to Zetaris (method nemotron_reader, the plain served model name);
- kept-earlier: the case already has a row for that field (append-only, first write wins);
- scan-not-stored: closed on the scan rung, whose quote offsets refer to Parse's text, not
  the report text the page highlights;
- flagged: still open (or two rungs disagreed), a reader_review flag for a person.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.rungs import LADDER_PROVIDER, R3, CaseEvidence, Ladder, climb
from app.reader.reader import METHOD, FieldResult, ReadResult
from app.reader.store import REASON_SUFFIX, REVIEW_RULE
from app.reports.ingest import read_reports_csv
from app.usl.client import insert_extraction, insert_flag, select
from app.usl.model import PG_SOURCE, table_fqn
from app.usl.sqltext import sql_string

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _rows(result: Any) -> list[dict[str, Any]]:
    columns = [column.lower() for column in result.columns]
    rows = []
    for row in result.rows:
        if isinstance(row, dict):
            rows.append({str(key).lower(): value for key, value in row.items()})
        else:
            rows.append(dict(zip(columns, row, strict=False)))
    return rows


async def load_evidence(case_id: str) -> CaseEvidence:
    rows = _rows(
        await select(
            "SELECT recorded_n, lymph_nodes_positive, edition_code FROM "
            f"{table_fqn('stage_check')} WHERE case_id = {sql_string(case_id)}",
            limit=1,
        )
    )
    if not rows:
        raise LookupError(f"{case_id}: not in stage_check")
    report = read_reports_csv().get(case_id)
    if report is None:
        raise LookupError(f"{case_id}: no report text")
    return CaseEvidence(
        case_id=case_id,
        report_text=report.report_text,
        recorded_n=rows[0].get("recorded_n"),
        registry_count=_number(rows[0].get("lymph_nodes_positive")),
        scan_text=scan_text(case_id),
        edition=rows[0].get("edition_code"),
    )


def scan_text(case_id: str) -> str | None:
    from app.scans.scans import SCANS_DIR, join_pages

    cache = SCANS_DIR / case_id / "blocks.json"
    if not cache.exists():
        return None
    text, _refs = join_pages(json.loads(cache.read_text(encoding="utf-8"))["pages"])
    return text


async def existing_fields(case_id: str) -> dict[str, str]:
    rows = _rows(
        await select(
            f"SELECT field, value FROM {PG_SOURCE}.derived_extraction "
            f"WHERE case_id = {sql_string(case_id)} AND method = {sql_string(METHOD)}",
            limit=50,
        )
    )
    return {str(r["field"]): str(r.get("value")) for r in rows}


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


async def _store_field(name: str, fr: FieldResult, result: ReadResult, stamp: str) -> None:
    assert fr.span is not None
    await insert_extraction(
        case_id=result.case_id,
        method=METHOD,
        field=name,
        value=fr.value,
        quote=fr.quote,
        quote_start=fr.span.start,
        quote_end=fr.span.end,
        model=result.model,
        receipt_id=result.receipt_id,
        created_at=stamp,
    )
    if fr.reason and name != "NPOS":
        await insert_extraction(
            case_id=result.case_id,
            method=METHOD,
            field=f"{name}{REASON_SUFFIX}",
            value=fr.reason[:250],
            model=result.model,
            receipt_id=result.receipt_id,
            created_at=stamp,
            requires=(name, stamp),
        )


async def store_ladder(ladder: Ladder) -> dict[str, str]:
    """Store a completed ladder's outcome; returns field -> outcome. Never stores partial runs."""
    if ladder.run.status != "completed":
        return {name: f"not-stored: run {ladder.run.status}" for name in ladder.closed}
    earlier = await existing_fields(ladder.case_id)
    stamp = _stamp()
    outcome: dict[str, str] = {}
    for name, info in ladder.closed.items():
        fr, result = ladder.closings[name]
        if info["rung"] == R3:
            outcome[name] = "scan-not-stored"
        elif name in earlier:
            outcome[name] = f"kept-earlier: {earlier[name]}"
        elif fr.span is None:
            outcome[name] = "not-stored: no span"
        else:
            await _store_field(name, fr, result, stamp)
            outcome[name] = "stored"
    for name in ladder.open_fields:
        reason = ladder.last_reasons.get(name) or "ladder exhausted"
        await insert_flag(
            flag_id=f"{ladder.case_id}:{name}:{REVIEW_RULE}:ladder",
            case_id=ladder.case_id,
            rule_id=REVIEW_RULE,
            field=name,
            reason=f"ladder: {reason}"[:300],
            severity="review",
            created_at=stamp,
        )
        outcome[name] = "flagged"
    return outcome


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def budget_honoured(chunk: dict[str, Any]) -> bool | None:
    """Thinking OFF must show no reasoning tokens; a budget must not be exceeded.

    NVIDIA direct reports reasoning tokens; Nightshift's usage does not, so there the check
    is on completion tokens: at most the budget plus the answer allowance (app/web/trace.py).
    """
    from app.web.trace import ANSWER_ALLOWANCE

    usage = chunk.get("usage") or {}
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if chunk.get("budget") is None:
        return None
    budget = int(chunk["budget"])
    if reasoning is not None:
        return reasoning == 0 if budget == 0 else reasoning <= budget
    completion = usage.get("completion_tokens")
    if not isinstance(completion, int):
        return None
    return completion <= max(budget, 0) + ANSWER_ALLOWANCE


def write_trace(ladder: Ladder, run_id: str, outcome: dict[str, str] | None) -> None:
    record = dict(ladder.run.record)
    _append(
        LOG_DIR / "markovian-runs.jsonl",
        {
            "run_id": run_id,
            "case": ladder.case_id,
            "logged_at": _stamp(),
            "stored": outcome is not None,
            "outcome": outcome,
            "engine": "meterless-markovian@4eb96f2",
            "status": record.get("status"),
            "error": record.get("error"),  # why an errored run stopped (the provider's message)
            "chunks": len(record.get("chunks") or []),
            "cascade_levels": ladder.run.levels,
            "closed": ladder.closed,
            "open": ladder.open_fields,
            "conflicts": ladder.conflicts,
            "chunkConfig": record.get("chunkConfig"),
            "tokenLabel": record.get("tokenLabel"),
            "engine_totalTokensUsed": record.get("totalTokensUsed"),
            "engine_totalTokensSaved": record.get("totalTokensSaved"),
            "measured_completion_tokens": sum(
                int((c.get("usage") or {}).get("completion_tokens") or 0) for c in ladder.chunks
            ),
        },
    )
    for chunk in ladder.chunks:
        _append(
            LOG_DIR / "markovian-chunks.jsonl",
            {"run_id": run_id, "budget_honoured": budget_honoured(chunk), **chunk},
        )


async def run_case(
    case_id: str, *, store: bool, provider: str = LADDER_PROVIDER
) -> tuple[Ladder, dict[str, str] | None]:
    evidence = await load_evidence(case_id)
    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    ladder = await climb(evidence, run_id=run_id, provider=provider)
    outcome = await store_ladder(ladder) if store else None
    write_trace(ladder, run_id, outcome)
    return ladder, outcome


def summary(ladder: Ladder, outcome: dict[str, str] | None = None) -> str:
    lines = [f"{ladder.case_id}: engine status {ladder.run.status}, {len(ladder.chunks)} rung(s)"]
    for chunk in ladder.chunks:
        usage = chunk.get("usage") or {}
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        lines.append(
            f"  {chunk.get('rung')}: budget {chunk.get('budget')}, {chunk.get('seconds')} s, "
            f"{usage.get('completion_tokens')} completion tokens"
            + (f" ({reasoning} reasoning)" if reasoning else "")
            + f", open after: {chunk.get('outgoing_need')}"
        )
    lines.append(f"  closed: {ladder.closed}")
    if ladder.conflicts:
        lines.append(f"  conflicts (demoted to a person): {ladder.conflicts}")
    lines.append(f"  open (a person decides): {ladder.open_fields}")
    if outcome is not None:
        lines.append(f"  stored outcome: {outcome}")
    return "\n".join(lines) + "\n"
