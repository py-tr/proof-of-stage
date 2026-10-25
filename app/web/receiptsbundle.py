"""The committed Nightshift receipts for the /receipts page, served as recorded (no model call).

Each bundle is a docs/evidence/attest/*envelopes.jsonl file written by a pre-registered run. The
page checks every Ed25519 signature in the browser against the committed public key, so it does
not have to trust this server; the server only hands over the files.
"""

from __future__ import annotations

import json
from typing import Any

from app.verify import BUNDLE, NOT_ESTABLISHED

BUNDLES = {
    "attest": (
        "envelopes.jsonl",
        "Attestation census: every stored value re-read once (42 values, 26 cases)",
    ),
    "agent-probe-4": (
        "agent-probe-4-envelopes.jsonl",
        "Agent probe 4: the agent's queries, including the refused overwrites",
    ),
    "hidden-2": ("hidden-2-envelopes.jsonl", "Hidden-error census 2: 300 consistent records"),
    "colon": (
        "colon-read-envelopes.jsonl",
        "Colorectal read (a second cancer type, a published miss)",
    ),
    "irs": ("irs-read-envelopes.jsonl", "IRS 990-EZ read (a non-medical domain, a published miss)"),
}
_KEEP = ("case", "receipt_id", "served_model", "run", "envelope")


def bundle_list() -> list[dict[str, Any]]:
    return [
        {"id": key, "label": label, "present": (BUNDLE / name).exists()}
        for key, (name, label) in BUNDLES.items()
    ]


def bundle(key: str) -> dict[str, Any] | None:
    if key not in BUNDLES:
        return None
    path = BUNDLE / BUNDLES[key][0]
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if isinstance((row.get("envelope") or {}).get("body"), dict):
                    rows.append({k: row.get(k) for k in _KEEP})
    pin = json.loads((BUNDLE / "pubkey.json").read_text(encoding="utf-8"))
    return {
        "id": key,
        "label": BUNDLES[key][1],
        "pubkey_b64": pin["pubkey_b64"],
        "fingerprint": pin["fingerprint"],
        "rows": rows,
        "not_established": NOT_ESTABLISHED,
    }
