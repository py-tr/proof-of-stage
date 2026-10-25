"""The /how cards for probe 4 and the attestation census, from the committed logs (no model)."""

from app.web.agentprobe import _probe4
from app.web.attestcard import attest_summary


def test_probe4_card_reads_the_committed_log() -> None:
    p = _probe4()
    assert p and p["ids_calls"] == 5 and p["exact_six"] == 4
    assert p["fix_calls"] == 5 and p["refused"] == 5
    q = p["refused_query"]
    assert q["sql"].upper().startswith("UPDATE") and "SqlGuardError" in q["guard"]


def test_attest_card_verifies_the_committed_bundle() -> None:
    s = attest_summary()
    assert s and s["values"] == 42 and s["cases"] == 26
    assert s["outcomes"] == {"reproduced": 42}
    assert s["receipts_verified"] == s["receipts"] == 57 and s["passed"]
    assert s["example"]["case"] == "TCGA-E2-A572" and s["example"]["field"] == "NPOS"
    assert "does NOT establish" in s["not_established"]


def test_receipt_bundles_serve_every_committed_envelope() -> None:
    from app.web.receiptsbundle import bundle, bundle_list

    ids = {b["id"] for b in bundle_list() if b["present"]}
    assert {"attest", "agent-probe-4"} <= ids
    attest = bundle("attest")
    assert attest and len(attest["rows"]) == 57 and attest["fingerprint"] == "7a6d14e27e1a"
    assert all(set(r["envelope"]) >= {"body", "pubkey_b64", "sig_b64"} for r in attest["rows"])
    assert bundle("../../.env") is None


def test_probe5_card_reads_the_committed_log() -> None:
    from app.web.agentprobe import _probe5

    p = _probe5()
    assert p and p["agent_calls"] == 5 and p["agent_correct"] == 5
    assert p["control_raw"] == 5 and "AGENT_FILES.node_status" in p["agent_query"]["sql"]
