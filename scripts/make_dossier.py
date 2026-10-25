"""Generate the discrepancy dossier for the NCI GDC help desk (prepared, NOT sent).

Read-only: the live layer (stage_check, derived_extraction), the frozen blind labels and the
attestation log. A record is included only if it has a stored, guard-checked quote AND the blind
human label (one lay labeller, the builder) agrees with the product's verdict; records the label
disputes (TCGA-BH-A0BS, TCGA-E2-A1LI) are left out on purpose and listed as such. Plus the hidden
error TCGA-A2-A25D (lay read by the builder). Writes docs/dossier/discrepancy-report.md and .csv.

    python scripts/make_dossier.py
"""

import asyncio
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.usl.client import select  # noqa: E402
from app.usl.model import table_fqn  # noqa: E402

OUT = ROOT / "docs" / "dossier"
LABELS = ROOT / "docs" / "preregistration" / "ground-truth-labels.json"
SCORES = ROOT / "logs" / "label-scores.json"
ATTEST = ROOT / "logs" / "attest.jsonl"
FIELD_WORDS = {"node_count": "positive lymph node count", "pathologic_n": "N stage (N category)"}
A25D = {
    "case_id": "TCGA-A2-A25D",
    "field": "positive lymph node count",
    "registry": "22 positive nodes",
    "report": 'final diagnosis: "TWENTY-THREE (23) LYMPH NODES POSITIVE FOR METASTATIC. CARCINOMA '
    '(SEE PARTS "B" AND "C")"; Part B 1 positive, Part C 22 of 23 positive',
    "why": "the registry records Part C's 22 and appears to miss Part B's 1; both 22 and 23 give "
    "the same N stage, so a stage rule cannot see it",
    "found_by": "docs/evidence/hidden-errors-results.md (lay read by the builder, 2026-10-24)",
}


def _n(value: object) -> str:
    text = str(value)
    return text[:-2] if text.endswith(".0") else text


async def main() -> None:
    scores = json.loads(SCORES.read_text(encoding="utf-8"))["baseline_all"]["per_case"]
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    attest = [json.loads(x) for x in ATTEST.read_text(encoding="utf-8").splitlines() if x]
    agree = sorted(c for c, v in scores.items() if v["A0"] == v["label"])
    disputed = sorted(c for c, v in scores.items() if v["A0"] != v["label"])
    ids = ", ".join(f"'{c}'" for c in agree)
    checks = (
        await select(
            "SELECT case_id, recorded_n, lymph_nodes_positive, lymph_nodes_tested, derived_n, "
            f"report_n, report_nodes_positive, fault_field FROM {table_fqn('stage_check')} "
            f"WHERE case_id IN ({ids})",
            limit=100,
        )
    ).rows
    quotes = (
        await select(
            "SELECT case_id, field, value, quote FROM oa_pg.derived_extraction "
            f"WHERE method = 'nemotron_reader' AND field IN ('N', 'NPOS') AND case_id IN ({ids})",
            limit=200,
        )
    ).rows
    by_case: dict[str, list] = {}
    for case_id, field, value, quote in quotes:
        by_case.setdefault(case_id, []).append((field, value, quote))
    receipts = {(a["case"], a["field"]): a.get("receipt_id") for a in attest}
    rows = []
    for c in checks:
        case_id, rec_n, count, tested, derived, rep_n, rep_count, fault = c
        named = fault in FIELD_WORDS
        rows.append(
            {
                "case_id": case_id,
                "status": "possible discrepancy for your review"
                if named
                else "the report does not settle it",
                "field": FIELD_WORDS.get(fault, "-"),
                "registry": f"N {rec_n}; {_n(count)} positive of {_n(tested)} examined",
                "count_rule_gives": derived,
                "report_reads": f"N {rep_n or '-'}; {rep_count or '-'} positive",
                "report_quotes": " | ".join(
                    f'{f}: "{(q or "").strip()}"' for f, _, q in by_case.get(case_id, [])
                ),
                "signed_re_read_receipts": " ".join(
                    r for r in (receipts.get((case_id, f)) for f in ("N", "NPOS")) if r
                ),
                "blind_label_note": (labels.get(case_id) or {}).get("note", ""),
            }
        )
    rows.sort(key=lambda r: (r["status"] != "possible discrepancy for your review", r["case_id"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "discrepancy-report.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    named = [r for r in rows if r["status"].startswith("possible")]
    lines = [
        "# Possible discrepancies in TCGA-BRCA clinical data (prepared, NOT sent)",
        "",
        "> Draft for the NCI GDC help desk, to be sent by the project author after the hackathon "
        "judging, under their own name. Nothing here has been confirmed by GDC or by a pathologist.",
        "",
        "Project TCGA-BRCA (GDC clinical data, 1,097 cases). Each record below has a recorded N "
        "stage and positive-node count that cannot both be true under the AJCC count ranges "
        "(paraphrased: N0 none, N1 1-3, N2 4-9, N3 10 or more), a sentence in the public "
        "pathology report that settles which field it contradicts (checked word for word by "
        "code), a signed re-read that reproduced it (2026-10-25), and a blind read by one lay "
        "reader that agrees. The "
        f"{len(disputed)} labelled records where the lay read differs from our reading "
        f"({', '.join(disputed)}) are left out on purpose (two of them, TCGA-AN-A0XN and "
        "TCGA-AN-A0XW, are labelling mis-clicks the reader later confirmed; still left out).",
        "",
        f"## {len(named)} records where the report contradicts one field",
        "",
    ]
    for r in named:
        lines += [
            f"### {r['case_id']}: the {r['field']}",
            f"- Registry: {r['registry']} (the count rule gives {r['count_rule_gives']})",
            f"- Report: {r['report_reads']}; {r['report_quotes']}",
            f"- Signed re-read receipts: {r['signed_re_read_receipts'] or '-'}",
            "",
        ]
    lines += [
        f"## {len(rows) - len(named)} records the report does not settle (listed for completeness)",
        "",
    ]
    lines += [
        f"- {r['case_id']}: registry {r['registry']}; report {r['report_reads']}"
        for r in rows
        if not r["status"].startswith("possible")
    ]
    lines += [
        "",
        "## One record that passes every rule",
        "",
        f"### {A25D['case_id']}: the {A25D['field']}",
        f"- Registry: {A25D['registry']}",
        f"- Report: {A25D['report']}",
        f"- Why: {A25D['why']}",
        f"- Source: {A25D['found_by']}",
        "",
        "Method and evidence: https://github.com/py-tr/proof-of-stage (README, docs/evidence/).",
    ]
    (OUT / "discrepancy-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"{len(named)} named, {len(rows) - len(named)} unsettled, + A2-A25D; disputed left out: {disputed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
