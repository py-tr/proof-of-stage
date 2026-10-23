from app.engine.agent_probe2 import summarise


def _row(arm: str, sql: str, result: object, ff: bool = False) -> dict:
    return {
        "arm": arm,
        "sql": sql,
        "result": result,
        "uses": {"fault_field": ff, "count_column": "lymph_nodes_positive" in sql},
    }


def test_the_claim_needs_the_column_and_the_expected_number_in_four_of_five() -> None:
    good = _row("treatment", "SELECT count(*) FROM t WHERE positive_nodes_checked > 0", "479")
    wrong_number = _row("treatment", "SELECT count(*) FROM t WHERE positive_nodes_checked > 0", "1")
    control = _row("control", "SELECT count(*) FROM t WHERE lymph_nodes_positive > 0", "476")
    out = summarise([good] * 4 + [wrong_number] + [control] * 5, 479)
    assert out["checked_column_used"] and out["treatment"]["reads_checked_column"] == 5
    out = summarise([good] * 3 + [wrong_number] * 2 + [control] * 5, 479)
    assert not out["checked_column_used"]
    assert (
        summarise([good] * 5 + [_row("control", "x", "1", ff=True)] * 2 + [control] * 3, 479)[
            "checked_column_used"
        ]
        is False
    )
