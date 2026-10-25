from app.fec import read_vl as v

RECORD = {
    "beginning": "60000.0",
    "receipts": "60000.0",
    "disbursements": "0.0",
    "close": "25042.54",
}


def test_compare_one_line_disagreement_goes_to_a_person():
    reading = {
        "23": "60,000.00",
        "24": "34957.54",
        "25": "25042.54",
        "26": "0.00",
        "27": "25042.54",
    }
    out = v.compare(reading, RECORD)
    assert out["lines"] == {"23": "agree", "24": "disagree", "26": "agree", "27": "agree"}
    assert out["outcome"] == "the readers disagree on line 24: a person decides"
    assert out["document_gap"] == "69915.00"


def test_compare_all_agree_and_the_document_gap():
    record = {
        "beginning": "500.0",
        "receipts": "14133.0",
        "disbursements": "12752.0",
        "close": "1810.61",
    }
    reading = {"23": "500.00", "24": "14133.00", "26": "12752.00", "27": "1810.61"}
    out = v.compare(reading, record)
    assert out["outcome"] == v.OUTCOME_AGREE
    assert out["document_gap"] == "70.39"


def test_unread_lines_count_as_disagreement():
    out = v.compare({"23": "", "24": "x", "26": "0", "27": "25042.54"}, RECORD)
    assert out["lines"]["23"] == "unread" and out["outcome"].startswith("the readers disagree on 2")


def test_summarise_claim_line():
    agree = {
        "lines": dict.fromkeys(v.LINES, "agree"),
        "outcome": v.OUTCOME_AGREE,
        "document_gap": "70.39",
        "filing_id": "a",
    }
    rows = [agree] * 16 + [{"outcome": v.OUTCOME_NOT_READ, "filing_id": "b"}] * 8
    out = v.summarise(rows)
    assert out["claim_met"] and out["all_four_agree_and_filing_does_not_add_up"] == 16
    rows = [agree] * 15 + [{"outcome": v.OUTCOME_NOT_READ, "filing_id": "b"}] * 9
    assert not v.summarise(rows)["claim_met"]
