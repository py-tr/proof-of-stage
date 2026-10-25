"""Attestation census: every stored report value re-read once, with a signed receipt kept.

Pre-registered in docs/preregistration/attest.md (the frozen cell list, the rule for
"reproduced" and the code hashes in attest.json, before the first call). The stored N and
positive-node values (oa_pg.derived_extraction, method nemotron_reader) were first written by
NVIDIA-direct reads without receipts and stay as they are (first write wins). Here each of their
cases goes once through the shipped evidence steps (`rungs.climb`, Nightshift, the model pinned
in a signed receipt, no cache, fresh item ids) inside `envelope_tap.capture()`, so every
envelope is kept with our sha256 of the messages and the answer. Per cell: the value the steps
closed is compared with the stored one (the same normalisation as the ladder's own comparison):
reproduced / differs / not_re_accepted / provider_failure. Separately, with no model, the stored
quote is re-checked under today's guard. Receipts and outcomes are written to the Zetaris
attestation tables (an attestation row needs a verified receipt row first). "Reproduced" means
the same value was read again, not that it is correct.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.engine.run_case import load_evidence
from app.engine.rungs import _comparable, climb
from app.providers import envelope_tap
from app.providers.receipts import _signed_receipt, key_fingerprint
from app.reader.reader import NODES_POSITIVE, judge_count, judge_field
from app.usl import attest_store
from app.usl.client import select
from app.zetaris import run_sql

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "attest.json"
LOG = ROOT / "logs" / "attest.jsonl"
RUNS_LOG = ROOT / "logs" / "attest-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "envelopes.jsonl"
FIELDS = ("N", "NPOS")
CELLS_SQL = (
    "SELECT case_id, field, value, quote FROM oa_pg.derived_extraction "
    "WHERE method = 'nemotron_reader' AND field IN ('N', 'NPOS') ORDER BY case_id, field"
)
VOID_FAILED_CASES = 5
FROZEN_FILES = (
    "app/engine/attest.py",
    "app/providers/envelope_tap.py",
    "app/usl/attest_store.py",
    "app/engine/rungs.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


async def current_cells() -> list[dict[str, Any]]:
    rows = (await select(CELLS_SQL, limit=1000)).rows
    return [{"case": r[0], "field": r[1], "value": r[2], "quote": r[3]} for r in rows]


def outcome(field: str, stored: Any, signed: Any) -> str:
    if signed is None:
        return "not_re_accepted"
    same = _comparable(field, str(stored)) == _comparable(field, str(signed))
    return "reproduced" if same else "differs"


def receipt_row(call: dict[str, Any], created_at: str) -> dict[str, Any] | None:
    """A receipt table row from one captured call, the signature checked again here."""
    envelope = call.get("envelope")
    if not isinstance(envelope, dict):
        return None
    state, signed, key = _signed_receipt(envelope)
    receipt_id = signed.get("receipt_id")
    if not receipt_id:
        return None
    route = signed.get("winning_route") if isinstance(signed.get("winning_route"), dict) else {}
    cache = signed.get("cache") if isinstance(signed.get("cache"), dict) else {}
    return {
        "receipt_id": receipt_id,
        "item_id": call.get("item_id"),
        "served_model": route.get("model"),
        "route_kind": route.get("kind"),
        "signer_fingerprint": key_fingerprint(key),
        "signature_state": state,
        "cache_status": cache.get("status"),
        "prompt_chars": signed.get("prompt_chars"),
        "messages_sha256": call.get("messages_sha256"),
        "answer_sha256": call.get("answer_sha256"),
        "envelope": envelope,
        "created_at": created_at,
    }


def _rechecked(field: str, value: Any, quote: Any, report: str) -> str:
    """Today's guard on the stored value and quote (no model): 'accepted' or the reason."""
    if field == NODES_POSITIVE:
        result = judge_count({"N_positive": value, "N_positive_quote": quote}, report)
    else:
        result = judge_field(field, {field: value, f"{field}_quote": quote}, report)  # type: ignore[arg-type]
    return "accepted" if result.status == "accepted" else (result.reason or result.status)


async def run_attest() -> dict[str, Any]:
    record = frozen()
    cells = record["cells"]
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    by_case: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        by_case.setdefault(cell["case"], []).append(cell)
    rows, failed_cases = [], 0
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id, case_cells in by_case.items():
        created_at = datetime.now(UTC).isoformat()
        try:
            evidence = await load_evidence(case_id)
            with envelope_tap.capture() as calls:
                ladder = await climb(
                    evidence, run_id=f"attest-{tag}-{case_id}-{uuid.uuid4().hex[:6]}"
                )
        except Exception as exc:  # a failure: recorded, never re-run
            failed_cases += 1
            for cell in case_cells:
                rows.append(
                    {
                        **_base(cell, tag, created_at),
                        "outcome": "provider_failure",
                        "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                    }
                )
            continue
        receipts = [r for r in (receipt_row(c, created_at) for c in calls) if r]
        for receipt in receipts:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"case": case_id, "run": tag, **receipt}, sort_keys=True) + "\n"
                )
            await run_sql(attest_store.insert_receipt_sql(**receipt))
        for cell in case_cells:
            closing = ladder.closings.get(cell["field"])
            fr, rr = closing if closing else (None, None)
            row = {
                **_base(cell, tag, created_at),
                "stored_quote_rechecked": _rechecked(
                    cell["field"], cell["value"], cell["quote"], evidence.report_text
                ),
                "signed_value": fr.value if fr else None,
                "signed_quote": fr.quote if fr else None,
                # an unsettled cell keeps the receipt of the last step that read it
                "receipt_id": rr.receipt_id if rr else _last_receipt(ladder.chunks),
                "rung": (ladder.closed.get(cell["field"]) or {}).get("rung"),
                "outcome": outcome(cell["field"], cell["value"], fr.value if fr else None),
                "rungs": [c.get("rung") for c in ladder.chunks if c.get("rung")],
            }
            rows.append(row)
        for row in rows[-len(case_cells) :]:
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    for row in rows:
        if row["outcome"] != "provider_failure" and row.get("receipt_id") is None:
            row["outcome_note"] = "no receipt: kept in the log only"
            continue
        await run_sql(
            attest_store.insert_attestation_sql(
                attest_id=f"{tag}-{row['case']}-{row['field']}",
                run=tag,
                case_id=row["case"],
                field=row["field"],
                stored_value=row["stored_value"],
                stored_quote=row["stored_quote"],
                stored_quote_rechecked=row.get("stored_quote_rechecked"),
                signed_value=row.get("signed_value"),
                signed_quote=row.get("signed_quote"),
                outcome=row["outcome"],
                receipt_id=row.get("receipt_id"),
                created_at=row["created_at"],
            )
        )
    counts = {o: sum(r["outcome"] == o for r in rows) for o in attest_store.OUTCOMES}
    summary = {
        "run": tag,
        "cells": len(cells),
        "cases": len(by_case),
        "failed_cases": failed_cases,
        "void": failed_cases > VOID_FAILED_CASES,
        "outcomes": counts,
        "stored_quote_rechecked_accepted": sum(
            r.get("stored_quote_rechecked") == "accepted" for r in rows
        ),
        "claim": f"{counts['reproduced']} of {len(cells)} reproduced",
    }
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary


def _last_receipt(chunks: list[dict[str, Any]]) -> str | None:
    ids = [c.get("receipt_id") for c in chunks if c.get("receipt_id")]
    return ids[-1] if ids else None


def _base(cell: dict[str, Any], tag: str, created_at: str) -> dict[str, Any]:
    return {
        "case": cell["case"],
        "field": cell["field"],
        "run": tag,
        "stored_value": cell["value"],
        "stored_quote": cell["quote"],
        "created_at": created_at,
    }
