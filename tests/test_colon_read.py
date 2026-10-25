from app.engine import colon_read as c


def test_colon_rule_and_impossible():
    assert c.colon_rule(0) == "N0" and c.colon_rule(3) == "N1" and c.colon_rule(12) == "N2"
    assert c.impossible("N2b", 0) and c.impossible("N1", 4)
    assert not c.impossible("N1c", 0)  # tumour deposits without a positive node
    assert not c.impossible("N2", 12)  # breast would say N3; colon has no N3
    assert not c.impossible("NX", 3)


def test_verdict_names_the_field_the_report_contradicts():
    assert c.verdict("N2b", 0, "N2B", "9") == "the report contradicts the count"
    assert c.verdict("N1", 4, "N2A", "4") == "the report contradicts the stage field"
    assert c.verdict("N1", 4, None, None) == "a person decides"
