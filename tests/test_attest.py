from app.engine import attest


def test_outcome_uses_the_ladder_normalisation():
    assert attest.outcome("N", "N1a", "N1A") == "reproduced"
    assert attest.outcome("N", "N2A", "N1") == "differs"
    assert attest.outcome("NPOS", "4", "4") == "reproduced"
    assert attest.outcome("NPOS", "4", None) == "not_re_accepted"


def test_receipt_row_rechecks_the_signature_and_keeps_the_envelope(chat_response):
    call = {
        "item_id": "i1",
        "messages_sha256": "a" * 64,
        "answer_sha256": "b" * 64,
        "envelope": chat_response["meterless"]["receipt_envelope"],
    }
    row = attest.receipt_row(call, "t")
    assert row is not None
    assert row["receipt_id"] == chat_response["meterless"]["receipt_id"]
    assert row["signature_state"] == "verified"
    assert row["envelope"] == call["envelope"]


def test_receipt_row_with_a_tampered_body_is_not_verified(chat_response):
    import copy

    envelope = copy.deepcopy(chat_response["meterless"]["receipt_envelope"])
    envelope["body"]["receipt"]["prompt_chars"] = 1
    row = attest.receipt_row({"envelope": envelope}, "t")
    assert row is None or row["signature_state"] != "verified"


def test_rechecked_reports_the_guard_reason_without_a_model():
    report = "LYMPH NODES: 2 of 14 positive for metastatic carcinoma."
    assert attest._rechecked("NPOS", "2", "LYMPH NODES: 2 of 14 positive", report) == "accepted"
    assert attest._rechecked("NPOS", "3", "not in the report at all", report) != "accepted"
