"""Read and append helpers for the stage_audit semantic layer."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.usl.errors import public_error
from app.usl.model import (
    DQ_RULES,
    EXTRACTION_COLUMNS,
    FLAG_COLUMNS,
    NAMESPACE,
    PG_SOURCE,
    SQL_NODE_COUNT,
    USL_NAME,
    allowed_name,
    table_fqn,
)
from app.usl.sqltext import split_statements, sql_int, sql_string
from app.zetaris import SqlResult, ZetarisError, run_sql

STAGE_CHECK = table_fqn("stage_check")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DOTTED = re.compile(r"\b[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+\b")
_CLAUSE_NAME = re.compile(
    r"\b(?:FROM|JOIN|TABLE|NAMESPACE|INTO|UPDATE|IN)\s+(`[^`]+`|[A-Za-z_][\w.]*)",
    re.IGNORECASE,
)
_SHOW_DB = re.compile(
    r"\bSHOW\s+(?:LIGHTNING|DATASOURCE)\s+TABLES\s+([A-Za-z_][\w.]*)",
    re.IGNORECASE,
)
_COMMA_NAME = re.compile(r"\s*,\s*(`[^`]+`|[A-Za-z_][\w.]*)")
_DENY = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|MERGE|COMPILE|REMOVE|GRANT|REVOKE|"
    r"TRUNCATE|UPSERT|CALL|COPY|INTO)\b",
    re.IGNORECASE,
)
_ALLOWED_COMMANDS = ("SHOW DQ", "LOAD USL", "RUN DQ", "SELECT", "SHOW")
_DQ_RULE = re.compile(
    r"(?:RUN\s+DQ|SHOW\s+DQ\s+(?:INVALID|VALID)\s+RECORD)\s+([A-Za-z_][\w]*)\s+TABLE\b",
    re.IGNORECASE,
)

_DQ_TARGET = re.compile(
    r"^(?:RUN\s+DQ|SHOW\s+DQ\s+(?:INVALID|VALID)\s+RECORD)\s+([A-Za-z_][\w]*)"
    r"\s+TABLE\s+([A-Za-z_][\w.]*)$",
    re.IGNORECASE,
)
# Spark/Hive functions that can reach the JVM, the environment or the file system.
_DENY_FUNCTIONS = re.compile(
    r"\b(?:reflect|java_method|try_reflect|getenv|input_file_name|input_file_block_start|"
    r"current_user|session_user|user|assert_true|raise_error|udf|transform)\s*\(",
    re.IGNORECASE,
)


class SqlGuardError(Exception):
    """A query is not a read against the registry audit sources."""


@dataclass(frozen=True)
class DqCounts:
    rule: str
    total: int
    valid: int
    invalid: int


def guard_select(sql: str) -> str:
    """Allow one SELECT, SHOW, LOAD USL, RUN DQ, or SHOW DQ against our sources."""
    parts = split_statements(sql)
    if len(parts) != 1:
        raise SqlGuardError("only one statement is allowed")
    statement = parts[0]
    if _has_quoted_identifier(statement):
        # Double-quoted or backticked identifiers could smuggle any name past the name check.
        raise SqlGuardError("quoted identifiers are not allowed")
    masked = _mask_strings(statement)
    compact = " ".join(masked.split())
    upper = compact.upper()
    if not any(upper.startswith(prefix) for prefix in _ALLOWED_COMMANDS):
        raise SqlGuardError("statement is not a read of the registry audit sources")
    if _DENY.search(masked):
        raise SqlGuardError("statement is not a read of the registry audit sources")
    if _DENY_FUNCTIONS.search(masked):
        raise SqlGuardError("function is not allowed")
    if upper.startswith(("RUN DQ", "SHOW DQ")):
        target = _DQ_TARGET.match(compact)
        if target is None:
            raise SqlGuardError("a data-quality command must name a rule and the stage_check table")
        if target.group(1).lower() not in DQ_RULES:
            raise SqlGuardError("unknown data-quality rule")
        if target.group(2).lower() != STAGE_CHECK.lower():
            raise SqlGuardError("data-quality commands may only target stage_check")
    for name in _referenced_names(masked):
        if not allowed_name(name):
            raise SqlGuardError("name is outside the registry audit sources")
    return statement


async def select(sql: str, limit: int = 1000) -> SqlResult:
    statement = guard_select(sql)
    return await run_sql(statement, limit=limit)


async def load_contract() -> Any:
    """LOAD USL returns the stage_audit JSON data contract."""
    result = await select(f"LOAD USL {USL_NAME} NAMESPACE {NAMESPACE}")
    return _parse_contract(result)


async def run_dq(rule: str) -> DqCounts:
    name = _check_rule(rule)
    result = await select(f"RUN DQ {name} TABLE {STAGE_CHECK}", limit=100)
    return parse_dq_counts(name, result)


async def invalid_records(rule: str, limit: int = 5000) -> SqlResult:
    name = _check_rule(rule)
    return await select(f"SHOW DQ INVALID RECORD {name} TABLE {STAGE_CHECK}", limit=limit)


async def insert_flag(
    *,
    flag_id: str,
    case_id: str,
    rule_id: str,
    field: str | None = None,
    recorded_value: str | None = None,
    derived_value: str | None = None,
    quote: str | None = None,
    reason: str | None = None,
    severity: str | None = None,
    model: str | None = None,
    receipt_id: str | None = None,
    created_at: str,
) -> SqlResult:
    statement = insert_flag_sql(
        flag_id=flag_id,
        case_id=case_id,
        rule_id=rule_id,
        field=field,
        recorded_value=recorded_value,
        derived_value=derived_value,
        quote=quote,
        reason=reason,
        severity=severity,
        model=model,
        receipt_id=receipt_id,
        created_at=created_at,
    )
    return await run_sql(statement)


async def insert_extraction(
    *,
    case_id: str,
    method: str,
    field: str,
    value: str | None = None,
    quote: str | None = None,
    quote_start: int | None = None,
    quote_end: int | None = None,
    model: str | None = None,
    receipt_id: str | None = None,
    created_at: str,
    requires: tuple[str, str] | None = None,
) -> SqlResult:
    statement = insert_extraction_sql(
        case_id=case_id,
        method=method,
        field=field,
        value=value,
        quote=quote,
        quote_start=quote_start,
        quote_end=quote_end,
        model=model,
        receipt_id=receipt_id,
        created_at=created_at,
        requires=requires,
    )
    return await run_sql(statement)


def insert_flag_sql(
    *,
    flag_id: str,
    case_id: str,
    rule_id: str,
    field: str | None = None,
    recorded_value: str | None = None,
    derived_value: str | None = None,
    quote: str | None = None,
    reason: str | None = None,
    severity: str | None = None,
    model: str | None = None,
    receipt_id: str | None = None,
    created_at: str,
) -> str:
    _require_text(flag_id, "flag_id")
    _require_text(case_id, "case_id")
    _require_text(rule_id, "rule_id")
    _require_text(created_at, "created_at")
    values = {
        "flag_id": sql_string(flag_id),
        "case_id": sql_string(case_id),
        "rule_id": sql_string(rule_id),
        "field": sql_string(field),
        "recorded_value": sql_string(recorded_value),
        "derived_value": sql_string(derived_value),
        "quote": sql_string(quote),
        "reason": sql_string(reason),
        "severity": sql_string(severity),
        "model": sql_string(model),
        "receipt_id": sql_string(receipt_id),
        "created_at": sql_string(created_at),
    }
    return _insert_where_missing(
        f"{PG_SOURCE}.flag_log",
        FLAG_COLUMNS,
        values,
        f"existing.flag_id = {sql_string(flag_id)}",
    )


def insert_extraction_sql(
    *,
    case_id: str,
    method: str,
    field: str,
    value: str | None = None,
    quote: str | None = None,
    quote_start: int | None = None,
    quote_end: int | None = None,
    model: str | None = None,
    receipt_id: str | None = None,
    created_at: str,
    requires: tuple[str, str] | None = None,
) -> str:
    """Append one extraction row unless (case_id, method, field) already exists.

    requires=(field, created_at): write only if that sibling row exists with exactly this
    created_at, i.e. it was written by the same read (ties a reason row to its value).
    """
    _require_text(case_id, "case_id")
    _require_text(method, "method")
    _require_text(field, "field")
    _require_text(created_at, "created_at")
    if method == SQL_NODE_COUNT:
        raise ValueError("sql_node_count is reserved for the node-count derivation")
    values = {
        "case_id": sql_string(case_id),
        "method": sql_string(method),
        "field": sql_string(field),
        "value": sql_string(value),
        "quote": sql_string(quote),
        "quote_start": sql_int(quote_start),
        "quote_end": sql_int(quote_end),
        "model": sql_string(model),
        "receipt_id": sql_string(receipt_id),
        "created_at": sql_string(created_at),
    }
    predicate = (
        f"existing.case_id = {sql_string(case_id)} "
        f"AND existing.method = {sql_string(method)} "
        f"AND existing.field = {sql_string(field)}"
    )
    table = f"{PG_SOURCE}.derived_extraction"
    also = None
    if requires is not None:
        sibling, stamp = requires
        _require_text(sibling, "requires field")
        _require_text(stamp, "requires created_at")
        also = (
            f"EXISTS (\n  SELECT 1 FROM {table} AS sibling\n"
            f"  WHERE sibling.case_id = {sql_string(case_id)} "
            f"AND sibling.method = {sql_string(method)} "
            f"AND sibling.field = {sql_string(sibling)} "
            f"AND sibling.created_at = {sql_string(stamp)}\n)"
        )
    return _insert_where_missing(table, EXTRACTION_COLUMNS, values, predicate, also)


def _insert_where_missing(
    table: str,
    columns: tuple[str, ...],
    values: dict[str, str],
    predicate: str,
    also: str | None = None,
) -> str:
    column_list = ", ".join(columns)
    value_list = ", ".join(values[column] for column in columns)
    return (
        f"INSERT INTO {table} ({column_list})\n"
        f"SELECT {value_list}\n"
        "FROM (SELECT 1 AS seed) seed\n"
        "WHERE NOT EXISTS (\n"
        f"  SELECT 1 FROM {table} AS existing\n"
        f"  WHERE {predicate}\n"
        ")" + (f"\nAND {also}" if also else "")
    )


def _check_rule(rule: str) -> str:
    if not isinstance(rule, str) or not _IDENT.fullmatch(rule) or rule not in DQ_RULES:
        raise SqlGuardError("unknown data-quality rule")
    return rule


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")


def _referenced_names(masked_sql: str) -> list[str]:
    names: list[str] = []
    for match in _DOTTED.finditer(masked_sql):
        names.append(match.group(0))
    for match in _SHOW_DB.finditer(masked_sql):
        names.append(match.group(1))
    for match in _CLAUSE_NAME.finditer(masked_sql):
        names.append(match.group(1))
        tail = masked_sql[match.end() :]
        while True:
            extra = _COMMA_NAME.match(tail)
            if extra is None:
                break
            names.append(extra.group(1))
            tail = tail[extra.end() :]
    return names


def _has_quoted_identifier(sql: str) -> bool:
    """True when a double quote or backtick appears outside a single-quoted string."""
    in_single = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if in_single:
            if char == "\\" and index + 1 < len(sql):
                index += 2
                continue
            if char == "'" and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            if char == "'":
                in_single = False
        elif char == "'":
            in_single = True
        elif char in '"`':
            return True
        index += 1
    return False


def _mask_strings(sql: str) -> str:
    """Replace quoted text so keyword and name checks ignore literals."""
    out: list[str] = []
    index = 0
    length = len(sql)
    in_single = False
    in_double = False
    while index < length:
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""
        if in_single or in_double:
            quote = "'" if in_single else '"'
            if char == "\\" and nxt:
                index += 2
                continue
            if char == quote and nxt == quote:
                index += 2
                continue
            if char == quote:
                out.append(quote)
                in_single = False
                in_double = False
            index += 1
            continue
        if char == "'":
            in_single = True
            out.append(char)
            index += 1
            continue
        if char == '"':
            in_double = True
            out.append(char)
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _parse_contract(result: SqlResult) -> Any:
    if not result.rows:
        raise ZetarisError("LOAD USL returned no contract")
    cell = _first_cell(result.rows[0])
    if isinstance(cell, str):
        try:
            return json.loads(cell)
        except json.JSONDecodeError as exc:
            raise ZetarisError("LOAD USL returned an unreadable contract") from exc
    if isinstance(cell, dict):
        return cell
    raise ZetarisError("LOAD USL returned an unreadable contract")


def _first_cell(row: Any) -> Any:
    if isinstance(row, dict):
        if "tables" in row or "name" in row:
            return row
        return next(iter(row.values()), None)
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    return row


_COUNT_KEYS = {
    "total": ("total_record", "total_records", "total"),
    "valid": ("valid_record", "valid_records", "valid"),
    "invalid": ("invalid_record", "invalid_records", "invalid"),
}


def parse_dq_counts(rule: str, result: SqlResult) -> DqCounts:
    """Read RUN DQ counts from Zetaris (`total_record`, `valid_record`, `invalid_record`)."""
    if not result.rows:
        raise ZetarisError(public_error("RUN DQ returned no counts"))
    rows = _count_rows(result)
    chosen = next(
        (row for row in rows if str(row.get("name", "")).lower() == rule.lower()),
        rows[0],
    )
    try:
        return DqCounts(
            rule=rule,
            total=_count_value(chosen, "total"),
            valid=_count_value(chosen, "valid"),
            invalid=_count_value(chosen, "invalid"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ZetarisError("RUN DQ returned no counts") from exc


def format_invalid_records(result: SqlResult, limit: int | None = None) -> str:
    """Print invalid stage_check rows: the recorded N, the count and what the report says."""
    mapping = (
        ("case_id", "case_id"),
        ("edition", "edition_code"),
        ("recorded N", "recorded_n"),
        ("lymph_nodes_positive", "lymph_nodes_positive"),
        ("derived N", "derived_n"),
        ("report N", "report_n"),
        ("report count", "report_nodes_positive"),
        ("fault_field", "fault_field"),
    )
    rows = _row_maps(result)
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        return "no invalid records\n"
    headers = [title for title, _key in mapping]
    cells = [
        ["" if row.get(key) is None else str(row.get(key, "")) for _title, key in mapping]
        for row in rows
    ]
    widths = [len(header) for header in headers]
    for line in cells:
        for index, value in enumerate(line):
            widths[index] = max(widths[index], len(value))
    header = "  ".join(title.ljust(widths[index]) for index, title in enumerate(headers))
    body = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(line)) for line in cells
    ]
    return header + "\n" + "\n".join(body) + "\n"


def _count_rows(result: SqlResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in result.rows:
        if isinstance(row, dict):
            rows.append({str(key).lower(): value for key, value in row.items()})
            continue
        values = list(row) if isinstance(row, (list, tuple)) else [row]
        columns = [column.lower() for column in result.columns]
        if len(columns) == len(values) and columns:
            rows.append(dict(zip(columns, values, strict=True)))
        elif len(values) >= 3:
            rows.append({"total": values[0], "valid": values[1], "invalid": values[2]})
        else:
            raise ZetarisError("RUN DQ returned no counts")
    return rows


def _count_value(row: dict[str, Any], kind: str) -> int:
    for key in _COUNT_KEYS[kind]:
        if key in row:
            return _as_int(row[key])
    raise KeyError(kind)


def _row_maps(result: SqlResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in result.rows:
        if isinstance(row, dict):
            rows.append({str(key).lower(): value for key, value in row.items()})
            continue
        values = list(row) if isinstance(row, (list, tuple)) else [row]
        columns = [column.lower() for column in result.columns] or [
            str(index) for index in range(len(values))
        ]
        rows.append(
            {
                (columns[index] if index < len(columns) else str(index)): value
                for index, value in enumerate(values)
            }
        )
    return rows


def _as_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise TypeError
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(float(str(value).strip()))
