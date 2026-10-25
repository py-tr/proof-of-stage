import copy
import json
from pathlib import Path

from app import verify
from app.engine import attest

REPORT = "Final diagnosis. Lymph node status: Positive 8 / 13 Extranodal extension present."


def _bundle(tmp_path: Path, chat_response: dict, outcome_row: dict | None = None):
    envelope = chat_response["meterless"]["receipt_envelope"]
    receipt = attest.receipt_row({"item_id": "i", "envelope": envelope}, "t")
    bundle = tmp_path / "attest"
    bundle.mkdir()
    (bundle / "envelopes.jsonl").write_text(
        json.dumps({"case": "TCGA-X", **receipt}) + "\n", encoding="utf-8"
    )
    (bundle / "pubkey.json").write_text(
        json.dumps({"fingerprint": receipt["signer_fingerprint"]}), encoding="utf-8"
    )
    row = outcome_row or {
        "case": "TCGA-X",
        "field": "N",
        "stored_value": "N2A",
        "signed_value": "N2A",
        "signed_quote": "Lymph node status: Positive 8 / 13",
        "outcome": "reproduced",
        "receipt_id": receipt["receipt_id"],
    }
    log = tmp_path / "attest.jsonl"
    log.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return bundle, log, receipt, row


def _run(bundle, log, monkeypatch, report=REPORT):
    monkeypatch.setattr(verify, "_reports", lambda: {"TCGA-X": report})
    return verify.verify(None, bundle=bundle, log=log)


def test_the_real_bundle_passes(tmp_path, chat_response, monkeypatch):
    bundle, log, _, _ = _bundle(tmp_path, chat_response)
    result = _run(bundle, log, monkeypatch)
    assert result["passed"], result["failures"]
    assert result["receipts_verified"] == 1 and result["quotes"]["ok"] == 1


def _rewrite_envelope(bundle, change):
    path = bundle / "envelopes.jsonl"
    row = json.loads(path.read_text(encoding="utf-8"))
    change(row)
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_one_flipped_signature_byte_fails(tmp_path, chat_response, monkeypatch):
    bundle, log, _, _ = _bundle(tmp_path, chat_response)

    def flip(row):
        sig = row["envelope"]["sig_b64"]
        row["envelope"]["sig_b64"] = ("A" if sig[0] != "A" else "B") + sig[1:]

    _rewrite_envelope(bundle, flip)
    assert not _run(bundle, log, monkeypatch)["passed"]


def test_a_changed_model_in_the_signed_body_fails(tmp_path, chat_response, monkeypatch):
    bundle, log, _, _ = _bundle(tmp_path, chat_response)

    def swap(row):
        row["envelope"]["body"]["receipt"]["winning_route"]["model"] = "nvidia/other-model"

    _rewrite_envelope(bundle, swap)
    assert not _run(bundle, log, monkeypatch)["passed"]


def test_a_changed_value_fails_the_outcome_check(tmp_path, chat_response, monkeypatch):
    bundle, log, _, row = _bundle(tmp_path, chat_response)
    tampered = {**row, "signed_value": "N1"}  # outcome still says reproduced
    log.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    result = _run(bundle, log, monkeypatch)
    assert not result["passed"]
    assert any("does not follow" in f for f in result["failures"])


def test_a_swapped_quote_keeps_the_signature_green_and_turns_the_quote_red(
    tmp_path, chat_response, monkeypatch
):
    bundle, log, _, row = _bundle(tmp_path, chat_response)
    swapped = {**row, "signed_quote": "Lymph node status: Negative 0 / 13"}
    log.write_text(json.dumps(swapped) + "\n", encoding="utf-8")
    result = _run(bundle, log, monkeypatch)
    assert result["receipts_verified"] == 1  # the signature still checks out
    assert any("quote is not in the report" in f for f in result["failures"])


def test_without_the_report_the_quote_is_skipped_not_passed(tmp_path, chat_response, monkeypatch):
    bundle, log, _, _ = _bundle(tmp_path, chat_response)
    monkeypatch.setattr(verify, "_reports", lambda: {})
    result = verify.verify(None, bundle=bundle, log=log)
    assert result["quotes"] == {"ok": 0, "skipped": 1}
    assert result["passed"]


def test_the_output_says_what_a_pass_does_not_establish(
    tmp_path, chat_response, monkeypatch, capsys
):
    bundle, log, _, _ = _bundle(tmp_path, chat_response)
    monkeypatch.setattr(verify, "BUNDLE", bundle)
    monkeypatch.setattr(verify, "OUTCOMES_LOG", log)
    monkeypatch.setattr(verify, "_reports", lambda: {"TCGA-X": REPORT})
    assert verify.main([]) == 0
    out = capsys.readouterr().out
    assert "does NOT establish" in out and "not the answer text" in out
    assert copy  # keep the import used
