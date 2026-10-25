from app.web.evidence import why_chain

CHECK = {
    "fault_field": "node_count",
    "reason_class": "n_count_contradiction",
    "recorded_n": "N2",
    "lymph_nodes_positive": "0.0",
    "derived_n": "pN0",
}
ACCEPTED = [{"field": "N", "quote": "Lymph node status: Positive 8 / 13 "}]


def test_why_chain_names_rule_quote_check_field_and_person():
    steps = why_chain(CHECK, ACCEPTED)
    assert len(steps) == 5
    assert "N2" in steps[0] and "both cannot be true" in steps[0]
    assert steps[1] == 'The report says: "Lymph node status: Positive 8 / 13"'
    assert "exact words" in steps[2]
    assert "count field" in steps[3]
    assert steps[4].startswith("A person decides")


def test_why_chain_without_a_quote_goes_to_a_person():
    steps = why_chain({**CHECK, "fault_field": "review"}, [])
    assert steps[-1] == "A person decides"


def test_no_chain_when_the_fields_agree():
    assert why_chain({"fault_field": None, "reason_class": "consistent"}, []) == []
