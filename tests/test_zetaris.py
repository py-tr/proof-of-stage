from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx

from app import zetaris
from app.zetaris import ZetarisError


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_run_sql_headers_and_body_shape() -> None:
    with respx.mock:
        route = respx.post("https://zetaris.test/sql-editor/sqls/run").mock(
            return_value=httpx.Response(200, json={"data": [[1]], "columns": ["one"]})
        )
        result = await zetaris.run_sql("SELECT 1", limit=25)
    assert result.rows == [[1]]
    assert result.columns == ["one"]
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-zetaris-key"
    assert request.headers["x-org-id"] == "test-org"
    uuid.UUID(request.headers["x-request-id"])
    body = json.loads(request.content)
    assert body["sql"] == "SELECT 1"
    assert body["source"] == "SqlEditor"
    assert body["limit"] == 25
    uuid.UUID(body["queryId"])
    assert set(body) == {"queryId", "sql", "source", "limit"}


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_run_sql_parses_headers_key() -> None:
    with respx.mock:
        respx.post("https://zetaris.test/sql-editor/sqls/run").mock(
            return_value=httpx.Response(
                200,
                json={
                    "headers": ["one", "two"],
                    "data": [["1", "2"]],
                    "total": 1,
                    "timeUsed": 12,
                },
            )
        )
        result = await zetaris.run_sql("SELECT 1", limit=25)
    assert result.columns == ["one", "two"]
    assert result.rows == [["1", "2"]]


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_run_sql_400_surfaces_msg_without_url() -> None:
    with respx.mock:
        respx.post("https://zetaris.test/sql-editor/sqls/run").mock(
            return_value=httpx.Response(400, json={"msg": "bad sql"})
        )
        with pytest.raises(ZetarisError, match="bad sql") as excinfo:
            await zetaris.run_sql("SELECT 1")
    assert "http" not in str(excinfo.value).lower()
    assert "zetaris.test" not in str(excinfo.value)
