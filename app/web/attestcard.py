"""The attestation census on the /how page: every stored value re-read once, signed, checked here.

Read from logs/attest.jsonl (the census outcomes) and checked with app.verify (every committed
Nightshift envelope's Ed25519 signature against the committed public key, offline). The check runs
when the page asks, once per server process; no key, no network, no model call.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from typing import Any

from app.verify import NOT_ESTABLISHED, OUTCOMES_LOG, verify


@lru_cache(maxsize=1)
def attest_summary() -> dict[str, Any] | None:
    if not OUTCOMES_LOG.exists():
        return None
    rows = [json.loads(x) for x in OUTCOMES_LOG.read_text(encoding="utf-8").splitlines() if x]
    if not rows:
        return None
    check = verify()
    e2 = [r for r in rows if r.get("case") == "TCGA-E2-A572"]
    example = next((r for r in e2 if r["field"] == "NPOS"), e2[0] if e2 else rows[0])
    return {
        "values": len(rows),
        "cases": len({r["case"] for r in rows}),
        "fields": dict(Counter(r["field"] for r in rows)),
        "outcomes": dict(Counter(r.get("outcome") for r in rows)),
        "receipts": check["receipts"],
        "receipts_verified": check["receipts_verified"],
        "fingerprint": check["pinned_fingerprint"],
        "passed": check["passed"],
        "failures": len(check["failures"]),
        "example": {
            k: example.get(k)
            for k in ("case", "field", "stored_value", "signed_value", "signed_quote", "receipt_id")
        },
        "not_established": NOT_ESTABLISHED,
    }
