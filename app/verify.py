"""Offline check of the committed attestation bundle: no keys, no network, no model.

`python -m app.verify [CASE_ID ...]` reads docs/evidence/attest/ (the signed Nightshift
envelopes and the pinned public key) and logs/attest.jsonl (the census outcomes) and checks, per
case: every envelope's Ed25519 signature against the committed public key; the signed receipt
says a cloud Nemotron answered and the cache was not used; every outcome row points to a
verified receipt and its outcome follows from the stored and the re-read value; where the
report text exists on this machine, the re-read quote is word for word in it. It prints what a
pass does NOT establish. Exit code 1 if any check fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.providers.receipts import _signed_receipt, key_fingerprint

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs" / "evidence" / "attest"
OUTCOMES_LOG = ROOT / "logs" / "attest.jsonl"
NOT_ESTABLISHED = (
    "A pass does NOT establish: that the values are correct (only that one re-read gave them); "
    "what Nemotron answered (the signed body covers the call: model, route, cache, prompt size, "
    "not the answer text; the answer hash beside it is ours, not Nightshift's); that the public "
    "key belongs to anyone but the Nightshift install that produced these receipts (Meterless "
    "publishes no key); that no other run was made and left out."
)


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def pinned_fingerprint(bundle: Path = BUNDLE) -> str | None:
    pin = bundle / "pubkey.json"
    return json.loads(pin.read_text(encoding="utf-8"))["fingerprint"] if pin.exists() else None


def check_envelope(row: dict[str, Any], fingerprint: str | None) -> list[str]:
    """Problems with one committed receipt row (empty list = it checks out)."""
    state, signed, key = _signed_receipt(row.get("envelope") or {})
    problems = []
    if state != "verified":
        problems.append(f"signature {state}")
        return problems
    if fingerprint and key_fingerprint(key) != fingerprint:
        problems.append("signed by a key other than the committed one")
    if signed.get("receipt_id") != row.get("receipt_id"):
        problems.append("receipt id differs from the signed body")
    route = signed.get("winning_route") if isinstance(signed.get("winning_route"), dict) else {}
    if not str(route.get("model") or "").startswith(("nvidia/nemotron", "local-runtime/nemotron")):
        problems.append(f"signed model is {route.get('model')!r}")
    if route.get("model") != row.get("served_model"):
        problems.append("served model differs from the signed body")
    cache = signed.get("cache") if isinstance(signed.get("cache"), dict) else {}
    if cache.get("status") not in (None, "miss", "bypass"):
        problems.append(f"cache {cache.get('status')}")
    return problems


def check_outcome(row: dict[str, Any], verified_ids: set[str]) -> list[str]:
    from app.engine.attest import outcome

    problems = []
    if row.get("outcome") == "provider_failure":
        return problems
    if row.get("receipt_id") not in verified_ids:
        problems.append("outcome row has no verified receipt in the bundle")
    expected = outcome(row["field"], row.get("stored_value"), row.get("signed_value"))
    if expected != row.get("outcome"):
        problems.append(f"outcome {row.get('outcome')!r} does not follow from the values")
    return problems


def check_quote(row: dict[str, Any], report: str | None) -> str:
    """'ok', 'not checked (no report text here)', or the problem."""
    from app.reader.quotes import locate

    quote = row.get("signed_quote")
    if not quote:
        return "ok"
    if report is None:
        return "not checked (no report text on this machine)"
    return "ok" if locate(quote, report) is not None else "quote is not in the report"


def _reports() -> dict[str, str]:
    try:
        from app.reports.ingest import read_reports_csv

        return {case: r.report_text for case, r in read_reports_csv().items()}
    except Exception:  # the report corpus is not committed; the quote check is then skipped
        return {}


def verify(
    cases: list[str] | None = None, bundle: Path | None = None, log: Path | None = None
) -> dict[str, Any]:
    bundle = bundle or BUNDLE
    log = log or OUTCOMES_LOG
    fingerprint = pinned_fingerprint(bundle)
    envelopes = _lines(bundle / "envelopes.jsonl")
    outcomes = _lines(log)
    if cases:
        envelopes = [e for e in envelopes if e.get("case") in cases]
        outcomes = [o for o in outcomes if o.get("case") in cases]
    reports = _reports()
    failures: list[str] = []
    verified: set[str] = set()
    for row in envelopes:
        problems = check_envelope(row, fingerprint)
        if problems:
            failures.append(
                f"{row.get('case')} receipt {row.get('receipt_id')}: " + "; ".join(problems)
            )
        else:
            verified.add(row["receipt_id"])
    quotes = {"ok": 0, "skipped": 0}
    for row in outcomes:
        for problem in check_outcome(row, verified):
            failures.append(f"{row['case']} {row['field']}: {problem}")
        q = check_quote(row, reports.get(row["case"]))
        if q == "ok":
            quotes["ok"] += 1
        elif q.startswith("not checked"):
            quotes["skipped"] += 1
        else:
            failures.append(f"{row['case']} {row['field']}: {q}")
    return {
        "receipts": len(envelopes),
        "receipts_verified": len(verified),
        "outcome_rows": len(outcomes),
        "quotes": quotes,
        "pinned_fingerprint": fingerprint,
        "failures": failures,
        "passed": not failures and bool(envelopes),
    }


def main(argv: list[str]) -> int:
    result = verify(argv or None)
    print(
        f"receipts: {result['receipts_verified']} of {result['receipts']} verified "
        f"(key {result['pinned_fingerprint']})"
    )
    print(
        f"outcome rows: {result['outcome_rows']}; quotes checked: {result['quotes']['ok']}, "
        f"skipped: {result['quotes']['skipped']}"
    )
    for failure in result["failures"]:
        print("FAIL", failure)
    print("PASS" if result["passed"] else "FAIL")
    print(NOT_ESTABLISHED)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
