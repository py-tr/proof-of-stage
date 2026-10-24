from decimal import Decimal

from app.fec.guard import Check, check_value, classify, identity_gap, money, verdict

DOC = (
    "23. CASH ON HAND AT BEGINNING OF REPORTING PERIOD ........ 12,000.00\n"
    "24. TOTAL RECEIPTS THIS PERIOD (from Line 16, page 3) .... 5,535.35\n"
    "26. TOTAL DISBURSEMENTS THIS PERIOD (from Line 22) ...... 2,000.00\n"
    "27. CASH ON HAND AT CLOSE OF REPORTING PERIOD ........... 15,535.35\n"
)
RECORD = {
    "cash_on_hand_beginning_period": 12000.0,
    "total_receipts_period": 5535.35,
    "total_disbursements_period": 2000.0,
    "cash_on_hand_end_period": 20535.35,
}


def test_money_and_the_identity() -> None:
    assert money("20,535.35") == Decimal("20535.35") and money("(250.00)") == Decimal("-250.00")
    assert identity_gap(RECORD) == Decimal("-5000.00")
    assert (
        classify(Decimal("-5000.00")) == "impossible" and classify(Decimal("-0.38")) == "cents_only"
    )
    assert classify(Decimal("0")) == "consistent" and classify(None) == "incomplete"


def test_a_value_needs_its_quote_its_amount_and_its_line_label() -> None:
    ok = check_value(
        "close",
        "15,535.35",
        "27. CASH ON HAND AT CLOSE OF REPORTING PERIOD ........... 15,535.35",
        DOC,
    )
    assert ok.status == "accepted" and ok.value == Decimal("15535.35")
    wrong_line = check_value(
        "close",
        "5,535.35",
        "24. TOTAL RECEIPTS THIS PERIOD (from Line 16, page 3) .... 5,535.35",
        DOC,
    )
    assert wrong_line.reason == "label_not_in_quote"
    assert (
        check_value(
            "close",
            "16,000.00",
            "27. CASH ON HAND AT CLOSE OF REPORTING PERIOD ........... 15,535.35",
            DOC,
        ).reason
        == "amount_not_in_quote"
    )
    assert (
        check_value("close", "1.00", "CASH ON HAND AT CLOSE: 1.00 made up", DOC).reason
        == "quote_not_in_document"
    )


def test_the_verdict_names_the_one_field_the_document_contradicts() -> None:
    lines = {
        "beginning": "23. CASH ON HAND AT BEGINNING OF REPORTING PERIOD ........ 12,000.00",
        "receipts": "24. TOTAL RECEIPTS THIS PERIOD (from Line 16, page 3) .... 5,535.35",
        "disbursements": "26. TOTAL DISBURSEMENTS THIS PERIOD (from Line 22) ...... 2,000.00",
        "close": "27. CASH ON HAND AT CLOSE OF REPORTING PERIOD ........... 15,535.35",
    }
    values = {
        "beginning": "12,000.00",
        "receipts": "5,535.35",
        "disbursements": "2,000.00",
        "close": "15,535.35",
    }
    doc = {f: check_value(f, values[f], lines[f], DOC) for f in lines}
    assert verdict(RECORD, doc) == "close"  # the record's close was keyed as 20,535.35
    doc["receipts"] = Check("receipts", "rejected", reason="quote_not_in_document")
    assert verdict(RECORD, doc) == "review"
