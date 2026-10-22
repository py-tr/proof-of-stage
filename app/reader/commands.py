"""CLI actions: fetch the report corpus, and read cases with Nemotron."""

from __future__ import annotations

import sys

from app.reader.reader import Provider, ReadResult, read_report
from app.reader.store import store_result
from app.reports.ingest import (
    download_corpus,
    iter_corpus,
    read_reports_csv,
    select_reports,
    write_reports_csv,
)
from app.usl.client import invalid_records, select
from app.usl.model import table_fqn


async def audited_case_ids() -> set[str]:
    result = await select(f"SELECT case_id FROM {table_fqn('tumour_case')}", limit=5000)
    return {str(row[0]).upper() for row in result.rows if row and row[0]}


async def fetch_reports() -> str:
    case_ids = await audited_case_ids()
    path = download_corpus()
    reports = select_reports(iter_corpus(path), case_ids)
    out = write_reports_csv(reports)
    return (
        f"reports: {len(reports)} of {len(case_ids)} audited cases have report text "
        f"-> {out.name} (run `usl setup` to load it into Zetaris)\n"
    )


async def _cases_for_rule(rule: str, limit: int) -> list[str]:
    result = await invalid_records(rule, limit=limit)
    index = result.columns.index("case_id") if "case_id" in result.columns else 0
    return [str(row[index]).upper() for row in result.rows if row]


def _format(result: ReadResult) -> str:
    lines = [f"{result.case_id}  model={result.model}  receipt={result.receipt_id or '-'}"]
    for name, fr in result.fields.items():
        where = f"[{fr.span.start}:{fr.span.end}]" if fr.span else ""
        quote = (fr.quote or "").replace("\n", " ")[:120]
        lines.append(
            f"  {name}: {fr.status:<9} {fr.value or '-':<7} {fr.reason:<22} {where} {quote}"
        )
    return "\n".join(lines)


async def read_cases(
    *,
    case_ids: list[str] | None,
    rule: str | None,
    limit: int,
    provider: Provider,
    store: bool,
) -> int:
    reports = read_reports_csv()
    if not reports:
        sys.stdout.write("no report text: run `python -m app.cli reports fetch` first\n")
        return 2
    targets = [c.upper() for c in case_ids] if case_ids else []
    if rule:
        targets += await _cases_for_rule(rule, limit=max(limit, 1) * 4)
    targets = list(dict.fromkeys(targets))[:limit]
    missing = [c for c in targets if c not in reports]
    totals = {"read": 0, "accepted": 0, "rejected": 0, "abstained": 0, "no_report": len(missing)}
    for case_id in targets:
        if case_id not in reports:
            continue
        try:
            result = await read_report(case_id, reports[case_id].report_text, provider=provider)
        except Exception as exc:  # one failed case must not stop the batch
            totals["errors"] = totals.get("errors", 0) + 1
            sys.stdout.write(f"{case_id}  ERROR {type(exc).__name__}: {str(exc)[:160]}\n")
            continue
        totals["read"] += 1
        for fr in result.fields.values():
            totals[fr.status] += 1
        if store:  # store first: a display failure must not lose a finished read
            await store_result(result)
        sys.stdout.write(_format(result) + "\n")
    summary = "  ".join(f"{k}={v}" for k, v in totals.items())
    sys.stdout.write(
        f"summary: {summary}" + ("" if store else "  (dry run: nothing written)") + "\n"
    )
    return 0
