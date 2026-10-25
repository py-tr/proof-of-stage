"""The frozen FEC read-level rules on synthetic Parse output (no network, no model)."""

from decimal import Decimal

from app.fec.guard import RECORD_COLUMNS
from app.fec.read import (
    VERDICT_MATCHES,
    VERDICT_NOT_ADD_UP,
    VERDICT_NOT_READ,
    VERDICT_OTHER,
    extract_line,
    filing_verdict,
    find_summary_page,
    lines_of,
    page_text,
    read_fields,
    summarise,
)


def _blocks(*texts: str) -> list[dict]:
    return [{"text": t, "kind": "Text", "x0": 0, "y0": 0, "x1": 1, "y1": 1} for t in texts]


SUMMARY = page_text(
    _blocks(
        "DETAILED SUMMARY PAGE of Disbursements",
        "17. OPERATING EXPENDITURES ........ 5.97 31,295.46",
        "22. TOTAL DISBURSEMENTS (add Lines 17, 18, 19(c), 20(d), and 21) 5.97 32,045.46",
        "III. CASH SUMMARY",
        "23. CASH ON HAND AT BEGINNING OF REPORTING PERIOD .............. 55,126.91",
        "24 TOTAL RECEIPTS THIS PERIOD (from Line 16, page 3) ............ 1.90",
        "25. SUBTOTAL (add Line 23 and Line 24) ........ 55,128.81",
        "26. TOTAL DISBURSEMENTS THIS PERIOD (from Line 22) ........ 5.97",
        "27. CASH ON HAND AT CLOSE OF REPORTING PERIOD\n"
        "(subtract Line 26 from Line 25)...... 55,122.84",
    )
)
RECEIPTS_PAGE = page_text(
    _blocks("DETAILED SUMMARY PAGE of Receipts", "16. TOTAL RECEIPTS (add Lines 11(e)...) 1.90")
)
COVER_SUMMARY = page_text(_blocks("8. CASH ON HAND AT CLOSE OF REPORTING PERIOD 55,122.84"))


def _record(b: str, r: str, d: str, c: str) -> dict:
    values = dict(zip(("beginning", "receipts", "disbursements", "close"), (b, r, d, c)))
    return {RECORD_COLUMNS[f]: v for f, v in values.items()}


def test_summary_page_is_the_first_page_with_both_cash_phrases() -> None:
    pages = {3: RECEIPTS_PAGE, 4: SUMMARY, 5: SUMMARY, 6: COVER_SUMMARY}
    assert find_summary_page(pages) == 4
    assert find_summary_page({3: RECEIPTS_PAGE, 6: COVER_SUMMARY}) is None
    assert find_summary_page({}) is None


def test_lines_split_at_newlines_and_latex_rows() -> None:
    page = "a & 1 \\\\ b & 2\n\nc</tr>d"
    assert [x.text(page).strip() for x in lines_of(page)] == ["a & 1", "b & 2", "c", "d"]


def test_each_line_takes_its_own_amount_not_a_line_reference() -> None:
    assert extract_line("beginning", SUMMARY)[0] == "55,126.91"
    amount, quote = extract_line("receipts", SUMMARY)
    assert amount == "1.90" and quote.startswith("24 TOTAL RECEIPTS")  # not 16 or 3
    amount, quote = extract_line("disbursements", SUMMARY)
    assert amount == "5.97" and quote.startswith("26.")  # line 22 is not "this period"
    amount, quote = extract_line("close", SUMMARY)  # label and amount on two lines
    assert amount == "55,122.84" and "subtract Line 26" in quote
    for field in ("beginning", "receipts", "disbursements", "close"):
        _, quote = extract_line(field, SUMMARY)
        assert quote in SUMMARY


def test_merged_rows_are_cut_at_the_next_label_and_latex_cells_work() -> None:
    merged = (
        "23. CASH ON HAND AT BEGINNING OF REPORTING PERIOD 100.00 "
        "24 TOTAL RECEIPTS THIS PERIOD (from Line 16) 50.00"
    )
    assert extract_line("beginning", merged)[0] == "100.00"
    assert extract_line("receipts", merged)[0] == "50.00"
    latex = (
        "\\begin{tabular}{ll} 26. TOTAL DISBURSEMENTS THIS PERIOD & \\$ 2,000.00 \\\\ "
        "\\end{tabular}"
    )
    assert extract_line("disbursements", latex)[0] == "$ 2,000.00"


def test_a_line_number_alone_is_a_label_and_a_missing_amount_is_none() -> None:
    assert extract_line("disbursements", "26. TOTAI DISBURSMENTS 7.00")[0] == "7.00"
    assert extract_line("close", "27. CASH ON HAND AT CLOSE OF REPORTING PERIOD") is None
    blank_then_label = "23. CASH ON HAND AT BEGINNING\n24 TOTAL RECEIPTS THIS PERIOD 9.00"
    assert extract_line("beginning", blank_then_label) is None  # never borrows another line


def test_guard_accepts_all_four_on_the_summary_page() -> None:
    fields = read_fields(SUMMARY)
    assert all(fields[f]["status"] == "accepted" for f in fields)
    assert fields["close"]["value"] == "55122.84"


def test_verdicts_in_their_frozen_order() -> None:
    fields = read_fields(SUMMARY)  # the document adds up: 55,126.91 + 1.90 - 5.97 = 55,122.84
    one = filing_verdict(_record("55126.91", "1.90", "5.97", "55222.84"), fields)
    assert (
        one["verdict"] == "the filing contradicts the record on close" and one["field"] == "close"
    )
    two = filing_verdict(_record("55126.91", "100.90", "5.97", "55222.84"), fields)
    assert two["verdict"] == VERDICT_OTHER
    cents = filing_verdict(_record("55126.00", "1.90", "5.97", "55122.00"), fields)
    assert cents["verdict"] == VERDICT_MATCHES  # differences under $1 are not a difference
    bad = read_fields(SUMMARY.replace("55,122.84", "55,000.00"))
    assert filing_verdict(_record("55126.91", "1.90", "5.97", "55222.84"), bad)["verdict"] == (
        VERDICT_NOT_ADD_UP
    )
    assert filing_verdict(_record("55126.91", "1.90", "5.97", "55000.00"), bad)["verdict"] == (
        VERDICT_MATCHES
    )
    missing = read_fields(SUMMARY.replace("55,126.91", ""))
    assert filing_verdict(_record("1", "1", "1", "1"), missing)["verdict"] == VERDICT_NOT_READ


def test_claim_line_and_void() -> None:
    contra = {"verdict": "the filing contradicts the record on close", "read_cleanly": True}
    match = {"verdict": VERDICT_MATCHES, "read_cleanly": True}
    miss = {"verdict": VERDICT_NOT_READ, "read_cleanly": False}
    rows = [contra] * 3 + [match] * 2 + [miss] * 7
    out = summarise(rows, page_failures=4)
    assert out["read_cleanly"] == 5 and out["name_one_field"] == 3
    assert out["pattern_transfers_at_read_level"] and not out["void"]
    assert not summarise(rows, page_failures=5)["pattern_transfers_at_read_level"]
    assert not summarise([contra] * 2 + [match] * 3 + [miss] * 7, 0)[
        "pattern_transfers_at_read_level"
    ]
    assert Decimal(read_fields(SUMMARY)["beginning"]["value"]) == Decimal("55126.91")
