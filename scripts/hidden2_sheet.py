"""The builder's lay-read sheet for the hidden-errors census 2 (read-only; never committed).

For each hit in logs/hidden-2.jsonl: the registry value, the reading, the accepted quote, and the
report's lines that mention lymph nodes or the N stage (from the local report corpus). Writes
.notes/hidden-2-lay-read-sheet.md, which holds report text and is git-ignored; the verdicts the
builder gives go into docs/evidence/hidden-2-lay-reads.json (case -> {"read": "stands" | "falls"
| "unsure", "note": ...}) for scripts/hidden2_writeup.py.

    python scripts/hidden2_sheet.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.reports.ingest import read_reports_csv  # noqa: E402

LOG = ROOT / "logs" / "hidden-2.jsonl"
OUT = ROOT / ".notes" / "hidden-2-lay-read-sheet.md"
CUE = re.compile(r"lymph|node|\bpN|N stage|N category|axilla|sentinel|metasta", re.IGNORECASE)
FIELD = {"N": "N category", "NPOS": "positive-node count"}


def excerpt(report: str, quote: str) -> list[str]:
    lines = [x.strip() for x in report.splitlines() if x.strip()]
    if len(lines) < 4:  # one long line: split on sentences instead
        lines = [x.strip() for x in re.split(r"(?<=[.;])\s+", report) if x.strip()]
    keep = [x for x in lines if CUE.search(x) or (quote and quote[:30] in x)]
    return keep[:25]


def main() -> int:
    rows = [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    hits = [r for r in rows if r.get("contradicts_registry")]
    reports = read_reports_csv()
    out = [
        "# Hidden-errors census 2: your lay reads (private, never committed)",
        "",
        f"{len(rows)} records read so far, {len(hits)} hits. For each hit, read the lines and say "
        "whether the report really gives the reading's value (stands), gives the registry's "
        "value (falls), or does not settle it (unsure). Watch for counts per level or per "
        "specimen that are not the total.",
        "",
    ]
    for i, r in enumerate(hits, 1):
        report = reports.get(r["case"])
        text = report.report_text if report else ""
        out.append(f"## {i}. {r['case']}")
        for field, c in r["contradicts_registry"].items():
            out += [
                f"- **{FIELD.get(field, field)}**: registry **{c['registry']}**, "
                f"reading **{c['report']}** (step {c['rung']})",
                f"- accepted quote: “{c['quote']}”",
            ]
        out += ["", "Report lines about nodes:", ""]
        out += [f"> {x}" for x in excerpt(text, "")] or ["> (no report text on this machine)"]
        out += ["", "**Your read:** stands / falls / unsure · note:", ""]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(hits)} hits of {len(rows)} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
