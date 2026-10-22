"""Zetaris Lightning SQL REST client."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app import config

_TIMEOUT_S = 60.0


class ZetarisError(Exception):
    """Zetaris SQL call failed. Messages never include URLs or env values."""


class SqlResult:
    def __init__(self, rows: list[Any], columns: list[str]) -> None:
        self.rows = rows
        self.columns = columns


def _columns_from(payload: dict[str, Any]) -> list[str]:
    raw = (
        payload.get("headers")
        or payload.get("columns")
        or payload.get("columnNames")
        or payload.get("fields")
    )
    if isinstance(raw, list) and raw:
        names: list[str] = []
        for item in raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("columnName") or item.get("label")
                names.append(str(name) if name is not None else "")
            else:
                names.append(str(item))
        return names
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return list(data[0].keys())
    return []


def _rows_from(payload: dict[str, Any]) -> list[Any]:
    if "data" in payload and isinstance(payload["data"], list):
        return payload["data"]
    if "rows" in payload and isinstance(payload["rows"], list):
        return payload["rows"]
    result = payload.get("result")
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        return result["data"]
    return []


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        for key in ("msg", "message", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return f"HTTP {response.status_code}"


async def run_sql(sql: str, limit: int = 1000) -> SqlResult:
    """POST /sql-editor/sqls/run and return data rows plus column names."""
    base = (config.getenv("ZETARIS_REST_URL") or "").rstrip("/")
    org_id = config.getenv("ZETARIS_ORG_ID")
    api_key = config.getenv("ZETARIS_API_KEY")
    request_id = str(uuid.uuid4())
    query_id = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": request_id,
    }
    if org_id is not None:
        headers["X-Org-ID"] = org_id
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "queryId": query_id,
        "sql": sql,
        "source": "SqlEditor",
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.post(f"{base}/sql-editor/sqls/run", headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise ZetarisError(f"Zetaris transport error: {type(exc).__name__}") from exc
    if not (200 <= response.status_code < 300):
        raise ZetarisError(_error_message(response))
    payload = response.json()
    if not isinstance(payload, dict):
        payload = {"data": payload}
    return SqlResult(rows=_rows_from(payload), columns=_columns_from(payload))


async def ping() -> SqlResult:
    return await run_sql("SELECT 1", limit=1)
