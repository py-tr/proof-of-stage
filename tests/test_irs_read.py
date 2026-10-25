"""The frozen IRS 990-EZ read-level rules on synthetic page text (no network, no model)."""

from decimal import Decimal

from app.irs.read import (
    VERDICT_MATCHES,
    VERDICT_NOT_ADD_UP,
    VERDICT_NOT_READ,
    VERDICT_OTHER,
    amount_in_quote,
    check_answer,
    check_line,
    draw,
    eligible,
    filing_verdict,
    parse_amount,
    parse_extract,
    record_gap,
    summarise,
    text_ok,
    token_values,
)

PAGE = (
    "8 Other revenue (describe in Schedule 0) . . . . . 8 0\n"
    "9 Total revenue. Add lines 1, 2, 3, 4, 5c, 6d, 7c, and 8 ► 9 45,210.00\n"
    "16 Other ex penses (describe in Schedule 0) t w 1 6\n"
    "17 Total expenses. Add lines 10 throu g h 16 f 17 41,650.00\n"
    "18 Excess or (deficit) for the year (Subtract line 17 from line)G.DE . . 18 3,560.00\n"
)
OCR_PAGE = (
    "9 Total revenue. Add lines 1, 2, 3, 4, 5c, 6d, 7c, and 8 . ► 9 6448446\n"
    "17 Total expenses. Add fines 10 through 16 . . . ► 17 5126213\n"
    "18 Excess or (deficit) for the year (Subtract line 17 from line 9) . . 18 13322.33\n"
)


def _answer(a9, q9, a17, q17, a18, q18):
    return {
        "9": {"amount": a9, "quote": q9},
        "17": {"amount": a17, "quote": q17},
        "18": {"amount": a18, "quote": q18},
    }


GOOD = _answer(
    "45,210.00",
    "9 Total revenue. Add lines 1, 2, 3, 4, 5c, 6d, 7c, and 8 ► 9 45,210.00",
    "41650.00",
    "17 Total expenses. Add lines 10 throu g h 16 f 17 41,650.00",
    "3,560.00",
    "Excess or (deficit) for the year (Subtract line 17 from line)G.DE . . 18 3,560.00",
)


def test_parse_amount_signs_and_noise():
    assert parse_amount("$45,210.00") == Decimal("45210.00")
    assert parse_amount("(3,560)") == Decimal("-3560.00")
    assert parse_amount("-332736") == Decimal("-332736.00")
    assert parse_amount("") is None and parse_amount("n/a") is None
    assert parse_amount("12.345") is None


def test_token_values_dropped_point():
    assert token_values("6448446") == [Decimal("6448446"), Decimal("64484.46")]
    assert token_values("45,210.00") == [Decimal("45210.00")]
    assert token_values("(2299.19)") == [Decimal("2299.19")]
    assert token_values("17") == [Decimal("17")]
    assert token_values("revenue.") == []


def test_amount_in_quote_cents_optional_and_digits_normalised():
    assert amount_in_quote(Decimal("45210.00"), "9 45,210.00")
    assert amount_in_quote(Decimal("45210.00"), "9 45,210")
    assert amount_in_quote(Decimal("5017.46"), "6c 5,017 00")  # cents optional
    assert amount_in_quote(Decimal("64484.46"), "9 6448446")  # OCR dropped the point
    assert amount_in_quote(Decimal("-2299.19"), "6d (2299.19)")  # sign not checked
    assert not amount_in_quote(Decimal("45110.00"), "9 45,210.00")
    assert not amount_in_quote(Decimal("45210.46"), "9 45,210.00")  # cents shown must match
    assert not amount_in_quote(Decimal("452100.00"), "9 4521.00")
    assert not amount_in_quote(Decimal("3560.00"), "21 3 560 00")  # split digits: not found


def test_check_line_reasons():
    page = PAGE
    ok = check_line("9", GOOD["9"], page)
    assert ok["status"] == "accepted" and ok["value"] == "45210.00" and ok["label_in_quote"]
    bad_quote = check_line("9", {"amount": "45210", "quote": "Total revenue 45,210.99"}, page)
    assert bad_quote["reason"] == "quote_not_in_text"
    wrong_amount = check_line("9", {"amount": "45110", "quote": GOOD["9"]["quote"]}, page)
    assert wrong_amount["reason"] == "amount_not_in_quote"
    assert check_line("9", {"amount": "", "quote": "x"}, page)["reason"] == "no_amount"
    assert check_line("9", None, page)["reason"] == "no_amount"
    assert check_line("9", {"amount": "abc", "quote": "x"}, page)["reason"] == "amount_unparseable"
    # a quote without the label is still accepted (label recorded, not gating)
    bare = check_line("9", {"amount": "45210.00", "quote": "8 ► 9 45,210.00"}, page)
    assert bare["status"] == "accepted" and bare["label_in_quote"] is False


def test_verdict_record_contradicts_return_on_revenue():
    record = {"9": "45110", "17": "41650", "18": "3560"}  # the verified example
    lines = check_answer(GOOD, PAGE)
    out = filing_verdict(record, lines)
    assert out["verdict"] == "the record contradicts the return on line 9 (total revenue)"
    assert out["return_gap"] == "0.00" and out["differing_lines"] == ["9"]
    assert record_gap(record) == Decimal("-100")


def test_verdict_on_ocr_page_with_dropped_points():
    answer = _answer(
        "64484.46",
        "Total revenue. Add lines 1, 2, 3, 4, 5c, 6d, 7c, and 8 . ► 9 6448446",
        "51262.13",
        "17 Total expenses. Add fines 10 through 16 . . . ► 17 5126213",
        "13322.33",
        "18 Excess or (deficit) for the year (Subtract line 17 from line 9) . . 18 13322.33",
    )
    lines = check_answer(answer, OCR_PAGE)
    assert all(v["status"] == "accepted" for v in lines.values())
    # this return's own 9 - 17 is 13,222.33, not 13,322.33: it does not add up
    record = {"9": "64484", "17": "51262", "18": "13222"}
    out = filing_verdict(record, lines)
    assert out["verdict"] == VERDICT_NOT_ADD_UP and out["return_gap"] == "-100.00"
    # database within $1 on every line (whole dollars): record matches return
    record = {"9": "64484", "17": "51262", "18": "13322"}
    assert filing_verdict(record, lines)["verdict"] == VERDICT_MATCHES


def _accepted(v9, v17, v18):
    return {
        ln: {"status": "accepted", "value": v} for ln, v in zip(("9", "17", "18"), (v9, v17, v18))
    }


def test_verdict_order_and_bands():
    record = {"9": "1000", "17": "800", "18": "150"}
    assert filing_verdict(record, _accepted("1000", "800", "150"))["verdict"] == VERDICT_MATCHES
    # every value within $1 of the database: matches, whatever the return's gap
    assert filing_verdict(record, _accepted("1000", "800", "150.50"))["verdict"] == (
        VERDICT_MATCHES
    )
    # the return's own gap of $40: does not add up
    assert filing_verdict(record, _accepted("1000", "800", "160"))["verdict"] == VERDICT_NOT_ADD_UP
    # two fields differ and the return adds up: other
    assert filing_verdict(record, _accepted("1100", "850", "250"))["verdict"] == VERDICT_OTHER
    # one field differs and the return gap is $1.50 (above $1, under $2): other
    assert filing_verdict(record, _accepted("1000", "800", "198.50"))["verdict"] == VERDICT_OTHER
    # one field differs, return gap exactly $1: adds up
    out = filing_verdict(record, _accepted("1000", "800", "199"))
    assert out["verdict"].startswith("the record contradicts the return on line 18")
    # any line not accepted: not read
    lines = _accepted("1000", "800", "200")
    lines["17"] = {"status": "rejected"}
    assert filing_verdict(record, lines) == {"verdict": VERDICT_NOT_READ, "read_cleanly": False}


def test_summarise_claim_and_void():
    contra = {"verdict": "the record contradicts the return on line 9 (total revenue)"}
    contra["read_cleanly"] = True
    clean = {"verdict": VERDICT_MATCHES, "read_cleanly": True}
    miss = {"verdict": VERDICT_NOT_READ, "read_cleanly": False}
    rows = [contra] * 3 + [clean] * 5 + [miss] * 8
    out = summarise(rows, 0)
    assert out["read_cleanly"] == 8 and out["record_contradicts_return"] == 3
    assert out["pattern_works_on_second_non_medical_domain"]
    assert not summarise([contra] * 2 + [clean] * 6 + [miss] * 8, 0)[
        "pattern_works_on_second_non_medical_domain"
    ]
    assert not summarise([contra] * 3 + [clean] * 4 + [miss] * 9, 0)[
        "pattern_works_on_second_non_medical_domain"
    ]
    voided = summarise(rows, 5)
    assert voided["void"] and not voided["pattern_works_on_second_non_medical_domain"]
    assert not summarise(rows, 4)["void"]


def test_text_threshold():
    assert not text_ok("x" * 499) and text_ok("x" * 500) and not text_ok(" " * 900)


def test_population_paper_gap_dedupe_design_cases_and_sort():
    lines = [
        "elf EIN tax_pd totrevnue totexpns totexcessyr",
        "N 900000002 201512 100 50 40",  # gap 10
        "N 900000002 201512 100 50 30",  # duplicate key: first kept
        "Y 900000003 201512 100 50 40",  # e-filed: out
        "N 900000001 201606 100 50 49",  # gap 1: out
        "N 900000001 201506 100 50 -2",  # gap 52
        "N 352517049 201506 45110 41650 3560",  # design case: out
        "N 900000004 201512 x 50 40",  # not an integer: out
    ]
    pool = eligible(parse_extract(lines))
    assert [(p["ein"], p["tax_period"]) for p in pool] == [
        ("900000001", "201506"),
        ("900000002", "201512"),
    ]
    assert pool[1]["record"] == {"9": 100, "17": 50, "18": 40}


def test_draw_is_seeded():
    pool = [{"ein": f"{i:09d}", "tax_period": "201512"} for i in range(40)]
    assert draw(pool) == draw(pool) and len(draw(pool)) == 16
