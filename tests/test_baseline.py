from app.engine.baseline import judge, score

REPORT = "FINAL DIAGNOSIS: Metastatic carcinoma in two of fourteen axillary lymph nodes (2/14)."


def test_judge_checks_only_that_the_quote_is_in_the_report() -> None:
    good = '{"fault": "pathologic_n", "quote": "two of fourteen axillary lymph nodes"}'
    found = judge(good, REPORT)
    assert found["fault"] == "pathologic_n" and found["quote_in_report"]
    made_up = judge('{"fault": "node_count", "quote": "three of fourteen nodes"}', REPORT)
    assert made_up["fault"] == "node_count" and not made_up["quote_in_report"]
    assert judge("no json", REPORT) == {"fault": None, "parsed": False, "quote_in_report": False}
    assert judge('{"fault": "both"}', REPORT)["fault"] is None


def test_score_counts_failures_as_misses_and_b0_always_blames_n() -> None:
    labels = {"A": {"field": "node_count"}, "B": {"field": "pathologic_n"}, "C": {"field": None}}
    m0 = [
        {
            "case": "A",
            "off": {"error": "x"},
            "4k": {"fault": "node_count", "parsed": True, "quote_in_report": True},
        },
        {
            "case": "B",
            "off": {"fault": "review", "parsed": True, "quote_in_report": False},
            "4k": {"fault": "pathologic_n", "parsed": True, "quote_in_report": True},
        },
    ]
    out = score(m0, labels, {"A": "node_count", "B": "review"})
    assert out["labelled"] == 2
    assert out["A0_ours"]["agree"] == 1 and out["B0_rule_alone"]["agree"] == 1
    assert out["M0_4k"]["agree"] == 2 and out["M0_off"]["agree"] == 0
    assert out["M0_off"]["provider_failures"] == 1 and out["M0_off"]["quote_not_in_report"] == 1
