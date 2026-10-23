"""Judge the same fresh reads with the previous and the current guard (no storing).

Reads every review-queue report once (Super, NVIDIA direct, thinking off) and prints, per
case and field (count, N, T), the value, its quote and both verdicts. Usage:
python scripts/guard_ab.py <path to the previous reader.py> > logs/guard-ab-<date>.txt
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys

from app.reader.reader import THINKING_OFF, judge_count, judge_field, read_report
from app.reports.ingest import read_reports_csv

QUEUE = (
    "3C-AAAU A1-A0SN A2-A0CV A7-A26E A7-A26H AC-A2FK AN-A0XN AN-A0XO AN-A0XP AN-A0XS AN-A0XT "
    "AN-A0XW AO-A1KP AQ-A1H2 BH-A0BS BH-A0DD E2-A1B4 E2-A572 E9-A3X8 EW-A424 A2-A0EW AO-A03P "
    "AR-A1AT D8-A27L E2-A1LI"
).split()


async def main(old_path: str) -> None:
    spec = importlib.util.spec_from_file_location("reader_old", old_path)
    old = importlib.util.module_from_spec(spec)
    sys.modules["reader_old"] = old
    spec.loader.exec_module(old)
    reports = read_reports_csv()
    for short in QUEUE:
        case_id = f"TCGA-{short}"
        report = reports[case_id].report_text
        try:
            result = await read_report(case_id, report, budget=THINKING_OFF)
        except Exception as exc:
            print(f"{case_id}\tERROR {type(exc).__name__}")
            continue
        answer = old.parse_answer(result.raw_text) or {}
        for field in ("NPOS", "N", "T"):
            if field == "NPOS":
                before, after = old.judge_count(answer, report), judge_count(answer, report)
                value, quote = answer.get("N_positive"), answer.get("N_positive_quote")
            else:
                before = old.judge_field(field, answer, report)
                after = judge_field(field, answer, report)
                value, quote = answer.get(field), answer.get(f"{field}_quote")
            quote = " ".join(str(quote or "").split())[:120]
            same = (before.status, before.reason) == (after.status, after.reason)
            print(
                f"{case_id}\t{field}\t{value}\told={before.status}:{before.reason}"
                f"\tnew={after.status}:{after.reason}\t{'' if same else 'CHANGED'}\t{quote}"
            )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
