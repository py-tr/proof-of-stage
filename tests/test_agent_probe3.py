from app.engine import agent_probe3 as p

CONTRACT = {
    "tables": [
        {
            "name": "a",
            "description": "Table A",
            "columnSpecs": [{"name": "x", "dataType": '"int"', "description": "X"}],
            "dqAnnotations": [{"name": "x_pos", "expression": "x >\n 0", "cte": ""}],
        },
        {
            "name": "b",
            "columnSpecs": [{"name": "y", "dataType": '"int"', "description": "Y"}],
            "dqAnnotations": [],
        },
    ]
}

RECORD = {
    "rules": {"stage_check": [["fault_named", "fault_field IS NULL OR fault_field NOT IN ('node_count')"]]},
    "integers": {
        "raw": 476,
        "checked": 479,
        "checked_fallback": 482,
        "correct_set": [479, 482, 557, 560],
        "filter": {"fault_named": 463, "ALL_7": 341},
    },
}


def test_rules_text_adds_only_rule_lines_under_their_table():
    text = p.rules_text(CONTRACT, "ns")
    assert text.split("\n") == [
        "TABLE ns.a: Table A",
        "  - x (int): X",
        "  DATA QUALITY RULES:",
        "    - x_pos: x > 0",
        "TABLE ns.b",
        "  - y (int): Y",
    ]
    control = p.schema_text(CONTRACT, "ns").split("\n")
    assert [line for line in text.split("\n") if line not in control] == text.split("\n")[2:4]


def test_code_correct_needs_fault_field_and_a_corrected_count():
    sql = "SELECT count(*) FROM t WHERE CASE WHEN fault_field = 'node_count' THEN a ELSE b END"
    assert p.code(sql, "479", RECORD) == "CORRECT"
    assert p.code(sql, "476", RECORD) == "RAW"


def test_code_checked_column_is_never_correct():
    sql = "SELECT count(*) FROM t WHERE positive_nodes_checked > 0 AND fault_field IS NULL"
    assert p.code(sql, "479", RECORD) == "CHECKED"
    assert p.code("SELECT count(*) FROM t WHERE positive_nodes_checked > 0", 479, RECORD) == "CHECKED"


def test_code_filter_by_copied_rule_or_filtered_integer():
    copied = "SELECT count(*) FROM t WHERE x > 0 AND (fault_field IS NULL OR  fault_field NOT IN ('node_count'))"
    assert p.code(copied, "479", RECORD) == "FILTER"
    assert p.code("SELECT count(*) FROM t WHERE whatever", "341", RECORD) == "FILTER"


def test_code_fallback_and_other():
    assert p.code("SELECT coalesce(positive_nodes_checked, lymph_nodes_positive)", "482.0", RECORD) == "CHECKED_FALLBACK"
    assert p.code("SELECT 1", None, RECORD) == "OTHER"


def test_summarise_claim_lines():
    def rows(arm, codes):
        return [{"arm": arm, "code": c} for c in codes]

    met = rows("control", ["RAW"] * 5) + rows("treatment", ["CORRECT"] * 4 + ["RAW"])
    assert p.summarise(met, RECORD)["rules_change_the_query"] is True
    near = rows("control", ["CORRECT"] + ["RAW"] * 4) + rows("treatment", ["CORRECT"] * 4 + ["RAW"])
    assert p.summarise(near, RECORD)["rules_change_the_query"] is False
    five = rows("control", ["CORRECT"] + ["RAW"] * 4) + rows("treatment", ["CORRECT"] * 5)
    assert p.summarise(five, RECORD)["rules_change_the_query"] is True
    failed = [{"arm": "treatment", "provider_failure": "x"}] * 3 + rows("treatment", ["CORRECT"] * 2)
    assert p.summarise(rows("control", ["RAW"] * 5) + failed, RECORD)["treatment"]["void"] is True
