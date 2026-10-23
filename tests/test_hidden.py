from app.engine.hidden import contradictions, summarise
from app.engine.rungs import CaseEvidence


def test_a_closed_count_in_the_same_category_still_counts_as_a_contradiction() -> None:
    case = CaseEvidence("C", "report", recorded_n="N2A", registry_count=7.0, edition="7")
    closed = {"N": {"rung": "R1", "value": "N2A"}, "NPOS": {"rung": "R2", "value": "6"}}
    assert contradictions(closed, case) == {"NPOS": {"registry": "7", "report": "6", "rung": "R2"}}
    assert contradictions({"N": {"rung": "R2", "value": "N2"}}, case) == {}  # same main category


def test_summary_counts_hits_and_voids_on_failures() -> None:
    rows = [
        {"case": "A", "provider_failure": False, "open": [], "contradicts_registry": {"NPOS": {}}},
        {"case": "B", "provider_failure": False, "open": ["N"], "contradicts_registry": {}},
        {"case": "C", "provider_failure": True, "open": [], "contradicts_registry": {}},
    ]
    out = summarise(rows)
    assert out["records_contradicting_registry"] == 1 and out["cases"] == ["A"]
    assert out["provider_failures"] == 1 and out["records_fully_settled"] == 1 and not out["void"]
