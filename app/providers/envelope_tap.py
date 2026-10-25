"""Keep every signed Nightshift receipt envelope a call returns, without touching the client.

`app/providers/nightshift.py` and `receipts.py` are frozen by an earlier pre-registration, and
`chat()` drops the envelope after `parse_receipt(payload)`. Inside `with capture() as calls:`
this module wraps `nightshift.chat` and `nightshift.parse_receipt` (module attributes, restored
on exit) and records, per HTTP answer: the envelope exactly as Nightshift sent it
({body, pubkey_b64, sig_b64}), the sha256 of the request messages and of the raw answer text,
and the item id. Outside the block nothing changes. The envelope's signed body does not hash the
answer; the two sha256 values are our own binding of a receipt to a prompt and an answer, and
are labelled as ours wherever they are shown.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
from collections.abc import Iterator
from typing import Any

from app.providers import nightshift

_calls: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "envelope_calls", default=None
)
_request: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "envelope_request", default=None
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def messages_sha256(messages: list[dict[str, Any]]) -> str:
    """A canonical hash of the messages a caller sent (sorted keys, no spaces)."""
    canonical = json.dumps(messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_text(canonical)


def _raw_answer(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def _record(payload: dict[str, Any]) -> None:
    calls = _calls.get()
    if calls is None:
        return
    meterless = payload.get("meterless") if isinstance(payload.get("meterless"), dict) else {}
    request = _request.get() or {}
    calls.append(
        {
            "item_id": request.get("item_id"),
            "model_requested": request.get("model"),
            "messages_sha256": request.get("messages_sha256"),
            "messages_chars": request.get("messages_chars"),
            "answer_sha256": sha256_text(_raw_answer(payload)),
            "answer_chars": len(_raw_answer(payload)),
            "served_model": payload.get("model"),
            "envelope": meterless.get("receipt_envelope"),
        }
    )


@contextlib.contextmanager
def capture() -> Iterator[list[dict[str, Any]]]:
    """Record every envelope returned inside the block; yields the list being filled."""
    original_parse = nightshift.parse_receipt
    original_chat = nightshift.chat
    calls: list[dict[str, Any]] = []
    token = _calls.set(calls)

    def tapped_parse(payload: dict[str, Any]) -> Any:
        _record(payload)
        return original_parse(payload)

    async def tapped_chat(messages: list[dict[str, Any]], model: str, **kwargs: Any) -> Any:
        req = _request.set(
            {
                "item_id": kwargs.get("item_id"),
                "model": model,
                "messages_sha256": messages_sha256(messages),
                "messages_chars": sum(len(str(m.get("content") or "")) for m in messages),
            }
        )
        try:
            return await original_chat(messages, model, **kwargs)
        finally:
            _request.reset(req)

    nightshift.parse_receipt = tapped_parse
    nightshift.chat = tapped_chat
    try:
        yield calls
    finally:
        nightshift.parse_receipt = original_parse
        nightshift.chat = original_chat
        _calls.reset(token)
