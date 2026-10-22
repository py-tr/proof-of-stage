"""Parse and verify Meterless Nightshift receipts.

Nightshift signs each receipt: `meterless.receipt_envelope` = {body, pubkey_b64, sig_b64},
Ed25519 over the body serialised as sorted, compact, UTF-8 JSON (measured 2026-10-22).
When the signature verifies, every field we enforce is read from the SIGNED copy, and a
disagreement with the unsigned copy makes the signature "invalid".
"""

from __future__ import annotations

import base64
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import is_local_nemotron_lane

Kind = Literal["local", "cloud"]
SignatureState = Literal["verified", "invalid", "absent"]


class ReceiptMismatch(Exception):
    """The Nightshift receipt does not match what the caller required."""


class Receipt(BaseModel):
    receipt_id: str | None = None
    winning_model: str | None = None
    winning_kind: str | None = None
    egress_destination: str | None = None
    context_sources: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    usage: dict[str, Any] = Field(default_factory=dict)  # tokens, from the response
    from_cache: bool | None = None
    cache_status: str | None = None
    signature: SignatureState = "absent"
    signer_key: str | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _first(*candidates: Any) -> Any:
    for value in candidates:
        if value is not None:
            return value
    return None


def _latency_ms(meterless: dict[str, Any], raw_receipt: dict[str, Any]) -> int | None:
    usage = _as_dict(meterless.get("usage")) or _as_dict(raw_receipt.get("usage"))
    latency = _first(
        usage.get("latency_ms"),
        meterless.get("latency_ms"),
        raw_receipt.get("latency_ms"),
    )
    if isinstance(latency, int | float):
        return int(latency)
    return None


def canonical_body(body: Any) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _js_number(value: float) -> str:
    """A float as JavaScript prints it (1.0 -> 1, 5e-05 -> 0.00005, 1e+21 stays exponent)."""
    from decimal import Decimal

    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    text = repr(value)
    if "e" not in text:
        return text
    mantissa, exponent = text.split("e")
    power = int(exponent)
    if -7 < power < 21:
        return format(Decimal(text), "f")
    return f"{mantissa}e{'+' if power > 0 else '-'}{abs(power)}"


def _js_json(value: Any) -> str:
    if isinstance(value, dict):
        items = sorted(value.items())
        return "{" + ",".join(f"{_js_json(str(k))}:{_js_json(v)}" for k, v in items) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_js_json(v) for v in value) + "]"
    if isinstance(value, float):
        return _js_number(value)
    return json.dumps(value, ensure_ascii=False)


def canonical_bodies(body: Any) -> list[bytes]:
    """Candidate serialisations of a signed body. The first verified every real receipt we
    saw; the second prints numbers as JavaScript does, in case a body carries one of the
    floats the two disagree on (5e-05, 1.0). Both are sorted, compact, UTF-8."""
    first = canonical_body(body)
    second = _js_json(body).encode("utf-8")
    return [first] if second == first else [first, second]


def _signed_receipt(envelope: dict[str, Any]) -> tuple[SignatureState, dict[str, Any], str | None]:
    """(state, the signed receipt dict, the signer's public key)."""
    body, key_b64, sig_b64 = (
        envelope.get("body"),
        envelope.get("pubkey_b64"),
        envelope.get("sig_b64"),
    )
    if not (isinstance(body, dict) and isinstance(key_b64, str) and isinstance(sig_b64, str)):
        return "absent", {}, None
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64))
        signature = base64.b64decode(sig_b64)
    except (ValueError, TypeError):
        return "invalid", {}, key_b64
    for candidate in canonical_bodies(body):
        try:
            key.verify(signature, candidate)
        except InvalidSignature:
            continue
        return "verified", _as_dict(body.get("receipt")), key_b64
    return "invalid", {}, key_b64


def parse_receipt(payload: dict[str, Any]) -> Receipt:
    """Build a Receipt. Prefer meterless top-level fields, then meterless.receipt."""
    meterless = _as_dict(payload.get("meterless"))
    raw_receipt = _as_dict(meterless.get("receipt"))
    signature, signed, signer_key = _signed_receipt(_as_dict(meterless.get("receipt_envelope")))
    if signature == "verified":
        unsigned = _receipt_fields(meterless, raw_receipt)
        if not _has_sent_block(meterless, raw_receipt):
            unsigned["context_sources"] = None  # absent unsigned block: nothing to compare
        trusted = _receipt_fields({}, signed)
        if any(unsigned[k] is not None and unsigned[k] != trusted[k] for k in trusted):
            signature = "invalid"  # the unsigned fields were altered
        else:
            meterless, raw_receipt = {}, signed
    receipt = _build(meterless, raw_receipt)
    top = _as_dict(payload.get("meterless"))
    # prefer the SIGNED cache status when the signature verified
    cache = _as_dict(signed.get("cache")) if signature == "verified" else {}
    cache = cache or _as_dict(top.get("cache"))
    from_cache = top.get("from_cache")
    if signature == "verified" and isinstance(cache.get("status"), str):
        from_cache = cache["status"] == "hit"
    return receipt.model_copy(
        update={
            "usage": _as_dict(payload.get("usage")),
            "from_cache": from_cache if isinstance(from_cache, bool) else None,
            "cache_status": cache.get("status") if isinstance(cache.get("status"), str) else None,
            "signature": signature,
            "signer_key": signer_key,
        }
    )


def _has_sent_block(meterless: dict[str, Any], raw_receipt: dict[str, Any]) -> bool:
    for source in (meterless, raw_receipt):
        if isinstance(_as_dict(source.get("egress")).get("sent"), dict):
            return True
    return False


def _receipt_fields(meterless: dict[str, Any], raw_receipt: dict[str, Any]) -> dict[str, Any]:
    built = _build(meterless, raw_receipt)
    return {
        "receipt_id": built.receipt_id,
        "winning_model": built.winning_model,
        "winning_kind": built.winning_kind,
        "egress_destination": built.egress_destination,
        "context_sources": built.context_sources,
    }


def _build(meterless: dict[str, Any], raw_receipt: dict[str, Any]) -> Receipt:
    winning_route = _as_dict(
        meterless.get("winning_route")
        if isinstance(meterless.get("winning_route"), dict)
        else raw_receipt.get("winning_route")
    )
    egress = _as_dict(
        meterless.get("egress")
        if isinstance(meterless.get("egress"), dict)
        else raw_receipt.get("egress")
    )
    sent = _as_dict(egress.get("sent"))
    receipt_id = _first(meterless.get("receipt_id"), raw_receipt.get("receipt_id"))
    return Receipt(
        receipt_id=str(receipt_id) if receipt_id is not None else None,
        winning_model=winning_route.get("model"),
        winning_kind=winning_route.get("kind"),
        egress_destination=egress.get("destination"),
        context_sources=_as_str_list(sent.get("context_sources")),
        latency_ms=_latency_ms(meterless, raw_receipt),
    )


def _egress_is_empty(destination: str | None) -> bool:
    if destination is None:
        return True
    return destination.strip().lower() in {"", "none", "null"}


def verify(
    receipt: Receipt,
    require_model: str | None = None,
    require_kind: Kind | None = None,
    require_family: str | None = "nvidia/nemotron",
    require_signature: bool = False,
    pinned_key: str | None = None,
    allow_cache: bool = True,
) -> Receipt:
    """Reject a receipt whose route or context sources do not match policy."""
    if not (receipt.receipt_id and str(receipt.receipt_id).strip()):
        raise ReceiptMismatch("missing receipt_id")
    if require_signature and receipt.signature != "verified":
        raise ReceiptMismatch(f"receipt signature {receipt.signature}")
    if pinned_key is not None and receipt.signer_key != pinned_key:
        raise ReceiptMismatch("receipt signed by an unexpected key")
    if not allow_cache and receipt.from_cache:
        raise ReceiptMismatch("answer served from the response cache, not a fresh read")
    if require_model is not None and receipt.winning_model != require_model:
        raise ReceiptMismatch(
            f"winning model {receipt.winning_model!r} != required {require_model!r}"
        )
    if require_kind is not None and receipt.winning_kind != require_kind:
        raise ReceiptMismatch(f"winning kind {receipt.winning_kind!r} != required {require_kind!r}")
    if require_kind == "local" and not _egress_is_empty(receipt.egress_destination):
        raise ReceiptMismatch(
            f"local kind requires empty egress destination, got {receipt.egress_destination!r}"
        )
    if require_family is not None:
        model = receipt.winning_model or ""
        kind = receipt.winning_kind or ""
        family_ok = model.startswith(require_family)
        local_ok = kind == "local" and is_local_nemotron_lane(model)
        if not family_ok and not local_ok:
            raise ReceiptMismatch(
                f"winning model {receipt.winning_model!r} is not family {require_family!r}"
            )
    if receipt.context_sources != ["messages"]:
        raise ReceiptMismatch(
            f"context_sources must be exactly ['messages'], got {receipt.context_sources!r}"
        )
    return receipt
