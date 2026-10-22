from __future__ import annotations

import pytest

from app.usl.client import (
    SqlGuardError,
    format_invalid_records,
    guard_select,
    insert_extraction_sql,
    insert_flag_sql,
    parse_dq_counts,
    run_dq,
    select,
)
from app.usl.model import EXTRACTION_COLUMNS, FLAG_COLUMNS
from app.usl.sqltext import split_statements
from app.zetaris import SqlResult


def test_guard_rejects_dml_and_foreign_names() -> None:
    with pytest.raises(SqlGuardError):
        guard_select("DELETE FROM oa_pg.flag_log")
    with pytest.raises(SqlGuardError):
        guard_select("INSERT INTO oa_pg.flag_log (flag_id) SELECT 'x'")
    with pytest.raises(SqlGuardError):
        guard_select("SELECT * FROM crm_pg.customers")
    with pytest.raises(SqlGuardError):
        guard_select("SELECT * FROM secrets")
    with pytest.raises(SqlGuardError):
        guard_select("SELECT * FROM oa_pg.flag_log; DROP TABLE oa_pg.flag_log")
    with pytest.raises(SqlGuardError):
        guard_select("UPDATE oa_pg.flag_log SET reason = 'x'")


def test_guard_allows_registry_reads() -> None:
    guard_select("SELECT case_id FROM lightning.metastore.registry_audit.stage_audit.tumour_case")
    guard_select("SELECT * FROM REG_FILES.staging_rules")
    guard_select("SELECT * FROM GDC_REST.brca_cases_raw")
    guard_select("SELECT quote FROM oa_pg.flag_log WHERE quote = 'INSERT INTO secret'")
    guard_select("LOAD USL stage_audit NAMESPACE lightning.metastore.registry_audit")
    guard_select(
        "RUN DQ nodes_consistent TABLE lightning.metastore.registry_audit.stage_audit.stage_check"
    )
    guard_select(
        "SHOW DQ INVALID RECORD nodes_consistent "
        "TABLE lightning.metastore.registry_audit.stage_audit.stage_check"
    )
    guard_select(
        "RUN DQ stage_derivable_but_missing TABLE "
        "lightning.metastore.registry_audit.stage_audit.stage_check"
    )
    with pytest.raises(SqlGuardError):
        guard_select(
            "RUN DQ other_rule TABLE lightning.metastore.registry_audit.stage_audit.stage_check"
        )


@pytest.mark.asyncio
async def test_select_does_not_run_rejected_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> SqlResult:
        raise AssertionError("ran sql")

    monkeypatch.setattr("app.usl.client.run_sql", fail)
    with pytest.raises(SqlGuardError):
        await select("DELETE FROM oa_pg.flag_log")


def test_insert_flag_escapes_quotes_and_stays_one_statement() -> None:
    payload = "N1'); DROP TABLE oa_pg.flag_log; --"
    sql = insert_flag_sql(
        flag_id="flag-1",
        case_id="case-1",
        rule_id="nodes_consistent",
        field="N",
        recorded_value="N1",
        derived_value="N2",
        quote=payload,
        reason='he said "drop"',
        severity="review",
        model="nvidia/nemotron",
        receipt_id="rcpt-1",
        created_at="2026-01-01T00:00:00Z",
    )
    parts = split_statements(sql)
    assert len(parts) == 1
    assert parts[0].startswith("INSERT INTO oa_pg.flag_log")
    assert "N1\\'); DROP TABLE oa_pg.flag_log; --" in sql
    assert "N1'); DROP TABLE" not in sql
    assert "WHERE NOT EXISTS" in sql
    for column in FLAG_COLUMNS:
        assert column in sql.split("SELECT", 1)[0]
    backslash = insert_flag_sql(
        flag_id="flag-2",
        case_id="case-1",
        rule_id="nodes_consistent",
        quote="\\'; DROP TABLE oa_pg.flag_log; --",
        created_at="2026-01-01T00:00:00Z",
    )
    assert len(split_statements(backslash)) == 1
    assert backslash.startswith("INSERT INTO oa_pg.flag_log")


def test_insert_extraction_rejects_non_integers_and_lists_every_column() -> None:
    with pytest.raises(TypeError):
        insert_extraction_sql(
            case_id="case-1",
            method="nemotron",
            field="N",
            quote_start="1; DROP TABLE oa_pg.flag_log",  # type: ignore[arg-type]
            created_at="2026-01-01T00:00:00Z",
        )
    with pytest.raises(TypeError):
        insert_extraction_sql(
            case_id="case-1",
            method="nemotron",
            field="N",
            quote_start=True,  # type: ignore[arg-type]
            created_at="2026-01-01T00:00:00Z",
        )
    sql = insert_extraction_sql(
        case_id="case-1",
        method="nemotron",
        field="N",
        value="N1",
        quote="O'Brien N1",
        quote_start=4,
        quote_end=6,
        model="nvidia/nemotron",
        receipt_id="rcpt-1",
        created_at="2026-01-01T00:00:00Z",
    )
    assert len(split_statements(sql)) == 1
    assert "O\\'Brien" in sql
    assert "WHERE existing.case_id = " in sql
    assert "existing.method = " in sql
    assert "existing.field = " in sql
    for column in EXTRACTION_COLUMNS:
        assert column in sql.split("SELECT", 1)[0]


@pytest.mark.asyncio
async def test_run_dq_parses_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def fake(sql: str, limit: int = 1000) -> SqlResult:
        seen.append(sql)
        return SqlResult(
            [["nodes_consistent", "stage_check", "Custom Data Quality", "1097", "963", "134"]],
            ["name", "table", "type", "total_record", "valid_record", "invalid_record"],
        )

    monkeypatch.setattr("app.usl.client.run_sql", fake)
    counts = await run_dq("nodes_consistent")
    assert counts.total == 1097
    assert counts.valid == 963
    assert counts.invalid == 134
    assert seen[0].startswith("RUN DQ nodes_consistent TABLE ")
    with pytest.raises(SqlGuardError):
        await run_dq("drop_table")


def test_parse_dq_counts_accepts_short_column_names() -> None:
    result = SqlResult([["10", "8", "2"]], ["total", "valid", "invalid"])
    counts = parse_dq_counts("report_agrees", result)
    assert (counts.total, counts.valid, counts.invalid) == (10, 8, 2)


def test_format_invalid_records_is_a_table() -> None:
    result = SqlResult(
        [["TCGA-AN-A0XO", "7", "N1A", "0", "pN0"]],
        ["case_id", "edition_code", "recorded_n", "lymph_nodes_positive", "derived_n"],
    )
    text = format_invalid_records(result, limit=10)
    assert "case_id" in text.splitlines()[0]
    assert "edition" in text.splitlines()[0]
    assert "recorded N" in text.splitlines()[0]
    assert "TCGA-AN-A0XO" in text
    assert "pN0" in text


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT * FROM "crm_pg"."customers"',
        "SELECT * FROM `crm_pg`.`customers`",
        'SELECT c.* FROM REG_FILES.staging_rules s JOIN "secrets" c ON 1 = 1',
        "SELECT reflect('java.lang.System', 'getenv', 'ZETARIS_API_KEY')",
        "SELECT java_method('java.lang.System', 'getenv', 'X') FROM REG_FILES.staging_rules",
        "SELECT * FROM lightning.metastore.other_ns.other_usl.t",
        "SELECT * FROM oa_pg.some_other_table",
        "RUN DQ nodes_consistent",
        "RUN DQ other_rule",
        "RUN DQ nodes_consistent TABLE lightning.metastore.registry_audit.stage_audit.flag",
    ],
)
def test_guard_blocks_review_bypasses(sql: str) -> None:
    with pytest.raises(SqlGuardError):
        guard_select(sql)


def test_guard_allows_quotes_inside_string_literals() -> None:
    guard_select("SELECT quote FROM oa_pg.flag_log WHERE quote = 'the \"chest wall\" is clear'")
