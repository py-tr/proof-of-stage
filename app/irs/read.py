"""IRS 990-EZ read level: does the filed return say which database field is wrong?

Pre-registered in docs/preregistration/irs-read.md (the sample, the rules, the prompt and this code
frozen in irs-read.json before the first model call). Sixteen paper-filed 990-EZ records from the
IRS SOI 2016 extract whose database values break line 9 (total revenue) - line 17 (total expenses)
= line 18 (excess or deficit) by $2 or more are drawn with a fixed seed. For each, the return's
PDF (Candid's 990 archive) is opened, the text layer of page 1 is taken as the document, and
Nemotron Super VL through Nightshift (text only, pinned, signed receipt, no cache, envelope kept)
returns lines 9, 17 and 18, each with a verbatim quote. Code accepts a line only when the quote is
in the page text (app.reader.quotes.locate) and the amount is inside the quote.

Downloads are untrusted data: one new folder per file under data/irs/ (not committed), the
extract read in-process with zipfile and the PDFs opened only by pypdfium2; nothing in them is
executed and nothing is imported from those folders.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import re
import time
import uuid
import zipfile
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.reader.quotes import locate

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "irs-read.json"
DATA = ROOT / "data" / "irs"
EXTRACT_DIR = DATA / "extract-2016"
EXTRACT_ZIP = EXTRACT_DIR / "16eofinextractez.zip"
EXTRACT_URL = "https://www.irs.gov/pub/irs-soi/16eofinextractez.zip"
PDF_DIR = DATA / "pdf"
LOG = ROOT / "logs" / "irs-read.jsonl"
RUNS_LOG = ROOT / "logs" / "irs-read-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "irs-read-envelopes.jsonl"
FROZEN_FILES = ("app/irs/read.py", "app/reader/quotes.py")

SEED = 20261025
SAMPLE_SIZE = 16
MIN_GAP = Decimal("2")  # database |9 - 17 - 18| for eligibility; return gap for "does not add up"
FIELD_TOLERANCE = Decimal("1")  # a return value differs from the database by $1 or more
ADDS_UP = Decimal("1")  # the return's own |9 - 17 - 18| <= $1 counts as adding up
MIN_TEXT_CHARS = 500  # page-1 text layer shorter than this: not read (no OCR fallback)
STOP_MISSING = 6  # more than this many of 16 without a document: stop, no run
VOID_FAILURES = 4  # more than this many provider failures: void
CLAIM_READ = 8
CLAIM_CONTRADICTS = 3
BUDGET = 4000
# Returns opened before this design (the main session's verified example and the scout's PDFs);
# excluded by (EIN, tax period) so the draw cannot pick a filing someone has already read.
DESIGN_CASES = (
    ("352517049", "201506"),
    ("061762420", "201507"),
    ("311741739", "201506"),
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0 Safari/537.36"
)
MAX_BYTES = 80_000_000
PDF_URL = "https://990s.foundationcenter.org/990_pdf_archive/{a}/{ein}/{ein}_{period}_990EZ.pdf"

LINES = ("9", "17", "18")
COLUMNS = {"9": "totrevnue", "17": "totexpns", "18": "totexcessyr"}
FIELD_NAMES = {"9": "total revenue", "17": "total expenses", "18": "excess or deficit"}
# Gating (added before the first call): the quote must carry the line's printed label or its
# printed instruction, so a right amount quoted from a wrong line is not accepted.
LABELS = {
    "9": re.compile(r"total\s*revenue|add\s*lines\s*1(?!\d)", re.I),
    "17": re.compile(r"total\s*expenses|add\s*lines\s*10\s*thro?u?\s*g?\s*h?\s*16", re.I),
    "18": re.compile(r"excess\s*or\s*\(?\s*deficit|subtract\s*line\s*17", re.I),
}

VERDICT_CONTRADICTS = "the record contradicts the return on {field}"
VERDICT_NOT_ADD_UP = "the return itself does not add up"
VERDICT_MATCHES = "record matches return"
VERDICT_OTHER = "other"
VERDICT_NOT_READ = "not read"

PROMPT = (
    "You read page 1 of a US Form 990-EZ (Return of Organization Exempt From Income Tax). You get "
    "the page's text layer, which may contain recognition errors and dropped decimal points. "
    "Find Part I line 9 (Total revenue), line 17 (Total expenses) and line 18 (Excess or "
    "(deficit) for the year). For each, give the amount exactly as the return shows it (do not "
    "compute or correct anything; a deficit in parentheses or with a minus sign is negative) and "
    "a verbatim quote copied from the text that contains the line's label and the amount. If a "
    "line has no amount or you cannot find it, give an empty amount and an empty quote.\n"
    'Return ONLY a JSON object: {"9": {"amount": "...", "quote": "..."}, '
    '"17": {"amount": "...", "quote": "..."}, "18": {"amount": "...", "quote": "..."}}'
)

# --- the frozen rules (pure functions) -------------------------------------------------------

_TOKEN_EDGE = re.compile(r"^[^\d]+|[^\d]+$")
_NUMERIC = re.compile(r"^\d[\d,]*(?:\.\d+)?$")


def parse_amount(text: Any) -> Decimal | None:
    """The model's amount: '$', commas and spaces ignored; '(...)' or a leading '-' is negative;
    two decimals kept. None if it is not a number."""
    raw = str(text if text is not None else "").strip()
    negative = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
    cleaned = re.sub(r"[\s$,()\-]", "", raw)
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", cleaned):
        return None
    try:
        value = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -value if negative else value


def token_values(token: str) -> list[Decimal]:
    """The values one whitespace-separated token of the quote can stand for (absolute values).

    Non-digit characters at either end are stripped ("$", "(", ")", "►", a trailing "."). What is
    left must be digits with optional commas and an optional decimal part. As written: commas
    removed; a token without a decimal point is whole dollars. A token of 3 or more plain digits
    (no comma, no point) may also be the amount with its decimal point dropped (the text layer is
    often OCR: "6448446" for 64,484.46), so it also stands for that value divided by 100.
    """
    core = _TOKEN_EDGE.sub("", token)
    if not core or not _NUMERIC.match(core):
        return []
    try:
        values = [Decimal(core.replace(",", ""))]
    except InvalidOperation:
        return []
    if core.isdigit() and len(core) >= 3:
        values.append((Decimal(core) / 100).quantize(Decimal("0.01")))
    return values


def amount_in_quote(amount: Decimal, quote: str) -> bool:
    """The amount appears inside the quote, digits normalised and cents optional: some token
    equals |amount| to the cent, or is whole dollars equal to |amount|'s dollars (cents not
    shown on the return), or is plain digits equal to |amount| with the point dropped. The sign
    is not checked (the text layer often loses parentheses); it comes from the model's amount."""
    target = abs(amount)
    whole = target.to_integral_value(rounding=ROUND_DOWN)
    for token in quote.split():
        core = _TOKEN_EDGE.sub("", token)
        for i, value in enumerate(token_values(token)):
            if value == target:
                return True
            written_whole = i == 0 and "." not in core
            if written_whole and value == whole:
                return True
    return False


def check_line(line: str, answer: Any, page: str) -> dict[str, Any]:
    """One line of the model's answer against the page text: accepted only if the amount parses,
    the quote is found verbatim (quotes.locate: case, punctuation and whitespace ignored), the
    quote carries the line's label or instruction, and the amount is inside the quote."""
    entry = answer if isinstance(answer, dict) else {}
    amount_text = str(entry.get("amount") or "").strip()
    quote = str(entry.get("quote") or "")
    out: dict[str, Any] = {"amount_text": amount_text, "quote": quote}
    if not amount_text:
        return {**out, "status": "rejected", "reason": "no_amount"}
    amount = parse_amount(amount_text)
    if amount is None:
        return {**out, "status": "rejected", "reason": "amount_unparseable"}
    out["value"] = str(amount)
    span = locate(quote, page)
    if span is None:
        return {**out, "status": "rejected", "reason": "quote_not_in_text"}
    out["span"] = [span.start, span.end]
    out["label_in_quote"] = bool(LABELS[line].search(quote))
    if not out["label_in_quote"]:
        return {**out, "status": "rejected", "reason": "label_not_in_quote"}
    if not amount_in_quote(amount, quote):
        return {**out, "status": "rejected", "reason": "amount_not_in_quote"}
    return {**out, "status": "accepted", "reason": ""}


def check_answer(answer: dict[str, Any] | None, page: str) -> dict[str, Any]:
    answer = answer or {}
    return {line: check_line(line, answer.get(line), page) for line in LINES}


def record_gap(record: dict[str, Any]) -> Decimal:
    """Database 9 - 17 - 18 (the extract holds whole dollars)."""
    return Decimal(str(record["9"])) - Decimal(str(record["17"])) - Decimal(str(record["18"]))


def filing_verdict(record: dict[str, Any], lines: dict[str, Any]) -> dict[str, Any]:
    """The frozen verdict, in this order:
    1. not read: any of lines 9, 17, 18 not accepted;
    2. record matches return: every accepted value within $1 of the database (|d| < $1);
    3. the return itself does not add up: the return's own |9 - 17 - 18| >= $2;
    4. the record contradicts the return on <field>: the return adds up (|gap| <= $1) and exactly
       one database value differs by $1 or more from the accepted value;
    5. other: anything else (more than one field differs, or a return gap above $1 and under $2).
    """
    if any(lines.get(ln, {}).get("status") != "accepted" for ln in LINES):
        return {"verdict": VERDICT_NOT_READ, "read_cleanly": False}
    doc = {ln: Decimal(lines[ln]["value"]) for ln in LINES}
    gap = doc["9"] - doc["17"] - doc["18"]
    differ = [ln for ln in LINES if abs(doc[ln] - Decimal(str(record[ln]))) >= FIELD_TOLERANCE]
    base = {"read_cleanly": True, "return_gap": str(gap), "differing_lines": differ}
    if not differ:
        return {**base, "verdict": VERDICT_MATCHES}
    if abs(gap) >= MIN_GAP:
        return {**base, "verdict": VERDICT_NOT_ADD_UP}
    if abs(gap) <= ADDS_UP and len(differ) == 1:
        field = f"line {differ[0]} ({FIELD_NAMES[differ[0]]})"
        return {**base, "verdict": VERDICT_CONTRADICTS.format(field=field), "line": differ[0]}
    return {**base, "verdict": VERDICT_OTHER}


def summarise(rows: list[dict[str, Any]], provider_failures: int) -> dict[str, Any]:
    verdicts = [r["verdict"] for r in rows]
    read = sum(bool(r.get("read_cleanly")) for r in rows)
    contradicts = sum(v.startswith("the record contradicts the return on") for v in verdicts)
    void = provider_failures > VOID_FAILURES
    return {
        "filings": len(rows),
        "read_cleanly": read,
        "record_contradicts_return": contradicts,
        "verdicts": {v: verdicts.count(v) for v in sorted(set(verdicts))},
        "provider_failures": provider_failures,
        "void": void,
        "pattern_works_on_second_non_medical_domain": (
            not void and read >= CLAIM_READ and contradicts >= CLAIM_CONTRADICTS
        ),
    }


def text_ok(text: str) -> bool:
    return len(text.strip()) >= MIN_TEXT_CHARS


# --- the population and the draw -------------------------------------------------------------


def parse_extract(lines: list[str]) -> list[dict[str, Any]]:
    """Rows of the space-separated SOI extract (header first) as dicts; nothing interpreted."""
    header = lines[0].split()
    return [dict(zip(header, line.split(), strict=False)) for line in lines[1:] if line.strip()]


def _int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def eligible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paper records (elf == N) whose three values are integers and break 9 - 17 = 18 by $2 or
    more; one row per (EIN, tax period), the first in file order kept; design cases out; sorted by
    (EIN, tax period)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        if r.get("elf") != "N":
            continue
        values = {ln: _int(r.get(COLUMNS[ln])) for ln in LINES}
        if any(v is None for v in values.values()):
            continue
        key = (str(r.get("EIN")), str(r.get("tax_pd")))
        if key in DESIGN_CASES or key in out:
            continue
        if abs(record_gap(values)) >= MIN_GAP:
            out[key] = {"ein": key[0], "tax_period": key[1], "record": values}
    return [out[k] for k in sorted(out)]


def draw(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return random.Random(SEED).sample(pool, SAMPLE_SIZE)


def pdf_url(ein: str, period: str) -> str:
    if not (ein.isdigit() and len(ein) == 9 and period.isdigit() and len(period) == 6):
        raise ValueError("EIN or tax period malformed")
    return PDF_URL.format(a=ein[:3], ein=ein, period=period)


# --- downloads (no model) --------------------------------------------------------------------


def _fetch(url: str, accept: str) -> tuple[int, bytes] | str:
    import httpx

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": accept}, timeout=180, follow_redirects=True
        ) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        return type(exc).__name__
    return response.status_code, response.content


def download_extract() -> dict[str, Any]:
    if not EXTRACT_ZIP.exists():
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        got = _fetch(EXTRACT_URL, "application/zip,*/*")
        if isinstance(got, str) or got[0] != 200 or got[1][:2] != b"PK" or len(got[1]) > MAX_BYTES:
            raise RuntimeError(
                f"extract download failed: {got if isinstance(got, str) else got[0]}"
            )
        EXTRACT_ZIP.write_bytes(got[1])
    body = EXTRACT_ZIP.read_bytes()
    return {"url": EXTRACT_URL, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def load_rows() -> tuple[list[dict[str, Any]], str]:
    """The extract's .dat member read in-process (never extracted to disk)."""
    with zipfile.ZipFile(io.BytesIO(EXTRACT_ZIP.read_bytes())) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".dat")]
        if len(names) != 1:
            raise RuntimeError("expected one .dat member in the extract")
        text = archive.read(names[0]).decode("latin-1")
    return parse_extract(text.splitlines()), names[0]


def _pdf_path(ein: str, period: str) -> Path:
    return PDF_DIR / f"{ein}_{period}" / "return.pdf"


def page1_text(path: Path) -> tuple[int, str]:
    """(page count, page 1 text layer) by pypdfium2."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    try:
        textpage = doc[0].get_textpage()
        return len(doc), textpage.get_text_range()
    finally:
        doc.close()


def download_pdf(ein: str, period: str) -> dict[str, Any]:
    """One return into its own new folder. A miss is recorded as "no document", never replaced."""
    target = _pdf_path(ein, period)
    url = pdf_url(ein, period)
    if not (target.exists() and target.read_bytes()[:4] == b"%PDF"):
        got = _fetch(url, "application/pdf,*/*")
        if isinstance(got, str):
            return {"status": "no document", "reason": got, "url": url}
        status, body = got
        if status != 200:
            return {"status": "no document", "reason": f"http_{status}", "url": url}
        if body[:4] != b"%PDF":
            return {"status": "no document", "reason": "not_a_pdf", "url": url}
        if len(body) > MAX_BYTES:
            return {"status": "no document", "reason": "too_large", "url": url}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    body = target.read_bytes()
    pages, text = page1_text(target)
    return {
        "status": "ok",
        "url": url,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "pages": pages,
        "page1_text_chars": len(text.strip()),
    }


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    """Download the extract, draw the sample, download the returns (no model), write the json.
    Refuses after a run."""
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    extract = download_extract()
    rows, member = load_rows()
    paper = sum(r.get("elf") == "N" for r in rows)
    pool = eligible(rows)
    sample = []
    for i, item in enumerate(draw(pool)):
        if i:
            time.sleep(2)  # polite: sequential, a pause between requests
        outcome = download_pdf(item["ein"], item["tax_period"])
        sample.append(
            {
                "ein": item["ein"],
                "tax_period": item["tax_period"],
                "record": {ln: str(item["record"][ln]) for ln in LINES},
                "record_gap": str(record_gap(item["record"])),
                "download": outcome,
            }
        )
    missing = sum(s["download"]["status"] != "ok" for s in sample)
    old = json.loads(PREREG.read_text(encoding="utf-8")) if PREREG.exists() else {}
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "prompt_sha256_16": sha16(PROMPT),
        "extract": {**extract, "member": member},
        "population": {
            "rows": len(rows),
            "paper_rows": paper,
            "eligible": len(pool),
            "eligible_rule": (
                "elf == N; totrevnue, totexpns, totexcessyr integers; |totrevnue - totexpns - "
                "totexcessyr| >= $2; one row per (EIN, tax_pd), first in file order kept; design "
                "cases excluded; sorted by (EIN, tax_pd)"
            ),
            "design_cases_excluded": [list(c) for c in DESIGN_CASES],
        },
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b via Nightshift, text only, pinned, "
        f"signed receipt, no cache, {BUDGET} thinking budget, one call per filing",
        "missing_documents": missing,
        "stop": missing > STOP_MISSING,
        "sample": sample,
        "rules": {
            "document": f"page 1 text layer (pypdfium2); under {MIN_TEXT_CHARS} chars = not read; "
            "no OCR fallback",
            "line_accepted": "amount parses; quote found by app.reader.quotes.locate; amount "
            "inside the quote (digits normalised, cents optional)",
            "verdict_order": [
                VERDICT_NOT_READ,
                VERDICT_MATCHES,
                VERDICT_NOT_ADD_UP,
                VERDICT_CONTRADICTS.format(field="[field]"),
                VERDICT_OTHER,
            ],
            "field_differs": "|return - database| >= $1",
            "return_adds_up": "|9 - 17 - 18| <= $1",
            "return_does_not_add_up": "|9 - 17 - 18| >= $2",
        },
        "claim": (
            "'the product's pattern works on a second, non-medical domain' only if >= "
            f"{CLAIM_READ} of {SAMPLE_SIZE} read cleanly (all three lines accepted) AND >= "
            f"{CLAIM_CONTRADICTS} are 'the record contradicts the return on [field]'"
        ),
        "void": f"more than {VOID_FAILURES} provider failures",
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
    if sha16(PROMPT) != record["prompt_sha256_16"]:
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


# --- the run ---------------------------------------------------------------------------------


async def ask(page: str, item_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One pinned, signed, uncached Super VL call through Nightshift on the page text."""
    from app import config
    from app.providers import envelope_tap, nightshift
    from app.reader.reader import parse_answer, thinking_args

    extra, max_tokens = thinking_args(BUDGET)
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Page 1 text:\n\n{page}"},
    ]
    row: dict[str, Any] = {"item_id": item_id}
    started = time.monotonic()
    with envelope_tap.capture() as calls:
        try:
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
        except Exception as exc:  # a provider failure: recorded, never re-run
            row["provider_failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            return row, calls
    row["seconds"] = round(time.monotonic() - started, 2)
    row["receipt_id"], row["signature"] = receipt.receipt_id, receipt.signature
    row["raw"] = text[:3000]
    row["answer"] = parse_answer(text)
    return row, calls


async def read_filing(item: dict[str, Any], tag: str, budget: dict[str, int]) -> dict[str, Any]:
    ein, period = item["ein"], item["tax_period"]
    row: dict[str, Any] = {"ein": ein, "tax_period": period, "record_gap": item["record_gap"]}
    path = _pdf_path(ein, period)
    if item["download"]["status"] != "ok" or not path.exists():
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "no document"}
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["download"]["sha256"]:
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "pdf_changed_since_freeze"}
    _, page = page1_text(path)
    row["page_text"] = page
    if not text_ok(page):
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "no text layer (under 500 chars)"}
    if budget["failures"] > VOID_FAILURES:
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "skipped_void"}
    item_id = f"irs-read-{tag}-{ein}-{period}-{uuid.uuid4().hex[:6]}"
    call, envelopes = await ask(page, item_id)
    row.update(call)
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for c in envelopes:
        with ENVELOPES.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"run": tag, "ein": ein, "tax_period": period, **c}, sort_keys=True)
                + "\n"
            )
    if "provider_failure" in call:
        budget["failures"] += 1
        return {**row, "verdict": VERDICT_NOT_READ, "reason": "provider failure"}
    row["lines"] = check_answer(call.get("answer"), page)
    return {**row, **filing_verdict(item["record"], row["lines"])}


async def run_irs_read() -> dict[str, Any]:
    record = frozen()
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    if record["stop"]:
        raise RuntimeError(f"more than {STOP_MISSING} returns had no document: stopped")
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction into irs-read.json before the run")
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    budget = {"failures": 0}
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for item in record["sample"]:
        row = {"run": tag, **(await read_filing(item, tag, budget))}
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows, budget["failures"])}
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, default=str) + "\n")
    return summary
