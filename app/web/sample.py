"""Build the bundled SAMPLE_MODE cases from the live USL and the report corpus.

Only registry facts and report text are kept. Every column that comes from a model
(report_t, report_n, report_n_main, report_nodes_positive, fault_field) is blanked, so
sample mode can never replay a model answer: the visitor plays the reader instead.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.reports.ingest import CORPUS_URL, read_reports_csv
from app.web.data import SAMPLE_FILE, LiveData

MODEL_COLUMNS = ("report_t", "report_n", "report_n_main", "report_nodes_positive", "fault_field")
DEFAULT_CASES = ("TCGA-E2-A572", "TCGA-A2-A0CV", "TCGA-AN-A0XO", "TCGA-A7-A26E", "TCGA-3C-AAAU")
SOURCE_NOTE = (
    "Registry facts: NCI Genomic Data Commons (TCGA-BRCA), open access. Report text: "
    f"TCGA-Reports (Kefeli et al.), MIT licence, {CORPUS_URL}. Research data, not for "
    "clinical use. No model outputs are stored here."
)


async def build_sample(case_ids: tuple[str, ...] = DEFAULT_CASES, out: Path = SAMPLE_FILE) -> Path:
    reports = read_reports_csv()
    live = LiveData()
    cases = []
    for case_id in case_ids:
        found = await live.case(case_id)
        if found is None or case_id not in reports:
            raise ValueError(f"{case_id}: no stage_check row or no report text")
        check = {
            key: (None if key in MODEL_COLUMNS else value) for key, value in found["check"].items()
        }
        cases.append({"check": check, "report_text": reports[case_id].report_text})
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": SOURCE_NOTE, "cases": cases}
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
