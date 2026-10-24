"""Zetaris retests from the 2026-10-24 claims audit (open-agent/research/claims-audit-2026-10-24.md).

Every write goes to a throwaway namespace (lightning.metastore.retest_scratch), which is dropped at
the end; the only statements on stage_audit are read-only (RUN DQ, SELECT). Each statement's
outcome (ok, row count or the exact error text) is logged to logs/zetaris-retest-2026-10-24.jsonl.

    python scripts/zetaris_retest.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.zetaris import run_sql  # noqa: E402

LOG = ROOT / "logs" / "zetaris-retest-2026-10-24.jsonl"
NS = "lightning.metastore.retest_scratch"
LIVE = "lightning.metastore.registry_audit.stage_audit"
READ_ONLY_ON_LIVE = ("RUN DQ", "SELECT")


async def step(name: str, sql: str, note: str = "") -> dict:
    if "registry_audit" in sql and not sql.lstrip().upper().startswith(READ_ONLY_ON_LIVE):
        raise RuntimeError(f"refusing a write on the live layer: {name}")
    row: dict = {"step": name, "note": note, "sql": sql[:600], "at": datetime.now(UTC).isoformat()}
    started = time.monotonic()
    try:
        result = await run_sql(sql, limit=50)
        row["ok"] = True
        row["rows"] = result.rows[:5]
        row["row_count"] = len(result.rows)
    except Exception as exc:  # the error text is the finding
        row["ok"] = False
        row["error"] = f"{type(exc).__name__}: {exc}"[:600]
    row["seconds"] = round(time.monotonic() - started, 2)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    shown = row.get("error") or f"rows={row.get('row_count')} {json.dumps(row.get('rows'), default=str)[:200]}"
    print(f"{'OK ' if row['ok'] else 'ERR'} {name:28s} {row['seconds']:>5}s  {shown}")
    return row


def compile_one(usl: str, ddl: str) -> str:
    return f"COMPILE USL {usl} DEPLOY NAMESPACE {NS} DDL\n{ddl}"


async def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    await step("ns_create", f"CREATE NAMESPACE IF NOT EXISTS {NS}")

    # 1. Types and names: is `double` really rejected?
    await step("ddl_double", compile_one("t_double",
               "CREATE TABLE t (id varchar(16) NOT NULL PRIMARY KEY, x double);"), "README:174 claim")
    await step("ddl_decimal", compile_one("t_decimal",
               "CREATE TABLE t (id varchar(16) NOT NULL PRIMARY KEY, x decimal(9,6));"))
    await step("ddl_bare_varchar", compile_one("t_varchar",
               "CREATE TABLE t (id varchar(16) NOT NULL PRIMARY KEY, x varchar);"), "polyglot.md:35")
    await step("ddl_text_kind_names", compile_one("t_names",
               "CREATE TABLE t (id varchar(16) NOT NULL PRIMARY KEY, text varchar(10), kind varchar(10));"),
               "the renamed parse_block columns")
    await step("ddl_doc_table", compile_one("t_doc",
               "CREATE TABLE doc (id varchar(16) NOT NULL PRIMARY KEY, x varchar(10));"), "table named doc")

    # 2. UPDATE USL ... AS: does it keep activation?
    await step("activate_double", f"ACTIVATE USL TABLE {NS}.t_double.t AS SELECT 'a' AS id, CAST(1.5 AS DOUBLE) AS x")
    await step("select_double_before", f"SELECT * FROM {NS}.t_double.t")
    loaded = await step("load_double", f"LOAD USL t_double NAMESPACE {NS}")
    contract = None
    if loaded.get("ok") and loaded.get("rows"):
        first = loaded["rows"][0]
        contract = next((v for v in (first.values() if isinstance(first, dict) else first) if isinstance(v, str) and v.startswith("{")), None)
    if contract:
        await step("update_usl_as", f"UPDATE USL t_double NAMESPACE {NS} AS {contract}")
        await step("select_double_after", f"SELECT * FROM {NS}.t_double.t", "documented: activation cleared")
    else:
        print("   (no LOAD USL JSON found; UPDATE USL step skipped)")

    # 3. Zetaris-native table CRUD (BUILD-JOURNAL Z1 "Not exist")
    await step("native_create", f"CREATE TABLE {NS}.native_t (id STRING, v INT)")
    await step("native_insert", f"INSERT INTO {NS}.native_t VALUES ('a', 1)")
    await step("native_select", f"SELECT * FROM {NS}.native_t")

    # 4. Composite key RUN DQ with backquotes (reference §14.6), read-only on the live layer
    await step("rundq_composite_backquoted",
               f"RUN DQ `case_id,page_no,block_index` TABLE {LIVE}.parse_block", "reference §14.6 form")
    await step("rundq_case_id", f"RUN DQ case_id TABLE {LIVE}.parse_block", "what our step 9 runs")
    await step("distinct_case_ids", f"SELECT count(*) AS n, count(DISTINCT case_id) AS cases FROM {LIVE}.parse_block")

    # 5. REST round-trip time
    times = []
    for i in range(10):
        r = await step(f"select1_{i}", "SELECT 1 AS one")
        times.append(r["seconds"])
    print(f"   SELECT 1 x10: median {statistics.median(times)} s, min {min(times)}, max {max(times)}")

    # cleanup
    await step("ns_drop", f"DROP NAMESPACE IF EXISTS {NS} CASCADE")


if __name__ == "__main__":
    asyncio.run(main())
