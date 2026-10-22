"""Parse and verify Meterless Nightshift receipts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import is_local_nemotron_lane

Kind = Literal["local", "cloud"]


class ReceiptMismatch(Exception):
    """The Nightshift receipt does not match what the caller required."""


class Receipt(BaseModel):
    receipt_id: str | None = None
    winning_model: str | None = None
    winning_kind: str | None = None
    egress_destination: str | None = None
    context_sources: list[str] = Field(default_factory=list)
    latency_ms: int | None = None


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


def parse_receipt(payload: dict[str, Any]) -> Receipt:
    """Build a Receipt. Prefer meterless top-level fields, then meterless.receipt."""
    meterless = _as_dict(payload.get("meterless"))
    raw_receipt = _as_dict(meterless.get("receipt"))
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
) -> Receipt:
    """Reject a receipt whose route or context sources do not match policy."""
    if not (receipt.receipt_id and str(receipt.receipt_id).strip()):
        raise ReceiptMismatch("missing receipt_id")
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
