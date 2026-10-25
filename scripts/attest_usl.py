"""A second, small USL for the attestations: `attest_audit`, with DQ rules a judge can run.

The signed receipts and re-read results already live in our Postgres (`oa_pg.attest_receipt`,
`oa_pg.attestation`, app/usl/attest_store.py). This puts them in a USL of their own, beside
`stage_audit` in the same namespace (nothing in `stage_audit` changes), and registers five rules
(app/usl/sql/090-093): every receipt signed by the pinned key, answered by a Nemotron, not
served from cache; every attestation backed by a verified receipt; every attestation reproduced.
In the Zetaris GUI: `RUN DQ <rule> TABLE lightning.metastore.registry_audit.attest_audit.<table>`.

    python scripts/attest_usl.py setup   # idempotent: compile if missing, activate, register rules
    python scripts/attest_usl.py dq      # run every rule, print total / valid / invalid
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.usl.client import parse_dq_counts  # noqa: E402
from app.usl.sqltext import load_sql, load_statements  # noqa: E402
from app.zetaris import run_sql  # noqa: E402

NAMESPACE = "lightning.metastore.registry_audit"
USL = f"{NAMESPACE}.attest_audit"
RULES = (
    ("receipt_signed", "receipt"),
    ("receipt_nemotron", "receipt"),
    ("receipt_not_cached", "receipt"),
    ("attested", "attestation"),
    ("reproduced", "attestation"),
)


async def _try(label: str, sql: str) -> None:
    try:
        await run_sql(sql, limit=10)
        print(f"ok    {label}")
    except Exception as exc:  # an "already exists" is fine on a re-run; anything else is shown
        print(f"note  {label}: {str(exc)[:160]}")


async def setup() -> None:
    listing = await run_sql(f"SHOW NAMESPACES OR TABLES IN {NAMESPACE}", limit=200)
    if "attest_audit" in str(listing.rows).lower():
        print("ok    usl attest_audit exists")
    else:
        await _try("compile usl attest_audit", load_sql("090_compile_attest_audit.sql"))
    await _try("activate receipt", load_sql("091_activate_receipt.sql"))
    await _try("activate attestation", load_sql("092_activate_attestation.sql"))
    for statement in load_statements("093_dq_attest_rules.sql"):
        await _try("register " + statement.split()[2], statement)


async def dq() -> None:
    for rule, table in RULES:
        result = await run_sql(f"RUN DQ {rule} TABLE {USL}.{table}", limit=100)
        c = parse_dq_counts(rule, result)
        print(
            f"{rule:20s} {table:12s} total {c.total:4d}  valid {c.valid:4d}  invalid {c.invalid:4d}"
        )


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        asyncio.run(setup())
    elif command == "dq":
        asyncio.run(dq())
    else:
        print(__doc__)
