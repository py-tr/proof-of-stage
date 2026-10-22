from __future__ import annotations

from app.usl.dq import (
    FAULT_NODE_COUNT,
    FAULT_PATHOLOGIC_N,
    FAULT_REVIEW,
    fault_field,
    fault_named_valid,
    fault_unresolved_valid,
)
from app.usl.sqltext import load_sql


def _row(**overrides: object) -> dict[str, object]:
    # A 7th-edition contradiction: recorded N1, the GDC count 4 implies N2.
    row: dict[str, object] = {
        "edition_code": "7",
        "recorded_n": "N1a",
        "recorded_n_main": "N1",
        "lymph_nodes_positive": "4",
        "derived_n_main": "N2",
        "reason_class": "n_count_contradiction",
        "report_n_main": None,
        "report_nodes_positive": None,
    }
    row.update(overrides)
    return row


def test_report_agrees_with_recorded_n_accuses_the_count() -> None:
    # TCGA-A2-A0CV shape: the report says (2/18) positive and N1; the count field says 4.
    row = _row(report_n_main="N1", report_nodes_positive="2")
    assert fault_field(row) == FAULT_NODE_COUNT
    assert not fault_named_valid(row) and fault_unresolved_valid(row)


def test_report_agrees_with_the_count_accuses_the_n_field() -> None:
    row = _row(report_n_main="N2", report_nodes_positive="4")
    assert fault_field(row) == FAULT_PATHOLOGIC_N


def test_missing_n_filled_by_the_report_names_the_n_field() -> None:
    # TCGA-3C-AAAU shape: NX recorded, the report says 4 positive -> N2.
    row = _row(
        recorded_n="NX",
        recorded_n_main="NX",
        reason_class="n_missing_derivable",
        report_n_main="N2",
        report_nodes_positive="4",
    )
    assert fault_field(row) == FAULT_PATHOLOGIC_N


def test_no_verified_report_n_goes_to_review() -> None:
    row = _row()
    assert fault_field(row) == FAULT_REVIEW
    assert fault_named_valid(row) and not fault_unresolved_valid(row)


def test_report_count_equal_to_gdc_count_cannot_accuse_the_count() -> None:
    # The report's own count matches the GDC count but its N matches the recorded N:
    # the report contradicts itself, so a human decides.
    assert fault_field(_row(report_n_main="N1", report_nodes_positive="4")) == FAULT_REVIEW


def test_third_value_goes_to_review() -> None:
    assert fault_field(_row(report_n_main="N3", report_nodes_positive="12")) == FAULT_REVIEW


def test_consistent_cases_have_no_fault() -> None:
    row = _row(reason_class="consistent", report_n_main="N1")
    assert fault_field(row) is None
    assert fault_named_valid(row) and fault_unresolved_valid(row)


def test_sql_uses_the_same_three_outcomes() -> None:
    check = load_sql("055_activate_stage_check.sql")
    for outcome in (FAULT_NODE_COUNT, FAULT_PATHOLOGIC_N, FAULT_REVIEW):
        assert f"'{outcome}'" in check
    assert "fault_field IS NULL OR fault_field NOT IN ('node_count', 'pathologic_n')" in load_sql(
        "065_dq_fault_named.sql"
    )


def test_node_count_needs_a_verified_report_count() -> None:
    # N agreement alone: the registry abstracted N from this same report, so no accusation.
    assert fault_field(_row(report_n_main="N1")) == FAULT_REVIEW
