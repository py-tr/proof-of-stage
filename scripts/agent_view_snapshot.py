"""Snapshot the checked values for agent probe 5 into their own Zetaris file-store table.

A Zetaris view needs its reader to have access to its source table, and `stage_check` also holds
the raw count, so the agent role instead gets a separate Lightning database, AGENT_FILES, whose
one table `node_status` is a dated copy of `case_id, positive_nodes_checked, fault_field` from the
live layer. This script reads those three columns as admin, uploads them as
file-store/agent/node_status.csv (the same REST calls `usl setup` uses) and prints the row count,
the node-positive count and the CSV's sha16 for the pre-registration. Re-running replaces the file.

    python scripts/agent_view_snapshot.py
"""

import asyncio
import csv
import io
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.dial import sha16  # noqa: E402
from app.usl.files import _create_dir, _save, require_zetaris_config  # noqa: E402
from app.usl.model import table_fqn  # noqa: E402
from app.zetaris import run_sql  # noqa: E402

STORE = "file-store/agent"


async def main() -> None:
    require_zetaris_config()
    result = await run_sql(
        f"SELECT case_id, positive_nodes_checked, fault_field FROM {table_fqn('stage_check')} "
        "ORDER BY case_id",
        limit=5000,
    )
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["case_id", "positive_nodes_checked", "fault_field"])
    for row in result.rows:
        values = list(row.values()) if isinstance(row, dict) else list(row)
        writer.writerow(["" if v is None else v for v in values])
    text = buf.getvalue()
    async with httpx.AsyncClient(timeout=60.0) as client:
        await _create_dir(client, STORE)
        await _save(client, STORE, "node_status.csv", text.encode("utf-8"))
    count = await run_sql("SELECT count(*) FROM AGENT_FILES.node_status", limit=1)
    positive = await run_sql(
        "SELECT count(*) FROM AGENT_FILES.node_status "
        "WHERE CAST(positive_nodes_checked AS DOUBLE) > 0",
        limit=1,
    )
    print(
        f"rows uploaded {len(result.rows)}; table rows {count.rows[0]}; node-positive {positive.rows[0]}"
    )
    print(f"csv sha16 {sha16(text)}")


if __name__ == "__main__":
    asyncio.run(main())
