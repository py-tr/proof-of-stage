"""A second cancer type: the impossible colorectal records (TCGA-COAD, TCGA-READ), read once.

Pre-registered in docs/preregistration/colon-read.md (the case list, the colon count rule, the
prompt and code hashes frozen in colon-read.json before the first call). The registry values
come from the public GDC API (the same fields the breast layer onboards), the report text from
the same TCGA report corpus. A record is impossible when its recorded N and positive-node count
cannot both be true under the paraphrased colon count rule (N0 none; N1 1-3; N2 4 or more;
N1c means tumour deposits with no positive node, so N1c with 0 is not impossible). Each such
record is read once by Super VL through Nightshift (4k budget, signed, envelope kept) with a
colorectal version of the reader's prompt; the reader's own guard (judge_field, judge_count,
imported unchanged) checks every quote; a verdict names the field the report contradicts or
leaves it to a person. Nothing is written to the breast layer.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import sha16
from app.providers import envelope_tap, nightshift
from app.reader.reader import NODES_POSITIVE, judge_count, judge_field, parse_answer, thinking_args

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "colon-read.json"
LOG = ROOT / "logs" / "colon-read.jsonl"
RUNS_LOG = ROOT / "logs" / "colon-read-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "colon-read-envelopes.jsonl"
PROJECTS = ("TCGA-COAD", "TCGA-READ")
GDC_FIELDS = (
    "submitter_id,diagnoses.ajcc_pathologic_n,diagnoses.ajcc_staging_system_edition,"
    "diagnoses.pathology_details.lymph_nodes_positive,diagnoses.pathology_details.lymph_nodes_tested"
)
BUDGET = 4000
VOID_FAILURES = 3
FROZEN_FILES = ("app/engine/colon_read.py",)
PROMPT = (
    "You read one colorectal cancer pathology report and report the PATHOLOGIC T and N "
    "categories (AJCC), as the report supports them.\n"
    "Return ONLY a JSON object with these keys:\n"
    '{"T": "...", "T_quote": "...", "T_reason": "...", '
    '"N": "...", "N_quote": "...", "N_reason": "...", '
    '"N_positive": 0, "N_positive_quote": "..."}\n'
    "Rules:\n"
    "- T is one of TX, T0, Tis, T1, T2, T3, T4a, T4b, T4; "
    "N is one of NX, N0, N1a, N1b, N1c, N1, N2a, N2b, N2.\n"
    "- T_quote / N_quote: ONE contiguous passage copied character-for-character from the "
    "report: the shortest passage that supports your category, at least a few words "
    "(not a bare code like 'pNx'). No ellipsis, no paraphrase, no joining of separate passages.\n"
    "- T_reason / N_reason: one short sentence on which rule you applied.\n"
    "- N_positive: the total number of positive regional lymph nodes as an integer; "
    "N_positive_quote: the passage that states it (it must contain that number). "
    "Use null with an empty quote if the report does not state a count.\n"
    '- If the report does not support a category, use "UNKNOWN" with an empty quote. '
    "Never guess."
)
_MAIN = re.compile(r"N(X|[0-3])")


def main_n(value: str | None) -> str | None:
    match = _MAIN.search((value or "").upper())
    return match.group(0) if match else None


def colon_rule(count: int | float | None) -> str | None:
    """Paraphrased colon count rule: the main N for a positive-node count."""
    if count is None:
        return None
    c = int(count)
    return "N0" if c == 0 else ("N1" if c <= 3 else "N2")


def impossible(recorded_n: str | None, count: int | float | None) -> bool:
    main = main_n(recorded_n)
    if main in (None, "NX") or count is None:
        return False
    if (recorded_n or "").upper().replace(" ", "").endswith("N1C") and int(count) == 0:
        return False  # tumour deposits without a positive node: a valid N1c
    return colon_rule(count) != main


def verdict(recorded_n: str, count: float, read_n: Any, read_count: Any) -> str:
    """Which registry field the accepted reading contradicts, by the colon rule."""
    n_ok, c_ok = read_n is not None, read_count is not None
    if (
        c_ok
        and int(float(read_count)) != int(count)
        and colon_rule(float(read_count)) == main_n(recorded_n)
    ):
        return "the report contradicts the count"
    if (
        n_ok
        and main_n(str(read_n)) != main_n(recorded_n)
        and main_n(str(read_n)) == colon_rule(count)
    ):
        return "the report contradicts the stage field"
    return "a person decides"


CORPUS = ROOT / "data" / "private" / "TCGA_Reports.csv.zip"


def corpus_reports(case_ids: set[str] | None = None) -> dict[str, str]:
    """case id -> report text from the full TCGA report corpus (all cancer types)."""
    import csv
    import io
    import zipfile

    csv.field_size_limit(10**8)
    archive = zipfile.ZipFile(CORPUS)
    name = next(n for n in archive.namelist() if n.endswith(".csv"))
    out: dict[str, str] = {}
    with archive.open(name) as raw:
        for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")):
            case = (row.get("patient_filename") or "")[:12].upper()
            if case_ids is None or case in case_ids:
                out[case] = row.get("text") or ""
    return out


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        p
        for p, d in record["code_sha256_16"].items()
        if sha16((ROOT / p).read_text(encoding="utf-8")) != d
    ]
    if sha16(PROMPT) != record["prompt_sha256_16"]:
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


def gdc_cases() -> list[dict[str, Any]]:
    import httpx

    out = []
    for project in PROJECTS:
        filt = json.dumps(
            {"op": "in", "content": {"field": "project.project_id", "value": [project]}}
        )
        r = httpx.get(
            "https://api.gdc.cancer.gov/cases",
            params={"filters": filt, "fields": GDC_FIELDS, "size": "2000", "format": "json"},
            timeout=120,
        )
        r.raise_for_status()
        for hit in r.json()["data"]["hits"]:
            for d in hit.get("diagnoses") or []:
                details = d.get("pathology_details") or []
                pos = next(
                    (
                        p.get("lymph_nodes_positive")
                        for p in details
                        if p.get("lymph_nodes_positive") is not None
                    ),
                    None,
                )
                tested = next(
                    (
                        p.get("lymph_nodes_tested")
                        for p in details
                        if p.get("lymph_nodes_tested") is not None
                    ),
                    None,
                )
                if d.get("ajcc_pathologic_n") and pos is not None:
                    out.append(
                        {
                            "case_id": hit["submitter_id"],
                            "project": project,
                            "recorded_n": d.get("ajcc_pathologic_n"),
                            "count": pos,
                            "tested": tested,
                            "edition": d.get("ajcc_staging_system_edition"),
                        }
                    )
                    break
    return out


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    cases = gdc_cases()
    reports = corpus_reports({c["case_id"] for c in cases})
    flagged = [c for c in cases if impossible(c["recorded_n"], c["count"])]
    with_report = sorted(
        (c for c in flagged if c["case_id"] in reports), key=lambda c: c["case_id"]
    )
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "prompt_sha256_16": sha16(PROMPT),
        "source": "GDC API /cases for TCGA-COAD and TCGA-READ, fetched at freeze time",
        "population": {
            "cases_with_n_and_count": len(cases),
            "impossible": len(flagged),
            "impossible_with_report": len(with_report),
        },
        "cases": with_report,
        "claim": "the report names the contradicted field (verified quote) on >= half read",
        "void": f"more than {VOID_FAILURES} provider failures",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


async def read_case(case: dict[str, Any], report: str, item_id: str) -> dict[str, Any]:
    extra, max_tokens = thinking_args(BUDGET)
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:32000]},
    ]
    text, receipt = await nightshift.chat(
        messages,
        config.NS_SUPER_VL,
        item_id=item_id,
        require_model=config.NS_SUPER_VL,
        retry_on_mismatch=True,
        require_signature=True,
        pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
        allow_cache=False,
        max_tokens=max_tokens,
        **extra,
    )
    answer = parse_answer(text) or {}
    n = judge_field("N", answer, report)
    k = judge_count(answer, report)
    read_n = n.value if n.status == "accepted" else None
    read_k = k.value if k.status == "accepted" else None
    return {
        "receipt_id": receipt.receipt_id,
        "signature": receipt.signature,
        "N": {"status": n.status, "value": n.value, "quote": n.quote, "reason": n.reason[:80]},
        NODES_POSITIVE: {
            "status": k.status,
            "value": k.value,
            "quote": k.quote,
            "reason": k.reason[:80],
        },
        "verdict": verdict(case["recorded_n"], case["count"], read_n, read_k),
    }


async def run_colon_read() -> dict[str, Any]:
    record = frozen()
    reports = corpus_reports({c["case_id"] for c in record["cases"]})
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for case in record["cases"]:
        row: dict[str, Any] = {"case": case["case_id"], "run": tag, "registry": case}
        item = f"colon-{tag}-{case['case_id']}-{uuid.uuid4().hex[:6]}"
        started = time.monotonic()
        with envelope_tap.capture() as calls:
            try:
                row.update(await read_case(case, reports[case["case_id"]], item))
            except Exception as exc:  # a provider failure: logged, never re-run
                row["provider_failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                row["verdict"] = "not read"
        row["seconds"] = round(time.monotonic() - started, 1)
        for c in calls:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"case": case["case_id"], "run": tag, **c}, sort_keys=True) + "\n"
                )
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    named = sum(r.get("verdict", "").startswith("the report contradicts") for r in rows)
    read = sum("provider_failure" not in r for r in rows)
    failures = len(rows) - read
    summary = {
        "run": tag,
        "cases": len(rows),
        "read": read,
        "failures": failures,
        "void": failures > VOID_FAILURES,
        "named_a_field": named,
        "verdicts": {
            v: sum(r.get("verdict") == v for r in rows) for v in {r.get("verdict") for r in rows}
        },
        "claim_met": failures <= VOID_FAILURES and read > 0 and named * 2 >= read,
    }
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, default=str) + "\n")
    return summary
