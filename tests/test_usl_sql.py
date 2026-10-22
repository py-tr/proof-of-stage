from __future__ import annotations

import re

from app.usl.model import SQL_DIR, USL_TABLES
from app.usl.sqltext import (
    extract_fingerprint,
    load_sql,
    load_statements,
    split_statements,
    sql_fingerprint,
    stamp_activation,
)

EXPECTED_COLUMNS = {
    "tumour_case": ["case_id", "primary_site", "site_key", "year_of_diagnosis"],
    "path_report": ["report_id", "case_id", "report_text"],
    "recorded_stage": [
        "case_id",
        "site_key",
        "pathologic_t",
        "pathologic_n",
        "pathologic_stage",
        "edition",
        "edition_code",
        "lymph_nodes_positive",
        "lymph_nodes_tested",
        "year_of_diagnosis",
        "n_main",
    ],
    "staging_rule": [
        "rule_id",
        "site",
        "element",
        "edition",
        "condition_text",
        "min_value",
        "max_value",
        "output",
        "cite",
    ],
    "derived_stage": [
        "case_id",
        "method",
        "field",
        "value",
        "quote",
        "quote_start",
        "quote_end",
        "model",
        "receipt_id",
        "created_at",
    ],
    "stage_check": [
        "case_id",
        "site_key",
        "edition_code",
        "recorded_t",
        "recorded_n",
        "recorded_stage",
        "recorded_n_main",
        "lymph_nodes_positive",
        "lymph_nodes_tested",
        "derived_n",
        "derived_n_main",
        "report_t",
        "report_n",
        "year_of_diagnosis",
        "edition_year_class",
        "reason_class",
        "report_n_main",
        "report_nodes_positive",
        "fault_field",
    ],
    "flag": [
        "flag_id",
        "case_id",
        "rule_id",
        "field",
        "recorded_value",
        "derived_value",
        "quote",
        "reason",
        "severity",
        "model",
        "receipt_id",
        "created_at",
    ],
}


def test_compile_block_stays_one_statement() -> None:
    sql = """
    COMPILE USL stage_audit DEPLOY NAMESPACE lightning.metastore.registry_audit DDL
    CREATE TABLE tumour_case (
      case_id varchar(64) NOT NULL PRIMARY KEY
    );
    CREATE TABLE flag (
      flag_id varchar(64) NOT NULL PRIMARY KEY
    );
    CREATE NAMESPACE IF NOT EXISTS lightning.metastore.registry_audit
    """
    parts = split_statements(sql)
    assert len(parts) == 2
    assert parts[0].lstrip().upper().startswith("COMPILE USL")
    assert "CREATE TABLE tumour_case" in parts[0]
    assert "CREATE TABLE flag" in parts[0]
    assert not parts[0].rstrip().endswith(";")
    assert parts[1].upper().startswith("CREATE NAMESPACE IF NOT EXISTS")


def test_semicolon_inside_a_string_is_not_a_split() -> None:
    parts = split_statements("SELECT 'O''Brien; still one' AS name; SELECT 1")
    assert parts == ["SELECT 'O''Brien; still one' AS name", "SELECT 1"]
    injected = "SELECT 'a\\'; DROP TABLE t' AS v"
    assert split_statements(injected) == [injected]


def test_compile_file_is_one_statement() -> None:
    parts = load_statements("030_compile_stage_audit.sql")
    assert len(parts) == 1
    statement = parts[0]
    assert statement.upper().startswith("COMPILE USL STAGE_AUDIT")
    for table in USL_TABLES:
        assert f"CREATE TABLE {table}" in statement
    assert not statement.rstrip().endswith(";")
    assert columns_by_table(load_sql("030_compile_stage_audit.sql")) == EXPECTED_COLUMNS


def test_descriptions_cover_every_column() -> None:
    descriptions = load_statements("040_descriptions.sql")
    assert len(descriptions) == len(EXPECTED_COLUMNS) + sum(
        len(columns) for columns in EXPECTED_COLUMNS.values()
    )
    text = "\n".join(descriptions)
    for table, columns in EXPECTED_COLUMNS.items():
        assert f"stage_audit.{table} SET TABLE DESCRIPTION" in text
        for column in columns:
            assert f"stage_audit.{table}.{column} SET COLUMN DESCRIPTION" in text
    assert ";" not in text


def test_activation_and_dq_files_are_single_statements() -> None:
    activates = [
        "050_activate_tumour_case.sql",
        "051_activate_path_report.sql",
        "052_activate_recorded_stage.sql",
        "053_activate_staging_rule.sql",
        "054_activate_derived_stage.sql",
        "055_activate_stage_check.sql",
        "056_activate_flag.sql",
    ]
    for name in activates:
        parts = load_statements(name)
        assert len(parts) == 1
        assert parts[0].upper().startswith("ACTIVATE USL TABLE")
    tumour = load_sql("050_activate_tumour_case.sql")
    recorded = load_sql("052_activate_recorded_stage.sql")
    assert "LATERAL VIEW explode" in tumour
    assert "LATERAL VIEW explode(data.hits)" in tumour
    assert "LATERAL VIEW explode(hit.diagnoses)" in recorded
    assert "LATERAL VIEW OUTER explode(diagnosis.pathology_details) AS pd" in recorded
    assert "pd.lymph_nodes_positive" in recorded
    assert "pd.lymph_nodes_tested" in recorded
    assert "MAX(" in recorded
    derived = load_sql("054_activate_derived_stage.sql")
    assert "UNION ALL" in derived
    assert "oa_pg.derived_extraction" in derived
    assert "sql_node_count" in derived
    check = load_sql("055_activate_stage_check.sql")
    assert "recorded_n_main" in check
    assert "report_t" in check
    assert "reason_class" in check
    assert "n_count_contradiction" in check
    assert "fault_field" in check
    assert "field = 'NPOS'" in check
    for name in (
        "060_dq_nodes_consistent.sql",
        "061_dq_stage_derivable_but_missing.sql",
        "062_dq_report_agrees.sql",
        "063_dq_edition_supported.sql",
        "064_dq_edition_matches_year.sql",
        "065_dq_fault_named.sql",
        "066_dq_fault_unresolved.sql",
    ):
        parts = load_statements(name)
        assert len(parts) == 1
        expression = re.split(r"\bAS\b", parts[0], maxsplit=1)[1]
        assert " OVER " not in expression.upper()
        assert not re.search(r"\b[A-Za-z_][\w]*\.[A-Za-z_]", expression)


def test_rest_and_filestore_sql_use_the_verified_clauses() -> None:
    rest = load_sql("021_rest_brca_cases.sql")
    assert "TCGA-BRCA" in rest
    assert "project.project_id" in rest
    assert "diagnoses.ajcc_pathologic_t" in rest
    assert "diagnoses.ajcc_pathologic_n" in rest
    assert "diagnoses.ajcc_pathologic_stage" in rest
    assert "diagnoses.ajcc_staging_system_edition" in rest
    assert "diagnoses.pathology_details.lymph_nodes_positive" in rest
    assert "diagnoses.pathology_details.lymph_nodes_tested" in rest
    assert "diagnoses.lymph_nodes_positive," not in rest
    assert "diagnoses.lymph_nodes_tested," not in rest
    assert "DROP LIGHTNING DATABASE TABLE GDC_REST.brca_cases_raw" in load_sql(
        "023_drop_brca_cases.sql"
    )
    assert "diagnoses.year_of_diagnosis" in rest
    assert "size=2000" in rest
    assert 'method "get"' in rest
    assert "HEADER (" in rest
    assert "BODY ()" in rest
    filestore = load_sql("011_filestore_staging_rules.sql")
    assert 'path "dffs://stage_audit/staging_rules.csv"' in filestore
    assert 'storage "dffs"' in filestore
    assert 'header "true"' in filestore
    assert 'multiLine "true"' in filestore
    assert 'escape "\\""' in filestore
    assert "CACHE TABLE GDC_REST.brca_cases_raw" in load_sql("022_cache_brca_cases.sql")


def test_activation_fingerprint_changes_with_the_sql() -> None:
    original = load_statements("052_activate_recorded_stage.sql")[0]
    stamped = stamp_activation(original)
    digest = sql_fingerprint(original)
    assert extract_fingerprint(stamped) == digest
    assert sql_fingerprint(stamped) == digest
    assert stamp_activation(stamped).count("uslfp:") == 1
    mutated = original.replace("pathology_details", "pathology_details_v2")
    assert sql_fingerprint(mutated) != digest


def test_shipped_sql_has_no_local_reference_paths() -> None:
    for path in SQL_DIR.glob("*.sql"):
        text = path.read_text(encoding="utf-8")
        assert ".ref" not in text
        assert "C:" not in text
        assert "Users" not in text


def columns_by_table(sql: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    current: str | None = None
    depth = 0
    for raw in sql.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if current is None:
            match = re.match(r"CREATE TABLE\s+(\w+)\s*\(", stripped)
            if match:
                current = match.group(1)
                tables[current] = []
                depth = stripped.count("(") - stripped.count(")")
            continue
        depth += stripped.count("(") - stripped.count(")")
        if depth <= 0:
            current = None
            continue
        if stripped.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "CONSTRAINT")):
            continue
        name = stripped.split()[0].rstrip(",")
        if name and name != ")":
            tables[current].append(name)
    return tables


def test_sql_string_uses_backslash_escapes() -> None:
    from app.usl.client import guard_select
    from app.usl.sqltext import sql_string

    assert sql_string("O'Brien") == "'O\\'Brien'"
    assert sql_string("a\\b") == "'a\\\\b'"
    # An escaped quote cannot end the literal, so this stays one SELECT.
    literal = sql_string("x'; DROP TABLE t; --")
    assert split_statements(f"SELECT {literal} AS v") == [f"SELECT {literal} AS v"]
    guard_select(f"SELECT {sql_string("it's")} AS v")
