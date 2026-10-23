from app.engine.agent_probe import POINTER, summarise, uses, without_pointers


def test_only_the_pointer_sentences_are_removed() -> None:
    text = (
        "  - pathologic_n (varchar(64)): Registry N category (audited: where this field and the "
        "other node field cannot both be true, stage_check.fault_field names the field)\n"
        "  - fault_field (varchar(32)): the registry field the report evidence points to"
    )
    out = without_pointers(text)
    assert "audited" not in out and "fault_field (varchar(32))" in out
    assert POINTER.search(text)


def test_uses_reads_which_evidence_a_query_counts_from() -> None:
    u = uses("SELECT count(*) FROM t WHERE recorded_n_main <> 'N0' AND fault_field IS NULL")
    assert u["fault_field"] and u["n_column"] and not u["count_column"]


def test_the_claim_needs_four_of_five_with_and_at_most_one_without() -> None:
    def row(arm, ff):
        return {"arm": arm, "uses": {"fault_field": ff, "n_column": True, "count_column": False}}

    rows = [row("with", True)] * 4 + [row("with", False)] + [row("without", False)] * 5
    assert summarise(rows)["pointer_changes_the_query"]
    rows = [row("with", True)] * 3 + [row("with", False)] * 2 + [row("without", False)] * 5
    assert not summarise(rows)["pointer_changes_the_query"]
    rows = (
        [row("with", True)] * 5
        + [{"arm": "without", "provider_failure": "x"}] * 3
        + [row("without", False)] * 2
    )
    assert summarise(rows)["without"]["void"] and not summarise(rows)["pointer_changes_the_query"]
