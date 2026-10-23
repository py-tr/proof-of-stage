"""Idempotent build, status, data-quality run, and teardown of stage_audit."""

from __future__ import annotations

import json
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from app.usl.client import format_invalid_records, invalid_records, run_dq, run_key_dq
from app.usl.errors import SetupError, public_error
from app.usl.files import require_zetaris_config, upload_csvs
from app.usl.model import (
    DQ_RULE_TABLES,
    DQ_RULES,
    FILE_DB,
    FILE_STORE_DIR,
    KEY_RULES,
    NAMESPACE,
    PARSE_BLOCK_COLUMNS,
    PARSE_BLOCKS_CSV,
    PG_SOURCE,
    REPORTS_CSV,
    REST_DB,
    ROOT,
    RULES_CSV,
    USL_FQN,
    USL_NAME,
    USL_TABLES,
    table_fqn,
)
from app.usl.postgres import apply_ddl, discover_user
from app.usl.rules import (
    FIELDNAMES,
    ensure_csv,
    ensure_path_reports_file,
    require_columns,
    write_staging_rules,
)
from app.usl.sqltext import (
    extract_fingerprint,
    load_sql,
    load_statements,
    sql_fingerprint,
    stamp_activation,
)
from app.zetaris import SqlResult, ZetarisError, run_sql

# Newest stage_check column: if the deployed USL lacks it, the schema changed and the
# USL is recompiled (the Postgres tables and the cached sources are kept).
SCHEMA_MARKER = "positive_nodes_checked"

_ACTIVATE = (
    "050_activate_tumour_case.sql",
    "051_activate_path_report.sql",
    "052_activate_recorded_stage.sql",
    "053_activate_staging_rule.sql",
    "054_activate_derived_stage.sql",
    "055_activate_stage_check.sql",
    "056_activate_flag.sql",
    "057_activate_parse_block.sql",
)
_DQ_FILES = (
    "060_dq_nodes_consistent.sql",
    "061_dq_stage_derivable_but_missing.sql",
    "062_dq_report_agrees.sql",
    "063_dq_edition_supported.sql",
    "064_dq_edition_matches_year.sql",
    "065_dq_fault_named.sql",
    "066_dq_fault_unresolved.sql",
    "067_dq_nodes_within_tested.sql",
)
_REGISTER = (
    ("derived_extraction", "004_register_derived_extraction.sql"),
    ("flag_log", "005_register_flag_log.sql"),
)
_FILE_TABLES = (
    ("staging_rules", "011_filestore_staging_rules.sql", "013_uncache_staging_rules.sql"),
    ("path_reports", "012_filestore_path_reports.sql", "014_uncache_path_reports.sql"),
    ("parse_blocks", "015_filestore_parse_blocks.sql", "016_uncache_parse_blocks.sql"),
)
_YES_VALUES = {"true", "yes", "1", "y", "activated"}
_REST_TABLE = "brca_cases_raw"
_PATHOLOGY_PROBE = (
    "SELECT CAST(pd.lymph_nodes_positive AS STRING) AS lymph_nodes_positive "
    f"FROM {REST_DB}.{_REST_TABLE} "
    "LATERAL VIEW explode(data.hits) AS hit "
    "LATERAL VIEW explode(hit.diagnoses) AS diagnosis "
    "LATERAL VIEW OUTER explode(diagnosis.pathology_details) AS pd "
    "LIMIT 1"
)
_CACHE_UNLISTED = "Spark CACHE TABLE is not listed by SHOW CACHE TABLES"


def _log(message: str) -> None:
    sys.stdout.write(message + "\n")


def present(result: SqlResult, name: str) -> bool:
    target = name.lower()
    for cell in _cells(result):
        text = cell.strip().lower()
        if text == target or text.endswith("." + target):
            return True
    return False


def usl_listed(result: SqlResult) -> bool:
    """True when the listing shows stage_audit or one of its tables."""
    if present(result, USL_NAME):
        return True
    return any(present(result, table) for table in USL_TABLES)


def activation_of(result: SqlResult, table: str) -> tuple[bool, str]:
    """Read present/activated from SHOW NAMESPACES OR TABLES (name, activated, …)."""
    hits = [_activation_row(row, table) for row in _row_dicts(result)]
    hits = [row for row in hits if row is not None]
    if not hits:
        return False, "no"
    row = hits[0]
    raw = row.get("activated", "")
    if not raw:
        return True, "unknown"
    flag = "yes" if raw.strip().lower() in _YES_VALUES else "no"
    return True, flag


async def setup() -> None:
    """Create any missing stage_audit objects. Existing objects are left in place."""
    require_zetaris_config()
    await _step("postgres tables", "002_postgres_derived_extraction.sql", _create_postgres)
    await _step(
        "register postgres tables",
        "004_register_derived_extraction.sql",
        _register_pg_tables,
    )
    await _step("staging rules csv", None, _prepare_files)
    await _step("upload filestore", None, _upload_files)
    await _step("lightning database REG_FILES", "010_lightning_reg_files.sql", _ensure_file_db)
    await _step("filestore tables", "011_filestore_staging_rules.sql", _ensure_filestores)
    await _step("lightning database GDC_REST", "020_lightning_gdc.sql", _ensure_rest_db)
    rest_changed = await _step("rest table brca_cases_raw", "021_rest_brca_cases.sql", _ensure_rest)

    async def cache_step() -> None:
        await _ensure_cache(rest_changed)

    await _step("cache brca_cases_raw", "022_cache_brca_cases.sql", cache_step)
    await _step("namespace", "001_namespace.sql", _ensure_namespace)
    usl_created = await _step("compile usl stage_audit", "030_compile_stage_audit.sql", _ensure_usl)
    if usl_created or descriptions_changed():
        await _step("descriptions", "040_descriptions.sql", _apply_descriptions)
        record_descriptions()
    else:
        _log("descriptions skipped (usl exists)")
    await _step("activate usl tables", "050_activate_tumour_case.sql", _activate_tables)
    await _step("register dq", "060_dq_nodes_consistent.sql", _ensure_dq)
    _log("setup complete")


async def status_report() -> str:
    """One line per object: present, and activated for USL tables."""
    lines: list[str] = []
    root, root_error = await _try_sql("SHOW NAMESPACES OR TABLES IN lightning.metastore")
    namespace_on = root_error is None and present(root, "registry_audit")
    lines.append(_status_line(NAMESPACE, namespace_on, "n/a", None if namespace_on else root_error))

    inner = SqlResult([], [])
    inner_error = None
    if namespace_on:
        inner, inner_error = await _try_sql(f"SHOW NAMESPACES OR TABLES IN {NAMESPACE}")
    usl_on = inner_error is None and namespace_on and usl_listed(inner)
    lines.append(_status_line(USL_FQN, usl_on, "n/a", inner_error))

    tables = SqlResult([], [])
    tables_error = None
    if usl_on:
        tables, tables_error = await _try_sql(f"SHOW NAMESPACES OR TABLES IN {USL_FQN}")
    for table in USL_TABLES:
        if not usl_on or tables_error:
            lines.append(
                _status_line(
                    table_fqn(table),
                    False,
                    "unknown" if tables_error else "no",
                    tables_error,
                )
            )
            continue
        there, activated = activation_of(tables, table)
        lines.append(_status_line(table_fqn(table), there, activated, None))

    databases, db_error = await _try_sql("SHOW LIGHTNING DATABASES")
    for database, table_names in (
        (FILE_DB, ("staging_rules", "path_reports", "parse_blocks")),
        (REST_DB, (_REST_TABLE,)),
    ):
        db_on = db_error is None and present(databases, database)
        lines.append(_status_line(database, db_on, "n/a", db_error))
        listed = SqlResult([], [])
        list_error = None
        if db_on:
            listed, list_error = await _try_sql(f"SHOW LIGHTNING TABLES {database}")
        for table in table_names:
            if list_error or not db_on:
                flag = "unknown" if list_error or db_error else "no"
                lines.append(
                    _status_line(
                        f"{database}.{table}",
                        False,
                        flag if flag == "unknown" else "n/a",
                        list_error or db_error,
                    )
                )
                continue
            lines.append(_status_line(f"{database}.{table}", present(listed, table), "n/a", None))

    cached, cache_error = await _try_sql("SHOW CACHE TABLES")
    if cache_error:
        lines.append(_status_line(f"cache.{REST_DB}.{_REST_TABLE}", False, "unknown", cache_error))
    elif present(cached, _REST_TABLE):
        lines.append(_status_line(f"cache.{REST_DB}.{_REST_TABLE}", True, "n/a", None))
    else:
        lines.append(_status_line(f"cache.{REST_DB}.{_REST_TABLE}", False, "n/a", _CACHE_UNLISTED))

    pg, pg_error = await _try_sql(f"SHOW DATASOURCE TABLES {PG_SOURCE}")
    for table in ("derived_extraction", "flag_log"):
        if pg_error:
            lines.append(_status_line(f"{PG_SOURCE}.{table}", False, "unknown", pg_error))
        else:
            lines.append(_status_line(f"{PG_SOURCE}.{table}", present(pg, table), "n/a", None))

    rules = SqlResult([], [])
    rule_error = None
    if usl_on:
        rules, rule_error = await _try_sql(f"LIST DQ USL {USL_FQN}")
    for rule in DQ_RULES:
        if rule_error:
            lines.append(_status_line(f"dq.{rule}", False, "unknown", rule_error))
        elif not usl_on:
            lines.append(_status_line(f"dq.{rule}", False, "n/a", None))
        else:
            lines.append(_status_line(f"dq.{rule}", present(rules, rule), "n/a", None))
    return "\n".join(lines) + "\n"


async def dq_report(invalid_rule: str | None = None, limit: int = 50) -> str:
    if invalid_rule:
        result = await invalid_records(invalid_rule, limit=limit)
        return format_invalid_records(result, limit=limit)
    lines: list[str] = []
    for rule in DQ_RULES:
        counts = await run_dq(rule)
        lines.append(
            f"{counts.rule} [{DQ_RULE_TABLES[rule]}] total={counts.total} valid={counts.valid} "
            f"invalid={counts.invalid}"
        )
    lines.append("key rules generated by Zetaris from the DDL:")
    for name, table in KEY_RULES:
        for row in await run_key_dq(name, table):
            lines.append(
                f"  {name} [{table}] {row.get('type', '')}: total={row.get('total_record')} "
                f"valid={row.get('valid_record')} invalid={row.get('invalid_record')}"
            )
    lines.append(
        "  (composite keys run via their first column; their listed names, e.g. "
        "case_id,page_no,block_index, do not parse in RUN DQ)"
    )
    return "\n".join(lines) + "\n"


async def teardown() -> None:
    """Remove only registry_audit, REG_FILES, GDC_REST, and the two Postgres tables."""
    require_zetaris_config()
    root, root_error = await _try_sql("SHOW NAMESPACES OR TABLES IN lightning.metastore")
    if root_error:
        raise ZetarisError(root_error)
    if present(root, "registry_audit"):
        inner = await run_sql(f"SHOW NAMESPACES OR TABLES IN {NAMESPACE}")
        if usl_listed(inner):
            listed = await run_sql(f"LIST DQ USL {USL_FQN}")
            for statement in load_statements("070_remove_dq.sql"):
                if any(present(listed, rule) and rule in statement for rule in DQ_RULES):
                    _log("remove dq rule")
                    await run_sql(statement)
            _log("remove usl stage_audit")
            await run_sql(load_statements("071_remove_usl.sql")[0])
        _log("drop namespace registry_audit")
        await run_sql(load_statements("072_drop_namespace.sql")[0])
    databases = await run_sql("SHOW LIGHTNING DATABASES")
    if present(databases, REST_DB):
        _log("drop lightning database GDC_REST")
        await run_sql(load_statements("074_drop_gdc.sql")[0])
    if present(databases, FILE_DB):
        _log("drop lightning database REG_FILES")
        await run_sql(load_statements("073_drop_reg_files.sql")[0])
    user, secrets = discover_user()
    _log("drop postgres tables")
    apply_ddl(user, load_sql("080_postgres_drop.sql"), secrets)
    _log("teardown complete")


async def _step(step: str, sql_file: str | None, action: Callable[[], Awaitable[Any] | Any]) -> Any:
    try:
        result = action()
        if isinstance(result, Awaitable):
            return await result
        return result
    except SetupError as exc:
        if exc.step:
            raise
        raise SetupError(str(exc), step=step, sql_file=sql_file) from exc
    except ZetarisError as exc:
        raise SetupError(public_error(str(exc)), step=step, sql_file=sql_file) from exc
    except Exception as exc:
        raise SetupError(
            public_error(f"{type(exc).__name__}: {exc}"),
            step=step,
            sql_file=sql_file,
        ) from exc


async def _create_postgres() -> None:
    user, secrets = discover_user()
    apply_ddl(user, _postgres_create_sql(), secrets)


def _postgres_create_sql() -> str:
    parts = [
        load_sql("002_postgres_derived_extraction.sql").strip(),
        load_sql("003_postgres_flag_log.sql").strip(),
    ]
    return "\n".join(parts) + "\n"


def _prepare_files() -> None:
    write_staging_rules(RULES_CSV)
    ensure_path_reports_file(REPORTS_CSV)
    ensure_csv(PARSE_BLOCKS_CSV, PARSE_BLOCK_COLUMNS)
    require_columns(RULES_CSV, FIELDNAMES)


async def _upload_files() -> None:
    _log(f"upload file-store/{FILE_STORE_DIR}")
    await upload_csvs(
        [
            ("staging_rules.csv", RULES_CSV.read_bytes()),
            ("path_reports.csv", REPORTS_CSV.read_bytes()),
            ("parse_blocks.csv", PARSE_BLOCKS_CSV.read_bytes()),
        ]
    )


async def _register_pg_tables() -> None:
    listed = await run_sql(f"SHOW DATASOURCE TABLES {PG_SOURCE}")
    for table, filename in _REGISTER:
        if present(listed, table):
            _log(f"datasource table {table} exists")
            continue
        _log(f"register datasource table {table}")
        await run_sql(load_statements(filename)[0])


async def _ensure_file_db() -> None:
    await _ensure_database(FILE_DB, "010_lightning_reg_files.sql")


async def _ensure_rest_db() -> None:
    await _ensure_database(REST_DB, "020_lightning_gdc.sql")


async def _ensure_filestores() -> None:
    for table, create_file, uncache_file in _FILE_TABLES:
        await _ensure_filestore(table, create_file, uncache_file)


async def _ensure_database(name: str, filename: str) -> None:
    listed = await run_sql("SHOW LIGHTNING DATABASES")
    if present(listed, name):
        _log(f"lightning database {name} exists")
        return
    _log(f"create lightning database {name}")
    await run_sql(load_statements(filename)[0])


async def _ensure_filestore(table: str, create_file: str, uncache_file: str) -> None:
    listed = await run_sql(f"SHOW LIGHTNING TABLES {FILE_DB}")
    if present(listed, table):
        _log(f"refresh filestore {table}")
        await run_sql(load_statements(uncache_file)[0])
        return
    _log(f"create filestore {table}")
    await run_sql(load_statements(create_file)[0])


async def _ensure_rest() -> bool:
    """Create or rebuild brca_cases_raw when pathology_details is missing. True if created."""
    listed = await run_sql(f"SHOW LIGHTNING TABLES {REST_DB}")
    if present(listed, _REST_TABLE):
        if await _rest_fields_current():
            _log("rest table brca_cases_raw exists")
            return False
        _log("drop rest table brca_cases_raw (field list changed)")
        await _exec("drop rest table brca_cases_raw", "023_drop_brca_cases.sql")
    _log("create rest table brca_cases_raw")
    await _exec("create rest table brca_cases_raw", "021_rest_brca_cases.sql")
    return True


async def _rest_fields_current() -> bool:
    described, describe_error = await _try_sql(f"DESCRIBE DATASOURCE TABLE {REST_DB}.{_REST_TABLE}")
    if describe_error is None and _cells_mention(described, "pathology_details"):
        return True
    if describe_error is None and _cells_mention(described, "lymph_nodes_positive"):
        if not _cells_mention(described, "pathology_details"):
            return False
    try:
        await run_sql(_PATHOLOGY_PROBE, limit=1)
    except ZetarisError as exc:
        if _missing_pathology_field(str(exc)):
            return False
        raise
    return True


async def _ensure_cache(rest_changed: bool) -> None:
    if not rest_changed:
        _log("cache brca_cases_raw skipped (rest table already current)")
        return
    _log("cache brca_cases_raw")
    await run_sql(load_statements("022_cache_brca_cases.sql")[0])


async def _ensure_namespace() -> None:
    _log("namespace")
    await run_sql(load_statements("001_namespace.sql")[0])


async def _ensure_usl() -> bool:
    listed = await run_sql(f"SHOW NAMESPACES OR TABLES IN {NAMESPACE}")
    if usl_listed(listed):
        if await _stage_check_is_current():
            _log("usl stage_audit exists")
            return False
        _log("replace usl stage_audit (schema changed)")
        await _exec("remove usl stage_audit", "071_remove_usl.sql")
    _log("compile usl stage_audit")
    await _exec("compile usl stage_audit", "030_compile_stage_audit.sql")
    return True


DESCRIPTIONS_STAMP = ROOT / "data" / "state" / "usl_descriptions.sha256"


def _descriptions_digest() -> str:
    import hashlib

    return hashlib.sha256(load_sql("040_descriptions.sql").encode("utf-8")).hexdigest()


def descriptions_changed() -> bool:
    """True when 040_descriptions.sql differs from what was last applied (so they never drift)."""
    if not DESCRIPTIONS_STAMP.exists():
        return True
    return DESCRIPTIONS_STAMP.read_text(encoding="utf-8").strip() != _descriptions_digest()


def record_descriptions() -> None:
    DESCRIPTIONS_STAMP.parent.mkdir(parents=True, exist_ok=True)
    DESCRIPTIONS_STAMP.write_text(_descriptions_digest() + "\n", encoding="utf-8")


async def _apply_descriptions() -> None:
    descriptions = load_statements("040_descriptions.sql")
    _log(f"descriptions {len(descriptions)}")
    for statement in descriptions:
        await run_sql(statement)


async def _activate_tables() -> None:
    listed, listed_error = await _try_sql(f"SHOW NAMESPACES OR TABLES IN {USL_FQN}")
    if listed_error:
        listed = SqlResult([], [])
    queries = await _stored_activate_queries()
    for filename in _ACTIVATE:
        statement = load_statements(filename)[0]
        table = activated_table(statement)
        digest = sql_fingerprint(statement)
        _, activated = activation_of(listed, table)
        stored = queries.get(table, "")
        if activated == "yes" and _activation_matches(stored, digest):
            _log(f"activate {table} skipped (already activated)")
            continue
        _log(f"activate {table}")
        await _exec(f"activate {table}", filename, stamp_activation(statement))


async def _stored_activate_queries() -> dict[str, str]:
    result, error = await _try_sql(f"LOAD USL {USL_NAME} NAMESPACE {NAMESPACE}")
    if error or not result.rows:
        return {}
    contract = _contract_from_result(result)
    if not isinstance(contract, dict):
        return {}
    found: dict[str, str] = {}
    tables = contract.get("tables")
    if not isinstance(tables, list):
        return {}
    for item in tables:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("table") or item.get("tableName")
        query = (
            item.get("activateQuery")
            or item.get("activationQuery")
            or item.get("activatedQuery")
            or item.get("query")
        )
        if isinstance(name, str) and isinstance(query, str):
            found[name] = query
    return found


def _activation_matches(stored_query: str, digest: str) -> bool:
    """Skip a live table unless a stored fingerprint proves the SQL changed."""
    stored_fp = extract_fingerprint(stored_query) if stored_query else None
    if stored_fp is None:
        return True
    return stored_fp == digest


async def _exec(step: str, sql_file: str, sql: str | None = None) -> SqlResult:
    statement = load_statements(sql_file)[0] if sql is None else sql
    try:
        return await run_sql(statement)
    except ZetarisError as exc:
        raise SetupError(public_error(str(exc)), step=step, sql_file=sql_file) from exc


async def _ensure_dq() -> None:
    listed = await run_sql(f"LIST DQ USL {USL_FQN}")
    for filename in _DQ_FILES:
        statement = load_statements(filename)[0]
        rule = next(rule for rule in DQ_RULES if rule in statement)
        if present(listed, rule):
            _log(f"replace dq {rule}")
            await run_sql(f"REMOVE DQ {rule} TABLE {table_fqn(DQ_RULE_TABLES[rule])}")
        else:
            _log(f"register dq {rule}")
        await run_sql(statement)


async def _try_sql(sql: str) -> tuple[SqlResult, str | None]:
    try:
        return await run_sql(sql, limit=5000), None
    except ZetarisError as exc:
        return SqlResult([], []), public_error(str(exc))


def _status_line(name: str, is_present: bool, activated: str, error: str | None) -> str:
    if error:
        return f"object={name} present=unknown activated={activated} detail={error}"
    state = "yes" if is_present else "no"
    return f"object={name} present={state} activated={activated}"


def activated_table(statement: str) -> str:
    marker = "ACTIVATE USL TABLE "
    start = statement.upper().find(marker)
    if start < 0:
        return "usl table"
    tail = statement[start + len(marker) :].split()[0]
    return tail.rsplit(".", 1)[-1]


def _missing_pathology_field(message: str) -> bool:
    text = message.lower()
    return "field_not_found" in text or "no such struct field" in text


def _cells_mention(result: SqlResult, token: str) -> bool:
    needle = token.lower()
    return any(needle in cell.lower() for cell in _cells(result))


def _activation_row(row: dict[str, str], table: str) -> dict[str, str] | None:
    name = row.get("name", "")
    if _is_name(name, table):
        return row
    if name:
        return None
    for key, value in row.items():
        if key in {"usl_id", "count", "activated", "type"}:
            continue
        if _is_name(value, table):
            return row
    return None


def _cells(result: SqlResult) -> list[str]:
    cells: list[str] = []
    for row in result.rows:
        if isinstance(row, dict):
            values = row.values()
        elif isinstance(row, (list, tuple)):
            values = list(row)
        else:
            values = [row]
        for value in values:
            if value is not None:
                cells.append(str(value))
    return cells


def _row_dicts(result: SqlResult) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in result.rows:
        if isinstance(row, dict):
            rows.append(
                {
                    str(key).lower(): "" if value is None else str(value)
                    for key, value in row.items()
                }
            )
            continue
        if isinstance(row, (list, tuple)):
            columns = [column.lower() for column in result.columns] or [
                str(i) for i in range(len(row))
            ]
            rows.append(
                {
                    (columns[index] if index < len(columns) else str(index)): ""
                    if value is None
                    else str(value)
                    for index, value in enumerate(row)
                }
            )
            continue
        rows.append({"value": "" if row is None else str(row)})
    return rows


def _is_name(value: str, name: str) -> bool:
    text = value.strip().lower()
    target = name.lower()
    return text == target or text.endswith("." + target)


async def _stage_check_is_current() -> bool:
    result, error = await _try_sql(f"LOAD USL {USL_NAME} NAMESPACE {NAMESPACE}")
    if error or not result.rows:
        return False
    contract = _contract_from_result(result)
    if not _has_all_tables(contract):
        return False
    names = _usl_table_column_names(contract, "stage_check")
    if SCHEMA_MARKER in names:
        return True
    if not isinstance(contract, dict):
        return False
    tables = contract.get("tables")
    if not isinstance(tables, list):
        return False
    for item in tables:
        if not isinstance(item, dict):
            continue
        label = item.get("name") or item.get("table") or item.get("tableName")
        if str(label) != "stage_check":
            continue
        return SCHEMA_MARKER in json.dumps(item).lower()
    return False


def _has_all_tables(contract: Any) -> bool:
    """False when the deployed USL lacks a table this code defines (a new table was added)."""
    tables = contract.get("tables") if isinstance(contract, dict) else None
    if not isinstance(tables, list):
        return True  # unknown contract shape: fall back to the column check
    listed = {
        str(item.get("name") or item.get("table") or item.get("tableName"))
        for item in tables
        if isinstance(item, dict)
    }
    return all(table in listed for table in USL_TABLES)


def _usl_table_column_names(contract: Any, table: str) -> set[str]:
    if not isinstance(contract, dict):
        return set()
    tables = contract.get("tables")
    if not isinstance(tables, list):
        return set()
    names: set[str] = set()
    for item in tables:
        if not isinstance(item, dict):
            continue
        label = item.get("name") or item.get("table") or item.get("tableName")
        if str(label) != table:
            continue
        columns = item.get("columns") or item.get("fields") or []
        if not isinstance(columns, list):
            continue
        for column in columns:
            if isinstance(column, str):
                names.add(column.lower())
            elif isinstance(column, dict):
                col_name = column.get("name") or column.get("columnName")
                if isinstance(col_name, str):
                    names.add(col_name.lower())
    return names


def _contract_from_result(result: SqlResult) -> Any:
    if not result.rows:
        return None
    cell = result.rows[0]
    if isinstance(cell, dict) and ("tables" in cell or "name" in cell):
        return cell
    if isinstance(cell, dict):
        cell = next(iter(cell.values()), None)
    elif isinstance(cell, (list, tuple)):
        cell = cell[0] if cell else None
    if isinstance(cell, dict):
        return cell
    if isinstance(cell, str):
        try:
            return json.loads(cell)
        except json.JSONDecodeError:
            return None
    return None
