from __future__ import annotations

import json
from subprocess import CompletedProcess

import httpx
import pytest
import respx

from app.cli import main
from app.usl.client import DqCounts
from app.usl.errors import SetupError
from app.usl.model import USL_TABLES
from app.usl.postgres import apply_ddl, user_from_env
from app.usl.setup import _ACTIVATE, dq_report, setup, status_report, teardown
from app.usl.sqltext import load_statements, sql_fingerprint
from app.zetaris import SqlResult, ZetarisError

_PASSWORD = "super-secret-password"


def test_user_from_env_keeps_the_password_out_of_the_user() -> None:
    user, secrets = user_from_env(f"POSTGRES_PASSWORD={_PASSWORD}\nPOSTGRES_USER=oa_user\n")
    assert user == "oa_user"
    assert secrets == [_PASSWORD]
    with pytest.raises(SetupError, match="unset"):
        user_from_env("POSTGRES_PASSWORD=only-a-secret\n")


def test_apply_ddl_does_not_pass_or_echo_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        seen["args"] = args
        seen["input"] = kwargs.get("input")
        return CompletedProcess(args, 0, stdout=f"POSTGRES_PASSWORD={_PASSWORD}", stderr="")

    monkeypatch.setattr("app.usl.postgres.subprocess.run", fake_run)
    apply_ddl("oa_user", "CREATE TABLE IF NOT EXISTS flag_log (flag_id TEXT);", [_PASSWORD])
    args = seen["args"]
    assert isinstance(args, list)
    assert _PASSWORD not in args
    assert "oa_user" in args
    assert "oa-pg" in args
    assert "oa" in args
    assert _PASSWORD not in str(seen["input"])


def test_apply_ddl_error_scrubs_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args, 1, stdout="", stderr=f"failed {_PASSWORD}")

    monkeypatch.setattr("app.usl.postgres.subprocess.run", fake_run)
    with pytest.raises(SetupError, match="failed") as excinfo:
        apply_ddl("oa_user", "CREATE TABLE IF NOT EXISTS flag_log (flag_id TEXT);", [_PASSWORD])
    assert _PASSWORD not in str(excinfo.value)


def _usl_table_rows(activated: str = "true") -> SqlResult:
    return SqlResult(
        [[table, "TABLE", "usl-1", "0", activated] for table in USL_TABLES],
        ["name", "type", "usl_id", "count", "activated"],
    )


def _load_usl_contract(digest_for: dict[str, str] | None = None) -> SqlResult:
    tables = []
    for filename in _ACTIVATE:
        statement = load_statements(filename)[0]
        name = statement.split("stage_audit.", 1)[1].split()[0]
        digest = (digest_for or {}).get(name, sql_fingerprint(statement))
        entry = {"name": name, "activateQuery": f"SELECT /* uslfp:{digest} */ 1"}
        if name == "stage_check":
            entry["columns"] = [{"name": "reason_class"}]
        tables.append(entry)
    return SqlResult([[json.dumps({"name": "stage_audit", "tables": tables})]], ["contract"])


def _catalog(sql: str) -> SqlResult:
    text = " ".join(sql.split()).upper()
    if text.startswith("SHOW LIGHTNING DATABASES"):
        return SqlResult([["REG_FILES"], ["GDC_REST"]], ["name"])
    if text.startswith("SHOW LIGHTNING TABLES REG_FILES"):
        return SqlResult([["staging_rules"], ["path_reports"]], ["name"])
    if text.startswith("SHOW LIGHTNING TABLES GDC_REST"):
        return SqlResult([["brca_cases_raw"]], ["name"])
    if text.startswith("SHOW DATASOURCE TABLES"):
        return SqlResult([["derived_extraction"], ["flag_log"]], ["name"])
    if text.startswith("LOAD USL"):
        return _load_usl_contract()
    if text.startswith("DESCRIBE DATASOURCE TABLE GDC_REST.BRCA_CASES_RAW"):
        return SqlResult([["pathology_details"]], ["col_name"])
    if "PATHOLOGY_DETAILS" in text and text.startswith("SELECT"):
        return SqlResult([["1"]], ["lymph_nodes_positive"])
    if "IN LIGHTNING.METASTORE.REGISTRY_AUDIT.STAGE_AUDIT" in text:
        return _usl_table_rows("true")
    if "IN LIGHTNING.METASTORE.REGISTRY_AUDIT" in text:
        return SqlResult([["stage_audit"]], ["name"])
    if text.startswith("SHOW NAMESPACES OR TABLES IN LIGHTNING.METASTORE"):
        return SqlResult([["registry_audit"]], ["name"])
    if text.startswith("SHOW CACHE TABLES"):
        return SqlResult([], ["name"])
    if text.startswith("LIST DQ"):
        return SqlResult(
            [
                ["nodes_consistent"],
                ["stage_derivable_but_missing"],
                ["report_agrees"],
                ["edition_supported"],
            ],
            ["name"],
        )
    return SqlResult([], [])


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_setup_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sql_calls: list[str] = []
    applied: list[str] = []
    existing = {"on": False}

    async def fake_sql(sql: str, limit: int = 1000) -> SqlResult:
        sql_calls.append(sql)
        if not existing["on"]:
            return SqlResult([], [])
        return _catalog(sql)

    def fake_discover() -> tuple[str, list[str]]:
        return "oa_user", [_PASSWORD]

    def fake_apply(user: str, sql: str, secrets: list[str]) -> None:
        assert user == "oa_user"
        assert _PASSWORD not in sql
        assert _PASSWORD not in secrets or secrets == [_PASSWORD]
        applied.append(sql)

    monkeypatch.setattr("app.usl.setup.discover_user", fake_discover)
    monkeypatch.setattr("app.usl.setup.apply_ddl", fake_apply)
    monkeypatch.setattr("app.usl.setup.run_sql", fake_sql)

    with respx.mock:
        created = respx.post("https://zetaris.test/ndp-files/createdir").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        saved = respx.post("https://zetaris.test/ndp-files/save").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await setup()
        first_sql = list(sql_calls)
        first_ddl = list(applied)
        existing["on"] = True
        sql_calls.clear()
        applied.clear()
        await setup()
        second_sql = list(sql_calls)
        second_ddl = list(applied)

    first = "\n".join(first_sql).upper()
    second = "\n".join(second_sql).upper()
    assert "CREATE LIGHTNING DATABASE REG_FILES" in first
    assert "CREATE LIGHTNING DATABASE GDC_REST" in first
    assert "CREATE LIGHTNING FILESTORE TABLE STAGING_RULES" in first
    assert "CREATE LIGHTNING FILESTORE TABLE PATH_REPORTS" in first
    assert "CREATE LIGHTNING REST TABLE BRCA_CASES_RAW" in first
    assert "CACHE TABLE GDC_REST.BRCA_CASES_RAW" in first
    assert "COMPILE USL STAGE_AUDIT" in first
    assert "REGISTER DATASOURCE TABLE" in first
    assert "REGISTER DQ NODES_CONSISTENT" in first
    assert "CREATE NAMESPACE IF NOT EXISTS" in first
    assert "CREATE TABLE IF NOT EXISTS" in first_ddl[0].upper()
    assert "DERIVED_EXTRACTION" in first_ddl[0].upper()
    assert "FLAG_LOG" in first_ddl[0].upper()
    for banned in (
        "CREATE LIGHTNING DATABASE",
        "CREATE LIGHTNING FILESTORE",
        "CREATE LIGHTNING REST",
        "COMPILE USL",
        "CACHE TABLE GDC_REST",
        "REGISTER DATASOURCE",
    ):
        assert banned not in second, banned
    assert "REMOVE DQ" in second
    assert "REGISTER DQ" in second
    assert "CREATE NAMESPACE IF NOT EXISTS" in second
    assert "UNCACHE LIGHTNING FILESTORE TABLE" in second
    assert "ACTIVATE USL TABLE" not in second
    assert "CREATE TABLE IF NOT EXISTS" in second_ddl[0].upper()
    assert _PASSWORD not in capsys.readouterr().out
    assert created.call_count == 2
    body = json.loads(created.calls[0].request.content)
    assert body == {"path": "file-store/stage_audit"}
    assert saved.call_count == 4
    saved_body = saved.calls[0].request.content
    assert b"file-store/stage_audit" in saved_body
    assert b"staging_rules.csv" in saved_body
    assert saved.calls[0].request.headers["x-org-id"] == "test-org"


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_teardown_removes_only_our_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    sql_calls: list[str] = []
    applied: list[str] = []

    async def fake_sql(sql: str, limit: int = 1000) -> SqlResult:
        sql_calls.append(sql)
        text = " ".join(sql.split()).upper()
        if "IN LIGHTNING.METASTORE.REGISTRY_AUDIT" in text:
            return SqlResult([["stage_audit"]], ["name"])
        if text.startswith("SHOW NAMESPACES OR TABLES IN LIGHTNING.METASTORE"):
            return SqlResult([["registry_audit"]], ["name"])
        if text.startswith("LIST DQ"):
            return SqlResult(
                [
                    ["nodes_consistent"],
                    ["stage_derivable_but_missing"],
                    ["report_agrees"],
                    ["edition_supported"],
                ],
                ["name"],
            )
        if text.startswith("SHOW LIGHTNING DATABASES"):
            return SqlResult([["REG_FILES"], ["GDC_REST"], ["other_db"]], ["name"])
        return SqlResult([], [])

    monkeypatch.setattr("app.usl.setup.run_sql", fake_sql)
    monkeypatch.setattr("app.usl.setup.discover_user", lambda: ("oa_user", [_PASSWORD]))

    def fake_apply(user: str, sql: str, secrets: list[str]) -> None:
        assert _PASSWORD not in sql
        applied.append(sql)

    monkeypatch.setattr("app.usl.setup.apply_ddl", fake_apply)
    await teardown()
    joined = "\n".join(sql_calls)
    upper = joined.upper()
    assert upper.count("REMOVE DQ") == 4
    assert "REMOVE USL stage_audit" in joined
    assert "DROP NAMESPACE IF EXISTS lightning.metastore.registry_audit" in joined
    assert "DROP LIGHTNING DATABASE REG_FILES" in joined
    assert "DROP LIGHTNING DATABASE GDC_REST" in joined
    assert "DROP LIGHTNING DATABASE other_db" not in joined
    assert "DROP DATASOURCE" not in upper
    assert "oa_pg" not in joined
    drop = applied[0].upper()
    assert "DROP TABLE IF EXISTS FLAG_LOG" in drop
    assert "DROP TABLE IF EXISTS DERIVED_EXTRACTION" in drop
    assert "OA_PG" not in drop


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_status_reports_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sql(sql: str, limit: int = 1000) -> SqlResult:
        text = " ".join(sql.split()).upper()
        if "IN LIGHTNING.METASTORE.REGISTRY_AUDIT.STAGE_AUDIT" in text:
            return SqlResult(
                [
                    ["tumour_case", "TABLE", "usl-1", "1097", "true"],
                    ["path_report", "TABLE", "usl-1", "0", "false"],
                    ["recorded_stage", "TABLE", "usl-1", "0", "false"],
                ],
                ["name", "type", "usl_id", "count", "activated"],
            )
        if "IN LIGHTNING.METASTORE.REGISTRY_AUDIT" in text:
            return SqlResult([["stage_audit"]], ["name"])
        if text.startswith("SHOW NAMESPACES OR TABLES IN LIGHTNING.METASTORE"):
            return SqlResult([["registry_audit"]], ["name"])
        if text.startswith("SHOW LIGHTNING DATABASES"):
            return SqlResult([["REG_FILES"], ["GDC_REST"]], ["name"])
        if text.startswith("SHOW LIGHTNING TABLES REG_FILES"):
            return SqlResult([["staging_rules"], ["path_reports"]], ["name"])
        if text.startswith("SHOW LIGHTNING TABLES GDC_REST"):
            return SqlResult([["brca_cases_raw"]], ["name"])
        if text.startswith("SHOW CACHE TABLES"):
            return SqlResult([], ["name"])
        if text.startswith("SHOW DATASOURCE TABLES"):
            return SqlResult([["derived_extraction"], ["flag_log"]], ["name"])
        if text.startswith("LIST DQ"):
            return SqlResult(
                [
                    ["nodes_consistent"],
                    ["stage_derivable_but_missing"],
                    ["report_agrees"],
                    ["edition_supported"],
                ],
                ["name"],
            )
        return SqlResult([], [])

    monkeypatch.setattr("app.usl.setup.run_sql", fake_sql)
    report = await status_report()
    assert (
        "object=lightning.metastore.registry_audit.stage_audit.tumour_case "
        "present=yes activated=yes"
    ) in report
    assert (
        "object=lightning.metastore.registry_audit.stage_audit.path_report present=yes activated=no"
    ) in report
    assert (
        "object=lightning.metastore.registry_audit.stage_audit.recorded_stage "
        "present=yes activated=no"
    ) in report
    assert "object=cache.GDC_REST.brca_cases_raw present=unknown" in report
    assert "SHOW CACHE TABLES" in report
    assert "object=dq.nodes_consistent present=yes activated=n/a" in report


@pytest.mark.asyncio
async def test_dq_report_prints_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(rule: str) -> DqCounts:
        return DqCounts(rule, 4, 3, 1)

    monkeypatch.setattr("app.usl.setup.run_dq", fake)
    text = await dq_report()
    assert "nodes_consistent total=4 valid=3 invalid=1" in text
    assert "stage_derivable_but_missing total=4 valid=3 invalid=1" in text
    assert "report_agrees total=4 valid=3 invalid=1" in text
    assert "edition_supported total=4 valid=3 invalid=1" in text


@pytest.mark.asyncio
async def test_dq_report_prints_invalid_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(rule: str, limit: int = 5000) -> SqlResult:
        assert rule == "nodes_consistent"
        assert limit == 2
        return SqlResult(
            [["TCGA-AN-A0XO", "7", "N1A", "0", "pN0"]],
            ["case_id", "edition_code", "recorded_n", "lymph_nodes_positive", "derived_n"],
        )

    monkeypatch.setattr("app.usl.setup.invalid_records", fake)
    text = await dq_report(invalid_rule="nodes_consistent", limit=2)
    assert "TCGA-AN-A0XO" in text
    assert "recorded N" in text.splitlines()[0]


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_setup_rebuilds_rest_table_when_pathology_details_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql_calls: list[str] = []

    async def fake_sql(sql: str, limit: int = 1000) -> SqlResult:
        sql_calls.append(sql)
        text = " ".join(sql.split()).upper()
        if text.startswith("DESCRIBE DATASOURCE TABLE GDC_REST.BRCA_CASES_RAW"):
            return SqlResult(
                [["ajcc_pathologic_n"], ["ajcc_pathologic_t"], ["year_of_diagnosis"]],
                ["col_name"],
            )
        if "PATHOLOGY_DETAILS" in text and text.startswith("SELECT"):
            raise ZetarisError(
                "[FIELD_NOT_FOUND] No such struct field lymph_nodes_positive in "
                "ajcc_pathologic_n, ajcc_pathologic_stage, ajcc_pathologic_t"
            )
        if text.startswith("SHOW LIGHTNING TABLES GDC_REST"):
            return SqlResult([["brca_cases_raw"]], ["name"])
        return _catalog(sql)

    monkeypatch.setattr("app.usl.setup.discover_user", lambda: ("oa_user", [_PASSWORD]))
    monkeypatch.setattr("app.usl.setup.apply_ddl", lambda *_args: None)
    monkeypatch.setattr("app.usl.setup.run_sql", fake_sql)
    with respx.mock:
        respx.post("https://zetaris.test/ndp-files/createdir").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        respx.post("https://zetaris.test/ndp-files/save").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await setup()
    joined = "\n".join(sql_calls).upper()
    assert "DROP LIGHTNING DATABASE TABLE GDC_REST.BRCA_CASES_RAW" in joined
    assert "CREATE LIGHTNING REST TABLE BRCA_CASES_RAW" in joined
    assert "CACHE TABLE GDC_REST.BRCA_CASES_RAW" in joined
    assert "PATHOLOGY_DETAILS.LYMPH_NODES_POSITIVE" in joined


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_setup_reactivates_when_fingerprint_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql_calls: list[str] = []

    async def fake_sql(sql: str, limit: int = 1000) -> SqlResult:
        sql_calls.append(sql)
        text = " ".join(sql.split()).upper()
        if text.startswith("LOAD USL"):
            return _load_usl_contract({"recorded_stage": "0" * 16})
        return _catalog(sql)

    monkeypatch.setattr("app.usl.setup.discover_user", lambda: ("oa_user", [_PASSWORD]))
    monkeypatch.setattr("app.usl.setup.apply_ddl", lambda *_args: None)
    monkeypatch.setattr("app.usl.setup.run_sql", fake_sql)
    with respx.mock:
        respx.post("https://zetaris.test/ndp-files/createdir").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        respx.post("https://zetaris.test/ndp-files/save").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await setup()
    activates = [sql for sql in sql_calls if sql.upper().startswith("ACTIVATE USL TABLE")]
    assert len(activates) == 1
    assert "recorded_stage" in activates[0]
    assert "uslfp:" in activates[0]


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_setup_error_names_the_step_and_sql_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sql(sql: str, limit: int = 1000) -> SqlResult:
        if sql.upper().startswith("ACTIVATE USL TABLE") and "recorded_stage" in sql:
            raise ZetarisError("[FIELD_NOT_FOUND] No such struct field lymph_nodes_positive")
        return SqlResult([], [])

    monkeypatch.setattr("app.usl.setup.discover_user", lambda: ("oa_user", [_PASSWORD]))
    monkeypatch.setattr("app.usl.setup.apply_ddl", lambda *_args: None)
    monkeypatch.setattr("app.usl.setup.run_sql", fake_sql)
    with respx.mock:
        respx.post("https://zetaris.test/ndp-files/createdir").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        respx.post("https://zetaris.test/ndp-files/save").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with pytest.raises(SetupError, match="step=activate recorded_stage") as excinfo:
            await setup()
    assert "sql=052_activate_recorded_stage.sql" in str(excinfo.value)
    assert "FIELD_NOT_FOUND" in str(excinfo.value)


def test_teardown_requires_yes(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["usl", "teardown"])
    assert code == 2
    out = capsys.readouterr().out
    assert "--yes" in out
    assert "registry_audit" in out
    assert "REG_FILES" in out
    assert "GDC_REST" in out
