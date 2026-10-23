"""Write docs/evidence/nightshift-provenance.md: do the latest signed runs read the stored values?

The 10 records are the ones `usl demo` step 12 lists (the N column and the count column disagree
on "node-positive?"). For each stored report value (stage_check.report_n / report_nodes_positive,
first write kept) the file shows the latest ladder run's closing for that field, its rung, its
model and receipt id, and whether the two match. Reads Zetaris and the local chunk log only; no
model call. Usage: python scripts/provenance_ten.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.engine.run_case import _rows
from app.usl.client import select
from app.usl.demo import _BOTH_APPLY, _DISAGREE
from app.usl.model import table_fqn
from app.web.trace import latest_trace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "nightshift-provenance.md"


def _same(name: str, stored: str, latest: str | None) -> bool:
    if latest is None:
        return False
    if name == "NPOS":
        return float(stored) == float(latest)
    return stored.strip().upper() == latest.strip().upper()


async def main() -> None:
    rows = _rows(
        await select(
            "SELECT case_id, report_n, report_nodes_positive FROM "
            f"{table_fqn('stage_check')} WHERE {_BOTH_APPLY} AND {_DISAGREE} ORDER BY case_id",
            limit=100,
        )
    )
    lines, fields, matches, rungs, signed = [], 0, 0, 0, 0
    for row in rows:
        trace = latest_trace(row["case_id"]) or {"run_id": None, "rungs": [], "closed": {}}
        by_rung = {r["rung"]: r for r in trace["rungs"]}
        rungs += len(trace["rungs"])
        signed += sum(
            r["provider"] == "nightshift" and r["signature"] == "verified" for r in trace["rungs"]
        )
        for name, stored in (("N", row["report_n"]), ("NPOS", row["report_nodes_positive"])):
            if stored in (None, ""):
                continue
            closed = trace["closed"].get(name) or {}
            rung = by_rung.get(closed.get("rung"), {})
            ok = _same(name, str(stored), closed.get("value"))
            fields += 1
            matches += ok
            lines.append(
                f"| {row['case_id']} | {'count' if name == 'NPOS' else 'N'} | {stored} | "
                f"{closed.get('value') or 'not closed'} | {closed.get('rung') or '-'} | "
                f"{rung.get('model') or '-'} | {rung.get('receipt_id') or '-'} | "
                f"{rung.get('signature') or '-'} | {'yes' if ok else 'no'} |"
            )
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    text = (
        "# Do the latest signed runs still read the stored values? (the 10 disagreeing records)\n\n"
        f"Generated {stamp} by `python scripts/provenance_ten.py` from the live Zetaris layer and "
        "`logs/markovian-chunks.jsonl` (no model call). The records are the 10 that `usl demo` "
        "step 12 lists. Stored values are the first ones written (append-only), from earlier "
        "NVIDIA-direct runs; the latest ladder runs go through Nightshift with signed receipts.\n\n"
        f"**{matches} of {fields}** stored report values are reproduced by the latest run; "
        f"those runs have {rungs} rungs, {signed} of them signed Nightshift receipts verified "
        "against the pinned key.\n\n"
        "| Case | Field | Stored | Latest run | Rung | Model | Receipt | Signature | Match |\n"
        "|---|---|---|---|---|---|---|---|---|\n" + "\n".join(lines) + "\n"
    )
    OUT.write_text(text, encoding="utf-8")
    print(f"{matches} of {fields} match; {signed} of {rungs} rungs signed -> {OUT.name}")


if __name__ == "__main__":
    asyncio.run(main())
