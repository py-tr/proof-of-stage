"""FEC v2: Super VL reads the handwritten cash summary; the FEC database is the second reader.

Pre-registered in docs/preregistration/fec-read-vl.md (sample, rules and code hashes frozen in
fec-read-vl.json before the first call). Designed after FEC v1 (docs/evidence/fec-read-results.md),
where text extraction misread handwritten amounts, and a spike on three v1 pages (design cases,
disclosed). Per filing: Nemotron Parse finds the Detailed Summary Page among pages 3-6 (the v1
rule, reused unchanged from app/fec/read.py); Super VL (NVIDIA direct: Nightshift 1.2.3 refuses
pinned image requests) reads lines 23-27 from that page image; each of lines 23, 24, 26, 27 is
compared with the value the FEC typed into its database from the same paper form. A line the two
readers agree on (to the cent) is confirmed; a line they disagree on goes to a person (a typing
error in the database or a misread, never decided by code). Nothing is stored in Zetaris.
"""

from __future__ import annotations

import base64
import io
import json
import random
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import sha16
from app.fec import read as v1
from app.providers import nvidia
from app.reader.reader import parse_answer, thinking_args

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "fec-read-vl.json"
LOG = ROOT / "logs" / "fec-read-vl.jsonl"
RUNS_LOG = ROOT / "logs" / "fec-read-vl-runs.jsonl"
FROZEN_FILES = ("app/fec/read_vl.py", "app/fec/read.py")
SEED = 20261026
SAMPLE_SIZE = 24
PAGES = (3, 4, 5, 6)  # 1-based, as v1
BUDGET = 4000
VOID_FAILURES = 6
CLAIM_READ = 16
CLAIM_AGREE_SHARE = Decimal("0.80")
LINES = {"23": "beginning", "24": "receipts", "26": "disbursements", "27": "close"}
PROMPT = (
    "This is the Detailed Summary Page of a US campaign finance report (FEC Form 3). "
    "Read the handwritten or typed amounts in section III, CASH SUMMARY, exactly as written in "
    "the boxes, digit by digit: line 23 (cash on hand at beginning), line 24 (total receipts), "
    "line 25 (subtotal), line 26 (total disbursements), line 27 (cash on hand at close). Do not "
    "correct or compute anything: if a box is crossed out or unclear, say so. "
    'Return ONLY JSON: {"23": "...", "24": "...", "25": "...", "26": "...", "27": "...", '
    '"notes": "..."} with amounts like 1234.56.'
)
OUTCOME_AGREE = "both readers agree on all four lines"
OUTCOME_ONE = "the readers disagree on line {line}: a person decides"
OUTCOME_MANY = "the readers disagree on {n} lines: unsettled"
OUTCOME_NOT_READ = "not read"


def money(value: Any) -> Decimal | None:
    text = str(value or "").replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        return Decimal(text.split()[0]).quantize(Decimal("0.01"))
    except (InvalidOperation, IndexError):
        return None


def compare(reading: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Per line: agree / disagree / unread; the outcome; the document gap from confirmed lines."""
    lines: dict[str, str] = {}
    for line, field in LINES.items():
        read, typed = money(reading.get(line)), money(record.get(field))
        if read is None:
            lines[line] = "unread"
        else:
            lines[line] = "agree" if typed is not None and read == typed else "disagree"
    disagree = [ln for ln, s in lines.items() if s != "agree"]
    if not disagree:
        outcome = OUTCOME_AGREE
    elif len(disagree) == 1:
        outcome = OUTCOME_ONE.format(line=disagree[0])
    else:
        outcome = OUTCOME_MANY.format(n=len(disagree))
    gap = None
    vals = [money(reading.get(ln)) for ln in ("23", "24", "26", "27")]
    if all(v is not None for v in vals):
        b, r, d, c = vals
        gap = str(b + r - d - c)
    return {"lines": lines, "outcome": outcome, "document_gap": gap}


def draw_sample(rows: list[dict[str, Any]], exclude: set[str]) -> list[dict[str, Any]]:
    # v1's eligible list, in v1's order (sorted by file number and first image), minus v1's sample
    # rows with a negative file number (FEC internal ids, no public filing number) are left out
    pool = [
        r
        for r in v1.eligible(rows)
        if str(r.get("file_number")).isdigit() and str(r.get("file_number")) not in exclude
    ]
    return random.Random(SEED).sample(pool, min(SAMPLE_SIZE, len(pool)))


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
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


def _vl_jpeg(doc: Any, index: int) -> str:
    img = doc[index].render(scale=1.6).to_pil().convert("L")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


async def read_filing(item: dict[str, Any]) -> dict[str, Any]:
    import pypdfium2 as pdfium

    fid = item["filing_id"]
    row: dict[str, Any] = {"filing_id": fid, "record": item["record"]}
    doc = pdfium.PdfDocument(str(v1.PDF_DIR / fid / "filing.pdf"))
    texts: dict[int, str] = {}
    for page in PAGES:
        if page > len(doc):
            break
        blocks, _ = await nvidia.parse_page(v1._page_jpeg(doc, page - 1))
        texts[page] = v1.page_text(blocks)
    summary = v1.find_summary_page(texts)
    row["summary_page"] = summary
    if summary is None:
        return {**row, "outcome": OUTCOME_NOT_READ, "reason": "summary page not in pages 3-6"}
    extra, max_tokens = thinking_args(BUDGET)
    content = [
        {"type": "text", "text": PROMPT},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + _vl_jpeg(doc, summary - 1)},
        },
    ]
    started = time.monotonic()
    text, served, usage = await nvidia.chat_with_usage(
        [{"role": "user", "content": content}], config.NV_SUPER, max_tokens=max_tokens, **extra
    )
    row.update(
        {
            "seconds": round(time.monotonic() - started, 1),
            "served": served,
            "completion_tokens": (usage or {}).get("completion_tokens"),
            "raw": text[:2000],
        }
    )
    reading = parse_answer(text) or {}
    row["reading"] = {k: reading.get(k) for k in ("23", "24", "25", "26", "27", "notes")}
    if not any(money(reading.get(ln)) is not None for ln in LINES):
        return {**row, "outcome": OUTCOME_NOT_READ, "reason": "no amounts in the answer"}
    return {**row, **compare(reading, item["record"])}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = sum("error" in r for r in rows)
    read = [r for r in rows if "lines" in r]
    states = [s for r in read for s in r["lines"].values()]
    agree = states.count("agree")
    share = Decimal(agree) / Decimal(len(states)) if states else Decimal(0)
    all_agree = [r for r in read if r["outcome"] == OUTCOME_AGREE]
    return {
        "filings": len(rows),
        "failures": failures,
        "void": failures > VOID_FAILURES,
        "read": len(read),
        "lines_read": len(states),
        "lines_agree": agree,
        "agree_share": str(share.quantize(Decimal("0.001"))),
        "all_four_agree": len(all_agree),
        "all_four_agree_and_filing_does_not_add_up": sum(
            1 for r in all_agree if r.get("document_gap") and abs(Decimal(r["document_gap"])) >= 2
        ),
        "one_line_disagrees": [
            {"filing": r["filing_id"], "outcome": r["outcome"]}
            for r in read
            if r["outcome"].startswith("the readers disagree on line")
        ],
        "claim_met": failures <= VOID_FAILURES
        and len(read) >= CLAIM_READ
        and share >= CLAIM_AGREE_SHARE,
    }


async def run_fec_read_vl() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for item in record["sample"]:
        try:
            row = await read_filing(item)
        except Exception as exc:  # a failure: recorded, never re-run
            row = {
                "filing_id": item["filing_id"],
                "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                "outcome": OUTCOME_NOT_READ,
            }
        row["run"] = tag
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, default=str) + "\n")
    return summary


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    """Draw the fresh sample (v1's filings and the spike pages excluded), download, write json."""
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    rows = v1.load_records()
    v1_ids = {s["filing_id"] for s in json.loads(v1.PREREG.read_text(encoding="utf-8"))["sample"]}
    sample = []
    for r in draw_sample(rows, v1_ids):
        fid = v1.filing_id(r)
        outcome = v1.download_pdf(fid, str(r["pdf_url"]))
        if outcome["status"] == "ok":
            outcome["pages"] = v1.page_count(fid)
        sample.append(
            {
                "filing_id": fid,
                "committee_name": r.get("committee_name"),
                "report": f"{r.get('report_type')} {str(r.get('coverage_end_date'))[:10]}",
                "pdf_url": r["pdf_url"],
                "record": {f: str(v1.money(r.get(v1.RECORD_COLUMNS[f]))) for f in v1.FIELDS},
                "record_gap": str(v1.identity_gap(r)),
                "download": outcome,
            }
        )
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "prompt_sha256_16": sha16(PROMPT),
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "excluded": {
            "v1_sample": sorted(v1_ids),
            "design_pages": ["1202879", "1231036", "1227521"],
        },
        "pages_1_based": list(PAGES),
        "models": {
            "page_finding": "nvidia/nemotron-parse (v1, NVIDIA direct), the v1 rule",
            "reading": f"{config.NV_SUPER} (NVIDIA direct; Nightshift 1.2.3 refuses pinned image "
            f"requests), 4k thinking budget, one call per filing",
        },
        "download_failures": sum(s["download"]["status"] != "ok" for s in sample),
        "sample": sample,
        "claim": (
            f"'Super VL reads the handwritten cash summary' only if >= {CLAIM_READ} of "
            f"{SAMPLE_SIZE} filings are read and Super VL agrees with the FEC database on >= 80% "
            "of the lines it read"
        ),
        "void": f"more than {VOID_FAILURES} filings fail at the provider",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record
