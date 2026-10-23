from __future__ import annotations

import json
from pathlib import Path

from app.usl.dq import (
    REASON_AMBIGUOUS_MICROMET,
    REASON_CONSISTENT,
    REASON_CONTRADICTION,
    REASON_COUNT_MISSING,
    REASON_MISSING_DERIVABLE,
    nodes_consistent_valid,
    reason_class,
    stage_derivable_but_missing_valid,
)
from app.usl.sqltext import load_sql

FIXTURE = Path(__file__).parent / "fixtures" / "dq_nodes_consistent_rows.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_nodes_consistent_invalid_set_matches_fixture() -> None:
    payload = _payload()
    expected = set(payload["expected_invalid_case_ids"])
    assert expected == {"TCGA-AN-A0XO", "TCGA-AN-A0XW", "TCGA-AN-A0XS", "TCGA-E9-A3X8"}
    invalid = {row["case_id"] for row in payload["rows"] if not nodes_consistent_valid(row)}
    assert invalid == expected


def test_null_count_and_micromet_are_valid_for_nodes_consistent() -> None:
    payload = _payload()
    by_id = {row["case_id"]: row for row in payload["rows"]}
    assert nodes_consistent_valid(by_id["NULL-COUNT-N1"])
    assert nodes_consistent_valid(by_id["MICROMET-N1MI"])
    assert nodes_consistent_valid(by_id["ITC-N0-I+"])
    assert nodes_consistent_valid(by_id["NX-WITH-COUNT"])
    assert nodes_consistent_valid(by_id["EDITION-8-MISMATCH"])
    assert reason_class(by_id["NULL-COUNT-N1"]) == REASON_COUNT_MISSING
    assert reason_class(by_id["MICROMET-N1MI"]) == REASON_AMBIGUOUS_MICROMET
    assert reason_class(by_id["NX-WITH-COUNT"]) == REASON_MISSING_DERIVABLE
    assert reason_class(by_id["MATCHING-N1"]) == REASON_CONSISTENT
    assert reason_class(by_id["TCGA-AN-A0XO"]) == REASON_CONTRADICTION


def test_stage_derivable_but_missing_flags_nx_with_a_count() -> None:
    payload = _payload()
    by_id = {row["case_id"]: row for row in payload["rows"]}
    assert not stage_derivable_but_missing_valid(by_id["NX-WITH-COUNT"])
    assert stage_derivable_but_missing_valid(by_id["TCGA-AN-A0XO"])
    assert stage_derivable_but_missing_valid(by_id["NULL-COUNT-N1"])


def test_registered_sql_matches_the_python_checks() -> None:
    nodes = load_sql("060_dq_nodes_consistent.sql")
    missing = load_sql("061_dq_stage_derivable_but_missing.sql")
    assert "lymph_nodes_positive IS NOT NULL" in nodes
    assert "N1MI" in nodes
    assert "N0(I+)" in nodes
    assert "N0(MOL+)" in nodes
    assert "recorded_n_main <> 'NX'" in nodes
    assert "coalesce(edition_code, '') IN ('6', '7')" in nodes
    assert "recorded_n_main = 'NX'" in missing
    assert "lymph_nodes_positive IS NOT NULL" in missing


def test_a_missing_edition_is_not_derivable() -> None:
    # TCGA-BH-A0H6: no edition, 0 of 0 nodes, NX. SQL's NULL IN (...) once made it invalid.
    from app.usl.dq import stage_derivable_but_missing_valid

    row = {"edition_code": None, "lymph_nodes_positive": "0.0", "recorded_n_main": "NX"}
    assert stage_derivable_but_missing_valid(row)
    sql = load_sql("061_dq_stage_derivable_but_missing.sql")
    assert "coalesce(edition_code, '') IN ('6', '7')" in sql
