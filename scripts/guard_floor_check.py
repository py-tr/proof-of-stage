"""Re-judge every stored node count under the current guard, replay the red-team attack, and
measure the report floor against the registry's own counts (docs/evidence/guard-floor.md).

Needs the live USL (.env) and the local report corpus. Run: python scripts/guard_floor_check.py
"""

from __future__ import annotations

import asyncio
from collections import Counter

from app.engine.run_case import _rows, scan_text
from app.reader.reader import NODES_POSITIVE, judge_count, report_floor
from app.reports.ingest import read_reports_csv
from app.usl.client import select
from app.usl.model import table_fqn

ATTACK_CASE = "TCGA-A2-A0CV"
ATTACK = {"N_positive": 1, "N_positive_quote": "ONE (1) SENTINEL LYMPH NODE (SPECIMEN A): POSITIVE"}


async def main() -> None:
    reports = read_reports_csv()
    stored = _rows(
        await select(
            f"SELECT case_id, value, quote FROM {table_fqn('derived_stage')} "
            f"WHERE field = '{NODES_POSITIVE}' AND method = 'nemotron_reader'",
            limit=1000,
        )
    )
    verdicts = Counter()
    print("stored counts, re-judged:")
    for row in stored:
        report = reports[row["case_id"]].report_text
        fr = judge_count({"N_positive": row["value"], "N_positive_quote": row["quote"]}, report)
        verdicts[fr.status] += 1
        floor = report_floor(report)
        print(f"  {row['case_id']} {row['value']}: {fr.status} {fr.reason} floor={floor}")
    print(f"  -> {dict(verdicts)}")

    fr = judge_count(ATTACK, scan_text(ATTACK_CASE) or "")
    print(f"attack ({ATTACK_CASE} scan, N=1 from one specimen): {fr.status} {fr.reason}")

    registry = _rows(
        await select(
            f"SELECT case_id, lymph_nodes_positive FROM {table_fqn('stage_check')}", limit=5000
        )
    )
    tally, below = Counter(), []
    for row in registry:
        report, count = reports.get(row["case_id"]), row.get("lymph_nodes_positive")
        if report is None or count in (None, ""):
            tally["no report or no count"] += 1
            continue
        floor = report_floor(report.report_text)
        if floor is None:
            tally["report states no node fraction"] += 1
        elif int(float(count)) >= floor:
            tally["registry count at or above the floor"] += 1
        else:
            tally["registry count below the floor"] += 1
            below.append(row["case_id"])
    print(f"registry vs report floor: {dict(tally)}")
    print("below the floor:", " ".join(sorted(below)))


if __name__ == "__main__":
    asyncio.run(main())
