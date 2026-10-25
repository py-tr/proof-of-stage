import pytest

from app.usl import attest_store as a
from app.usl.client import guard_select


def test_attestation_insert_requires_a_verified_receipt_row():
    sql = a.insert_attestation_sql(
        attest_id="x1",
        run="r",
        case_id="TCGA-E2-A572",
        field="N",
        stored_value="N2A",
        stored_quote="q",
        stored_quote_rechecked="accepted",
        signed_value="N2A",
        signed_quote="q",
        outcome="reproduced",
        receipt_id="rcpt_1",
        created_at="t",
    )
    assert sql.startswith("INSERT INTO oa_pg.attestation")
    assert "NOT EXISTS" in sql and "existing.attest_id = 'x1'" in sql
    assert "FROM oa_pg.attest_receipt AS signed" in sql
    assert "signed.signature_state = 'verified'" in sql


def test_a_reading_without_receipt_is_only_a_provider_failure():
    with pytest.raises(ValueError):
        a.insert_attestation_sql(
            attest_id="x2",
            run="r",
            case_id="c",
            field="N",
            stored_value=None,
            stored_quote=None,
            stored_quote_rechecked=None,
            signed_value="N1",
            signed_quote=None,
            outcome="reproduced",
            receipt_id=None,
            created_at="t",
        )
    sql = a.insert_attestation_sql(
        attest_id="x3",
        run="r",
        case_id="c",
        field="N",
        stored_value=None,
        stored_quote=None,
        stored_quote_rechecked=None,
        signed_value=None,
        signed_quote=None,
        outcome="provider_failure",
        receipt_id=None,
        created_at="t",
    )
    assert "attest_receipt" not in sql


def test_unknown_outcome_is_refused():
    with pytest.raises(ValueError):
        a.insert_attestation_sql(
            attest_id="x4",
            run="r",
            case_id="c",
            field="N",
            stored_value=None,
            stored_quote=None,
            stored_quote_rechecked=None,
            signed_value=None,
            signed_quote=None,
            outcome="correct",
            receipt_id="r1",
            created_at="t",
        )


def test_receipt_insert_is_append_only_and_keeps_the_envelope():
    sql = a.insert_receipt_sql(
        receipt_id="rcpt_1",
        item_id="i",
        served_model="m",
        route_kind="cloud",
        signer_fingerprint="7a6d14e27e1a",
        signature_state="verified",
        cache_status="miss",
        prompt_chars=10,
        messages_sha256="a" * 64,
        answer_sha256="b" * 64,
        envelope={"body": {"x": 1}, "sig_b64": "s", "pubkey_b64": "p"},
        created_at="t",
    )
    assert "NOT EXISTS" in sql and '"sig_b64": "s"' in sql


def test_read_guard_admits_the_attestation_tables():
    guard_select("SELECT outcome, count(*) FROM oa_pg.attestation GROUP BY outcome")
    guard_select("SELECT receipt_id FROM oa_pg.attest_receipt")
