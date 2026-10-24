"""Count the FEC cash-identity results over the pulled reports (no model call).

Reads data/fec/raw/cycle-<cycle>-page-*.json (from scripts/fec_pull.py), drops duplicate rows,
classifies each report with app.fec.guard (consistent / cents_only / impossible / incomplete),
splits by how it was filed, and prints the table as JSON. Usage: python scripts/fec_counts.py 2018
"""

from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

from app.fec.guard import classify, identity_gap

ROOT = Path(__file__).resolve().parents[1]


def main(cycle: str) -> None:
    rows, seen = [], set()
    for path in sorted(
        glob.glob(str(ROOT / "data" / "fec" / "raw" / f"cycle-{cycle}-page-*.json"))
    ):
        for r in json.loads(Path(path).read_text(encoding="utf-8"))["results"]:
            key = (
                r.get("committee_id"),
                r.get("beginning_image_number"),
                r.get("file_number"),
                r.get("report_type"),
                r.get("coverage_end_date"),
            )
            if key not in seen:
                seen.add(key)
                rows.append(r)
    table = Counter(f"{r.get('means_filed')}:{classify(identity_gap(r))}" for r in rows)
    impossible = [r for r in rows if classify(identity_gap(r)) == "impossible"]
    gaps = sorted((abs(identity_gap(r)) for r in impossible), reverse=True)
    out = {
        "cycle": cycle,
        "reports": len(rows),
        "by_filing_and_class": dict(sorted(table.items())),
        "impossible": len(impossible),
        "impossible_amended": sum(bool(r.get("is_amended")) for r in impossible),
        "impossible_with_pdf": sum(bool(r.get("pdf_url")) for r in impossible),
        "largest_gaps": [f"{g:,.2f}" for g in gaps[:10]],
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2018")
