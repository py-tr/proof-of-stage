"""Fetch the public TCGA-Reports corpus and keep the reports of the audited cases.

Source: TCGA-Reports (Kefeli & Tatonetti, Patterns 2024), machine-readable text of
TCGA pathology reports, MIT licence: github.com/tatonetti-lab/tcga-path-reports.
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.usl.model import REPORT_COLUMNS, REPORTS_CSV, ROOT

CORPUS_URL = "https://github.com/tatonetti-lab/tcga-path-reports/raw/main/TCGA_Reports.csv.zip"
CORPUS_ZIP = ROOT / "data" / "private" / "TCGA_Reports.csv.zip"
_CASE_ID_LEN = 12  # e.g. TCGA-A2-A0CV


@dataclass(frozen=True)
class Report:
    report_id: str
    case_id: str
    report_text: str


def case_id_of(patient_filename: str) -> str:
    """TCGA-XX-XXXX.<uuid> -> TCGA-XX-XXXX."""
    return patient_filename.strip()[:_CASE_ID_LEN].upper()


def download_corpus(path: Path = CORPUS_ZIP, url: str = CORPUS_URL) -> Path:
    """Download the corpus zip once; reuse the cached copy afterwards."""
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        tmp = path.with_suffix(".part")
        with tmp.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    tmp.replace(path)
    return path


def iter_corpus(path: Path) -> Iterator[tuple[str, str]]:
    """Yield (patient_filename, text) rows from the corpus zip."""
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with zipfile.ZipFile(path) as archive:
        name = next(
            n for n in archive.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")
        )
        with archive.open(name) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))
            for row in reader:
                yield row.get("patient_filename") or "", row.get("text") or ""


def select_reports(rows: Iterable[tuple[str, str]], case_ids: set[str]) -> list[Report]:
    """Keep one report per wanted case (the first one; reports with no text are skipped)."""
    wanted = {c.upper() for c in case_ids}
    chosen: dict[str, Report] = {}
    for filename, text in rows:
        case_id = case_id_of(filename)
        if case_id not in wanted or case_id in chosen or not text.strip():
            continue
        chosen[case_id] = Report(report_id=filename.strip(), case_id=case_id, report_text=text)
    return [chosen[c] for c in sorted(chosen)]


def write_reports_csv(reports: list[Report], path: Path = REPORTS_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(REPORT_COLUMNS)
        for report in reports:
            writer.writerow([report.report_id, report.case_id, report.report_text])
    return path


def read_reports_csv(path: Path = REPORTS_CSV) -> dict[str, Report]:
    """case_id -> Report from the local path_reports.csv."""
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    out: dict[str, Report] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = (row.get("case_id") or "").upper()
            if case_id:
                out[case_id] = Report(
                    report_id=row.get("report_id") or "",
                    case_id=case_id,
                    report_text=row.get("report_text") or "",
                )
    return out
