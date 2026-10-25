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
