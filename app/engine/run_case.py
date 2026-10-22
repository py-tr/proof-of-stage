"""`python -m app.cli run --case X [--store]`: one case through the RUNGS ladder, with a trace.

Evidence: the registry row from the Zetaris USL (stage_check), the report text, and Nemotron
Parse's reading of the original scan when it has been parsed (data/scans/<case>/blocks.json).
Every run appends its engine record to logs/markovian-runs.jsonl and one row per rung to
logs/markovian-chunks.jsonl. With --store, each closed field is appended to Zetaris
(method nemotron_reader for the text rungs, nemotron_reader_scan for the scan rung).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.rungs import R3, CaseEvidence, Ladder, climb
from app.reader.reader import METHOD, FieldResult, ReadResult
from app.reader.store import REASON_SUFFIX
from app.reports.ingest import read_reports_csv
from app.usl.client import insert_extraction, select
from app.usl.model import table_fqn
from app.usl.sqltext import sql_string

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
SCAN_METHOD = "nemotron_reader_scan"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


async def load_evidence(case_id: str) -> CaseEvidence:
    rows = await select(
        "SELECT recorded_n, lymph_nodes_positive, edition_code FROM "
        f"{table_fqn('stage_check')} WHERE case_id = {sql_string(case_id)}",
        limit=1,
    )
    if not rows.rows:
        raise LookupError(f"{case_id}: not in stage_check")
    recorded_n, count, edition = rows.rows[0][0], rows.rows[0][1], rows.rows[0][2]
    report = read_reports_csv().get(case_id)
    if report is None:
        raise LookupError(f"{case_id}: no report text")
    return CaseEvidence(
        case_id=case_id,
        report_text=report.report_text,
        recorded_n=recorded_n,
        registry_count=_number(count),
        scan_text=scan_text(case_id),
        edition=edition,
    )


def scan_text(case_id: str) -> str | None:
    from app.scans.scans import SCANS_DIR, join_pages

    cache = SCANS_DIR / case_id / "blocks.json"
    if not cache.exists():
        return None
    text, _refs = join_pages(json.loads(cache.read_text(encoding="utf-8"))["pages"])
    return text


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


async def store_closed(name: str, rung: str, fr: FieldResult, result: ReadResult) -> None:
    """Append one closed field (and the model's reason) to Zetaris; first write wins."""
    if fr.span is None:
        return
    stamp = _stamp()
    method = SCAN_METHOD if rung == R3 else METHOD
    model = f"{result.model} budget={result.budget} rung={rung}"
    await insert_extraction(
        case_id=result.case_id,
        method=method,
        field=name,
        value=fr.value,
        quote=fr.quote,
        quote_start=fr.span.start,
        quote_end=fr.span.end,
        model=model,
        receipt_id=result.receipt_id,
        created_at=stamp,
    )
    if fr.reason and name != "NPOS":
        await insert_extraction(
            case_id=result.case_id,
            method=method,
            field=f"{name}{REASON_SUFFIX}",
            value=fr.reason[:250],
            model=model,
            receipt_id=result.receipt_id,
            created_at=stamp,
            requires=(name, stamp),
        )


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_trace(ladder: Ladder, run_id: str, stored: bool) -> None:
    record = dict(ladder.run.record)
    _append(
        LOG_DIR / "markovian-runs.jsonl",
        {
            "run_id": run_id,
            "case": ladder.case_id,
            "logged_at": _stamp(),
            "stored": stored,
            "engine": "meterless-markovian@4eb96f2",
            "status": record.get("status"),
            "chunks": len(record.get("chunks") or []),
            "cascade_levels": ladder.run.levels,
            "closed": ladder.closed,
            "open": ladder.open_fields,
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
        _append(LOG_DIR / "markovian-chunks.jsonl", {"run_id": run_id, **chunk})


async def run_case(case_id: str, *, store: bool) -> Ladder:
    evidence = await load_evidence(case_id)
    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    ladder = await climb(evidence, run_id=run_id, on_close=store_closed if store else None)
    write_trace(ladder, run_id, stored=store)
    return ladder


def summary(ladder: Ladder) -> str:
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
    lines.append(f"  open (a person decides): {ladder.open_fields}")
    return "\n".join(lines) + "\n"
