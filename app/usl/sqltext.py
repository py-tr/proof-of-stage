"""Statement splitting and Spark string literals for Lightning SQL."""

from __future__ import annotations

import hashlib
import re

from app.usl.model import SQL_DIR

_FINGERPRINT_RE = re.compile(r"/\*\s*uslfp:([0-9a-f]+)\s*\*/", re.IGNORECASE)
_AS_SELECT_RE = re.compile(r"\bAS\s+SELECT\b", re.IGNORECASE)


def split_statements(sql: str) -> list[str]:
    """Split on semicolons outside quotes. A COMPILE USL statement stays whole.

    CREATE TABLE pieces that belong to the COMPILE DDL are joined back with
    semicolons. The returned statements have no trailing semicolon.
    """
    pieces = _semicolon_pieces(sql)
    merged: list[str] = []
    index = 0
    while index < len(pieces):
        piece = pieces[index].strip()
        if not piece:
            index += 1
            continue
        if _starts_with(piece, "COMPILE USL"):
            parts = [piece]
            index += 1
            while index < len(pieces):
                nxt = pieces[index].strip()
                if not nxt:
                    index += 1
                    continue
                if _starts_with(nxt, "CREATE TABLE"):
                    parts.append(nxt)
                    index += 1
                    continue
                break
            merged.append(";\n".join(parts))
            continue
        merged.append(piece)
        index += 1
    return merged


def load_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def load_statements(name: str) -> list[str]:
    return split_statements(load_sql(name))


def sql_string(value: str | None) -> str:
    """Spark single-quoted literal. None is NULL. Quotes and backslashes are escaped.

    Backslash escapes, not doubled quotes: on Lightning 'O''Brien' parses as two adjacent
    literals and returns "OBrien" (measured live), silently dropping every apostrophe.
    """
    if value is None:
        return "NULL"
    if not isinstance(value, str):
        raise TypeError("SQL string value must be a str or None")
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return "'" + escaped + "'"


def sql_int(value: int | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("SQL integer value must be an int or None")
    return str(value)


def sql_fingerprint(sql: str) -> str:
    """Stable hash of activation SQL with whitespace and uslfp comments ignored."""
    return hashlib.sha256(normalize_sql(sql).encode("utf-8")).hexdigest()[:16]


def normalize_sql(sql: str) -> str:
    return " ".join(_FINGERPRINT_RE.sub("", sql).split()).lower()


def stamp_activation(sql: str) -> str:
    """Embed the fingerprint in the SELECT so LOAD USL can show whether it changed."""
    digest = sql_fingerprint(sql)
    if extract_fingerprint(sql) == digest:
        return sql
    match = _AS_SELECT_RE.search(sql)
    if match is None:
        return sql
    return sql[: match.end()] + f" /* uslfp:{digest} */" + sql[match.end() :]


def extract_fingerprint(sql: str) -> str | None:
    match = _FINGERPRINT_RE.search(sql)
    if match is None:
        return None
    return match.group(1).lower()


def _starts_with(statement: str, prefix: str) -> bool:
    compact = " ".join(statement.split())
    return compact.upper().startswith(prefix.upper())


def _semicolon_pieces(sql: str) -> list[str]:
    pieces: list[str] = []
    buf: list[str] = []
    index = 0
    length = len(sql)
    in_single = False
    in_double = False
    while index < length:
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""
        if in_single or in_double:
            buf.append(char)
            if char == "\\" and nxt:
                buf.append(nxt)
                index += 2
                continue
            quote = "'" if in_single else '"'
            if char == quote and nxt == quote:
                buf.append(nxt)
                index += 2
                continue
            if char == quote:
                in_single = False
                in_double = False
            index += 1
            continue
        if char == "-" and nxt == "-":
            index += 2
            while index < length and sql[index] != "\n":
                index += 1
            if index < length and sql[index] == "\n":
                buf.append("\n")
            continue
        if char == "/" and nxt == "*":
            index += 2
            while index + 1 < length and not (sql[index] == "*" and sql[index + 1] == "/"):
                index += 1
            index = min(length, index + 2)
            continue
        if char == "'":
            in_single = True
            buf.append(char)
            index += 1
            continue
        if char == '"':
            in_double = True
            buf.append(char)
            index += 1
            continue
        if char == ";":
            pieces.append("".join(buf))
            buf = []
            index += 1
            continue
        buf.append(char)
        index += 1
    pieces.append("".join(buf))
    return pieces
