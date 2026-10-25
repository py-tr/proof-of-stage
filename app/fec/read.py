"""FEC read level: does the scanned filing say which database field is wrong?

Pre-registered in docs/preregistration/fec-read.md (the sample, the rules and this code frozen in
fec-read.json before the first model call). Twelve 2018 Senate paper filings whose database
record breaks cash at beginning + receipts - disbursements = cash at close by $2 or more
(app/fec/guard.py) are drawn with a fixed seed. For each, NVIDIA's hosted Nemotron Parse v1
(app/providers/nvidia.parse_page, the shipped scan reader) reads pages 3-6 (1-based) of the filed
PDF; the detailed summary page is found by text; the amounts on lines 23, 24, 26 and 27 are taken
from the Parse text by the frozen rules below, and each must pass guard.check_value against that
page's text. No other model is called: the extraction is deterministic code.

Downloads are untrusted data: one new folder per filing under data/fec/pdf/<filing_id>/ (not
committed), opened only by pypdfium2 to render page images; nothing in them is executed.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.fec.guard import FIELDS, RECORD_COLUMNS, check_value, classify, identity_gap, money

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "fec-read.json"
RAW = ROOT / "data" / "fec" / "raw"
PDF_DIR = ROOT / "data" / "fec" / "pdf"
LOG = ROOT / "logs" / "fec-read.jsonl"
RUNS_LOG = ROOT / "logs" / "fec-read-runs.jsonl"
FROZEN_FILES = ("app/fec/read.py", "app/fec/guard.py")

CYCLE = "2018"
SEED = 20261025
SAMPLE_SIZE = 12
MIN_GAP = Decimal("2.00")
PAGES_1_BASED = (3, 4, 5, 6)  # Parse reads these pages only; never extended
STOP_DOWNLOAD_FAILURES = 4  # more than this: stop
VOID_PAGE_FAILURES = 4  # more than this: void
FIELD_TOLERANCE = Decimal("1.00")  # a document value differs from the record by $1 or more
CLAIM_READ = 5
CLAIM_ONE_FIELD = 3
# Filings opened in the 2026-10-24 spike (beginning image numbers). All were consistent records,
# so none can be in the eligible set; listed so the exclusion is checkable.
SPIKE_IMAGES = (
    "201901310300261891",
    "201910220300299955",
    "201902190300267510",
    "201902140300267352",
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0 Safari/537.36"
)
MAX_PDF_BYTES = 80_000_000
CANVAS = (1024, 1280)  # as app/scans/scans.py: centred on white, grayscale, JPEG quality 60

VERDICT_CONTRADICTS = "the filing contradicts the record on {field}"
VERDICT_NOT_ADD_UP = "the filing itself does not add up"
VERDICT_MATCHES = "record matches filing"
VERDICT_OTHER = "other"
VERDICT_NOT_READ = "not read"

# --- the frozen text rules -------------------------------------------------------------------

_W = r"\s*"
BEGIN_PHRASE = re.compile(r"cash\s*on\s*hand\s*at\s*(?:the\s*)?beginning", re.I)
CLOSE_PHRASE = re.compile(r"cash\s*on\s*hand\s*at\s*(?:the\s*)?close", re.I)
PHRASES = {
    "beginning": BEGIN_PHRASE,
    "receipts": re.compile(r"total\s*receipts\s*this\s*period", re.I),
    "disbursements": re.compile(r"total\s*disbursements\s*this\s*period", re.I),
    "close": CLOSE_PHRASE,
}
LINE_NUMBERS = {"beginning": "23", "receipts": "24", "disbursements": "26", "close": "27"}
# A line that starts with the field's line number followed by words ("26. TOTAL ...").
_NUMBERED = {
    f: re.compile(rf"^[\s|*#>\-]*{n}(?:\s*[.)])?\s+(?=[A-Za-z])") for f, n in LINE_NUMBERS.items()
}
# Where another cash-summary line starts inside a merged line: cut the remainder there.
_NEXT_LABEL = re.compile(
    r"\b2[3-7]\b\s*[.)]?\s+[A-Za-z]|cash\s*on\s*hand|total\s*(?:receipts|disbursements)|subtotal",
    re.I,
)
_PARENS = re.compile(r"\([^()]*[A-Za-z][^()]*\)")
_REFS = re.compile(r"\b(?:lines?|page|from|and|add|subtract)\s*\d+[a-z]?(?:\([a-z]\))?", re.I)
_AMOUNT = re.compile(r"\(?\$?\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?\)?")
_LINE_BREAK = re.compile(r"\n|\\\\|</tr>", re.I)


@dataclass
class Line:
    start: int  # offsets into the page text
    end: int

    def text(self, page: str) -> str:
        return page[self.start : self.end]


def page_text(blocks: list[dict[str, Any]]) -> str:
    """Parse's blocks in Parse's order, joined by newlines: the document the guard checks."""
    return "\n".join(str(b.get("text", "")) for b in blocks)


def lines_of(page: str) -> list[Line]:
    """Split at newlines, LaTeX row ends (\\\\) and </tr>; empty lines dropped."""
    out, cursor = [], 0
    for match in _LINE_BREAK.finditer(page):
        if page[cursor : match.start()].strip():
            out.append(Line(cursor, match.start()))
        cursor = match.end()
    if page[cursor:].strip():
        out.append(Line(cursor, len(page)))
    return out


def find_summary_page(pages: dict[int, str]) -> int | None:
    """The first page (lowest number) whose text carries both "cash on hand at beginning" and
    "cash on hand at close"; None if no page in the range does."""
    for number in sorted(pages):
        text = pages[number]
        if BEGIN_PHRASE.search(text) and CLOSE_PHRASE.search(text):
            return number
    return None


def _label_end(field: str, line: str) -> int | None:
    """End of the field's label in the line (phrase first, else a leading line number)."""
    phrase = PHRASES[field].search(line)
    if phrase:
        return phrase.end()
    numbered = _NUMBERED[field].search(line)
    return numbered.end() if numbered else None


def _clean(text: str) -> str:
    """Parenthesised text and "Line 16" style references blanked out (offsets kept)."""
    text = _PARENS.sub(lambda m: " " * len(m.group(0)), text)
    return _REFS.sub(lambda m: " " * len(m.group(0)), text)


def _amount_in(rest: str) -> re.Match[str] | None:
    """The last amount in the cleaned text after the label, cut where another cash-summary
    line's label starts (a match at the very start does not count)."""
    blank = _clean(rest)
    cut = next((m.start() for m in _NEXT_LABEL.finditer(blank) if m.start() > 0), len(blank))
    found = [m for m in _AMOUNT.finditer(blank[:cut]) if re.search(r"\d", m.group(0))]
    return found[-1] if found else None


def extract_line(field: str, page: str) -> tuple[str, str] | None:
    """(amount text, quote) for one field from the summary page's Parse text, or None.

    Candidates are the lines carrying the field's label, in page order. For each: the amount is
    the last amount after the label (see _amount_in); if the label line has none, the next line
    is tried, unless it carries another line's label. The first candidate that yields an amount
    wins. The quote runs from the start of the label line to the end of the amount, verbatim.
    """
    lines = lines_of(page)
    for index, line in enumerate(lines):
        text = line.text(page)
        end = _label_end(field, text)
        if end is None:
            continue
        found = _amount_in(text[end:])
        if found:
            stop = line.start + end + found.end()
            return found.group(0).strip(), page[line.start : stop]
        if index + 1 < len(lines):
            following = lines[index + 1]
            nxt = following.text(page)
            if _NEXT_LABEL.search(_clean(nxt)):
                continue
            found = _amount_in(nxt)
            if found:
                return found.group(0).strip(), page[line.start : following.start + found.end()]
    return None


def read_fields(page: str) -> dict[str, Any]:
    """Each field's extracted amount and quote, checked by the guard against the page text."""
    out: dict[str, Any] = {}
    for field in FIELDS:
        got = extract_line(field, page)
        if got is None:
            out[field] = {"status": "rejected", "reason": "no_line_found"}
            continue
        amount, quote = got
        check = check_value(field, amount, quote, page)
        out[field] = {
            "status": check.status,
            "reason": check.reason,
            "value": None if check.value is None else str(check.value),
            "amount_text": amount,
            "quote": quote,
        }
    return out


def filing_verdict(record: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    """The frozen verdict, in this order: not read (a field not accepted); record matches filing
    (every field within $1 of the record); the filing itself does not add up (document gap of $2
    or more); the filing contradicts the record on <field> (exactly one field differs by $1 or
    more); other (more than one differs)."""
    if any(fields.get(f, {}).get("status") != "accepted" for f in FIELDS):
        return {"verdict": VERDICT_NOT_READ, "read_cleanly": False}
    doc = {f: Decimal(fields[f]["value"]) for f in FIELDS}
    gap = doc["beginning"] + doc["receipts"] - doc["disbursements"] - doc["close"]
    differ = [
        f for f in FIELDS if abs(doc[f] - money(record.get(RECORD_COLUMNS[f]))) >= FIELD_TOLERANCE
    ]
    base = {"read_cleanly": True, "document_gap": str(gap), "differing_fields": differ}
    if not differ:
        return {**base, "verdict": VERDICT_MATCHES}
    if abs(gap) >= MIN_GAP:
        return {**base, "verdict": VERDICT_NOT_ADD_UP}
    if len(differ) == 1:
        return {**base, "verdict": VERDICT_CONTRADICTS.format(field=differ[0]), "field": differ[0]}
    return {**base, "verdict": VERDICT_OTHER}


def summarise(rows: list[dict[str, Any]], page_failures: int) -> dict[str, Any]:
    verdicts = [r["verdict"] for r in rows]
    read = sum(r.get("read_cleanly", False) for r in rows)
    one_field = sum(v.startswith("the filing contradicts the record on") for v in verdicts)
    void = page_failures > VOID_PAGE_FAILURES
    return {
        "filings": len(rows),
        "read_cleanly": read,
        "name_one_field": one_field,
        "verdicts": {v: verdicts.count(v) for v in sorted(set(verdicts))},
        "parse_page_failures": page_failures,
        "void": void,
        "pattern_transfers_at_read_level": (
            not void and read >= CLAIM_READ and one_field >= CLAIM_ONE_FIELD
        ),
    }


# --- the sample ------------------------------------------------------------------------------


def load_records(cycle: str = CYCLE) -> list[dict[str, Any]]:
    """The pulled reports with duplicate rows dropped, exactly as scripts/fec_counts.py does."""
    rows, seen = [], set()
    for path in sorted(RAW.glob(f"cycle-{cycle}-page-*.json")):
        for r in json.loads(path.read_text(encoding="utf-8"))["results"]:
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
    return rows


def eligible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paper, impossible by $2 or more, a PDF, the most recent version (is_amended false), not a
    spike filing; sorted by file number, then beginning image number."""
    out = []
    for r in rows:
        gap = identity_gap(r)
        if (
            r.get("means_filed") == "paper"
            and classify(gap) == "impossible"
            and abs(gap) >= MIN_GAP
            and r.get("pdf_url")
            and not r.get("is_amended")
            and str(r.get("beginning_image_number")) not in SPIKE_IMAGES
        ):
            out.append(r)
    return sorted(out, key=lambda r: (int(r["file_number"]), str(r["beginning_image_number"])))


def draw(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return random.Random(SEED).sample(eligible(rows), SAMPLE_SIZE)


def filing_id(record: dict[str, Any]) -> str:
    value = str(record["file_number"])
    if not value.isdigit():
        raise ValueError("file_number is not numeric")
    return value


def download_pdf(fid: str, url: str) -> dict[str, Any]:
    """Fetch one filing PDF into its own new folder (data only). Returns the outcome."""
    import httpx

    folder = PDF_DIR / fid
    target = folder / "filing.pdf"
    if target.exists() and target.read_bytes()[:4] == b"%PDF":
        body = target.read_bytes()
        return {"status": "ok", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    if not url.startswith("https://docquery.fec.gov/"):
        return {"status": "failed", "reason": "not_a_docquery_url"}
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"},
            timeout=180,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        return {"status": "failed", "reason": type(exc).__name__}
    body = response.content
    if response.status_code != 200:
        return {"status": "failed", "reason": f"http_{response.status_code}"}
    if body[:4] != b"%PDF":
        return {"status": "failed", "reason": "not_a_pdf"}
    if len(body) > MAX_PDF_BYTES:
        return {"status": "failed", "reason": "too_large"}
    target.write_bytes(body)
    return {"status": "ok", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def page_count(fid: str) -> int:
    import pypdfium2 as pdfium

    return len(pdfium.PdfDocument(str(PDF_DIR / fid / "filing.pdf")))


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    """Draw the sample, download the PDFs (no model), write fec-read.json. Refuses after a run."""
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    rows = load_records()
    pool = eligible(rows)
    sample = []
    for r in draw(rows):
        fid = filing_id(r)
        outcome = download_pdf(fid, str(r["pdf_url"]))
        if outcome["status"] == "ok":
            outcome["pages"] = page_count(fid)
        sample.append(
            {
                "filing_id": fid,
                "committee_id": r.get("committee_id"),
                "committee_name": r.get("committee_name"),
                "report": f"{r.get('report_type')} {str(r.get('coverage_end_date'))[:10]}",
                "amendment_indicator": r.get("amendment_indicator"),
                "beginning_image_number": str(r.get("beginning_image_number")),
                "pdf_url": r["pdf_url"],
                "record": {f: str(money(r.get(RECORD_COLUMNS[f]))) for f in FIELDS},
                "record_gap": str(identity_gap(r)),
                "download": outcome,
            }
        )
    failures = sum(s["download"]["status"] != "ok" for s in sample)
    old = json.loads(PREREG.read_text(encoding="utf-8")) if PREREG.exists() else {}
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "population": {
            "reports_after_dedup": len(rows),
            "eligible": len(pool),
            "eligible_rule": (
                "means_filed == paper; guard.classify == impossible; |record gap| >= $2; "
                "pdf_url present; is_amended false (most recent version); beginning image "
                "number not a spike filing; sorted by (file_number, beginning_image_number)"
            ),
            "spike_images_excluded": list(SPIKE_IMAGES),
            "spike_images_among_all_records": [
                {"image": str(r.get("beginning_image_number")), "class": classify(identity_gap(r))}
                for r in rows
                if str(r.get("beginning_image_number")) in SPIKE_IMAGES
            ],
        },
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "pages_1_based": list(PAGES_1_BASED),
        "models": {"parse": "nvidia/nemotron-parse (v1, NVIDIA hosted)", "other": "none"},
        "download_failures": failures,
        "stop": failures > STOP_DOWNLOAD_FAILURES,
        "sample": sample,
        "claim": (
            f"'the pattern transfers at the read level' only if >= {CLAIM_READ} of "
            f"{SAMPLE_SIZE} read cleanly AND >= {CLAIM_ONE_FIELD} name exactly one field"
        ),
        "prediction": old.get("prediction", prediction),
    }
    PREREG.parent.mkdir(parents=True, exist_ok=True)
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


# --- the run ---------------------------------------------------------------------------------


def _page_jpeg(doc: Any, index: int) -> bytes:
    from PIL import Image

    page = doc[index]
    width, height = page.get_size()
    scale = min(CANVAS[0] / width, CANVAS[1] / height)
    image = page.render(scale=scale).to_pil().convert("L")
    canvas = Image.new("L", CANVAS, 255)
    canvas.paste(image, ((CANVAS[0] - image.width) // 2, (CANVAS[1] - image.height) // 2))
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=60)
    return buffer.getvalue()


async def _read_filing(item: dict[str, Any], budget: dict[str, int]) -> dict[str, Any]:
    import pypdfium2 as pdfium

    from app.providers import nvidia

    fid = item["filing_id"]
    row: dict[str, Any] = {"filing_id": fid, "record_gap": item["record_gap"]}
    pdf = PDF_DIR / fid / "filing.pdf"
    if item["download"]["status"] != "ok" or not pdf.exists():
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "download_failed"}
    body = pdf.read_bytes()
    if hashlib.sha256(body).hexdigest() != item["download"]["sha256"]:
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "pdf_changed_since_freeze"}
    doc = pdfium.PdfDocument(str(pdf))
    pages: dict[int, str] = {}
    blocks_by_page: dict[str, Any] = {}
    row["parse"] = []
    for number in PAGES_1_BASED:
        if number > len(doc):
            row["parse"].append({"page": number, "status": "absent"})
            continue
        if budget["failures"] > VOID_PAGE_FAILURES:
            row["parse"].append({"page": number, "status": "skipped_void"})
            continue
        try:
            blocks, served = await nvidia.parse_page(_page_jpeg(doc, number - 1))
        except Exception as exc:  # one attempt per page (the client's own retries only)
            budget["failures"] += 1
            row["parse"].append({"page": number, "status": "failed", "error": type(exc).__name__})
            continue
        if not blocks:
            budget["failures"] += 1
            row["parse"].append({"page": number, "status": "failed", "error": "no_blocks"})
            continue
        pages[number] = page_text(blocks)
        blocks_by_page[str(number)] = blocks
        row["parse"].append(
            {"page": number, "status": "ok", "blocks": len(blocks), "model": served}
        )
    (PDF_DIR / fid / "parse.json").write_text(json.dumps(blocks_by_page), encoding="utf-8")
    row["page_texts"] = {str(k): v for k, v in pages.items()}
    summary = find_summary_page(pages)
    row["summary_page"] = summary
    if summary is None:
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "summary_page_not_in_pages_3_6"}
    row["fields"] = read_fields(pages[summary])
    record = {RECORD_COLUMNS[f]: item["record"][f] for f in FIELDS}
    return {**row, **filing_verdict(record, row["fields"])}


async def run_fec_read() -> dict[str, Any]:
    record = frozen()
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    if record["stop"]:
        raise RuntimeError("more than 4 PDF downloads failed: stopped")
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction into fec-read.json before the run")
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    budget = {"failures": 0}
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for item in record["sample"]:
        row = {"run": tag, **(await _read_filing(item, budget))}
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows, budget["failures"])}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
