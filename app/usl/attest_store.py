"""Attestation storage: signed Nightshift receipts and re-read results as rows in Zetaris.

Two append-only Postgres tables, registered in Zetaris through the existing `oa_pg` datasource
(`app/usl/sql/006`-`008`): `attest_receipt` (one row per signed receipt, with the envelope as
Nightshift sent it and our sha256 of the messages and the answer) and `attestation` (one row
per stored report value re-read: the stored value, the signed reading, the outcome). They are
not part of the `stage_audit` USL, so no count or rule of the main layer changes.

Provenance at write time: an attestation row with a receipt is inserted only if that receipt is
already a row with signature_state 'verified' (the INSERT carries an EXISTS check, so the layer
refuses it otherwise, whatever the Python side does). Rows are never updated or deleted.
"""

from __future__ import annotations

import json
from typing import Any

from app.usl.client import _insert_where_missing, _require_text
from app.usl.model import PG_SOURCE
from app.usl.sqltext import load_sql, sql_int, sql_string
from app.zetaris import run_sql

RECEIPT_TABLE = f"{PG_SOURCE}.attest_receipt"
ATTEST_TABLE = f"{PG_SOURCE}.attestation"
RECEIPT_COLUMNS = (
    "receipt_id",
    "item_id",
    "served_model",
    "route_kind",
    "signer_fingerprint",
    "signature_state",
    "cache_status",
    "prompt_chars",
    "messages_sha256",
    "answer_sha256",
    "envelope_json",
    "created_at",
)
ATTEST_COLUMNS = (
    "attest_id",
    "run",
    "case_id",
    "field",
    "stored_value",
    "stored_quote",
    "stored_quote_rechecked",
    "signed_value",
    "signed_quote",
    "outcome",
    "receipt_id",
    "created_at",
)
OUTCOMES = ("reproduced", "differs", "not_re_accepted", "provider_failure")


def insert_receipt_sql(
    *,
    receipt_id: str,
    item_id: str | None,
    served_model: str | None,
    route_kind: str | None,
    signer_fingerprint: str | None,
    signature_state: str | None,
    cache_status: str | None,
    prompt_chars: int | None,
    messages_sha256: str | None,
    answer_sha256: str | None,
    envelope: dict[str, Any] | None,
    created_at: str,
) -> str:
    _require_text(receipt_id, "receipt_id")
    _require_text(created_at, "created_at")
    values = {
        "receipt_id": sql_string(receipt_id),
        "item_id": sql_string(item_id),
        "served_model": sql_string(served_model),
        "route_kind": sql_string(route_kind),
        "signer_fingerprint": sql_string(signer_fingerprint),
        "signature_state": sql_string(signature_state),
        "cache_status": sql_string(cache_status),
        "prompt_chars": sql_int(prompt_chars),
        "messages_sha256": sql_string(messages_sha256),
        "answer_sha256": sql_string(answer_sha256),
        "envelope_json": sql_string(json.dumps(envelope, sort_keys=True) if envelope else None),
        "created_at": sql_string(created_at),
    }
    predicate = f"existing.receipt_id = {sql_string(receipt_id)}"
    return _insert_where_missing(RECEIPT_TABLE, RECEIPT_COLUMNS, values, predicate)


def insert_attestation_sql(
    *,
    attest_id: str,
    run: str,
    case_id: str,
    field: str,
    stored_value: str | None,
    stored_quote: str | None,
    stored_quote_rechecked: str | None,
    signed_value: str | None,
    signed_quote: str | None,
    outcome: str,
    receipt_id: str | None,
    created_at: str,
) -> str:
    for value, name in ((attest_id, "attest_id"), (run, "run"), (case_id, "case_id")):
        _require_text(value, name)
    _require_text(field, "field")
    _require_text(created_at, "created_at")
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown attestation outcome {outcome!r}")
    values = {
        "attest_id": sql_string(attest_id),
        "run": sql_string(run),
        "case_id": sql_string(case_id),
        "field": sql_string(field),
        "stored_value": sql_string(stored_value),
        "stored_quote": sql_string(stored_quote),
        "stored_quote_rechecked": sql_string(stored_quote_rechecked),
        "signed_value": sql_string(signed_value),
        "signed_quote": sql_string(signed_quote),
        "outcome": sql_string(outcome),
        "receipt_id": sql_string(receipt_id),
        "created_at": sql_string(created_at),
    }
    predicate = f"existing.attest_id = {sql_string(attest_id)}"
    also = None
    if receipt_id is not None:
        also = (
            f"EXISTS (\n  SELECT 1 FROM {RECEIPT_TABLE} AS signed\n"
            f"  WHERE signed.receipt_id = {sql_string(receipt_id)} "
            "AND signed.signature_state = 'verified'\n)"
        )
    elif outcome != "provider_failure":
        raise ValueError("a reading without a receipt can only be recorded as provider_failure")
    return _insert_where_missing(ATTEST_TABLE, ATTEST_COLUMNS, values, predicate, also)


async def setup_attestation() -> None:
    """Create the two tables in oa-pg and register them in Zetaris (idempotent)."""
    from app.usl.postgres import apply_ddl, discover_user

    user, secrets = discover_user()
    apply_ddl(user, load_sql("006_postgres_attestation.sql"), secrets)
    for name in ("007_register_attest_receipt.sql", "008_register_attestation.sql"):
        try:
            await run_sql(load_sql(name).strip())
        except Exception as exc:  # already registered is fine; anything else is raised
            if "exist" not in str(exc).lower():
                raise
