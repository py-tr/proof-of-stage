"""Operator CLI. `python -m app.cli doctor` checks each dependency."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from uuid import uuid4

from app import config, zetaris
from app.providers import nightshift, nvidia
from app.providers.errors import EmptyAnswer

_PING_MAX_TOKENS = 800
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


def _line(ok: bool, name: str, reason: str) -> str:
    status = "PASS" if ok else "FAIL"
    return f"{status}  {name}: {reason}"


def _sanitize(text: str) -> str:
    cleaned = _URL_RE.sub("", text)
    cleaned = _BEARER_RE.sub("Bearer <redacted>", cleaned)
    for value in config.secret_values():
        cleaned = cleaned.replace(value, "<redacted>")
    return " ".join(cleaned.split())


def _exc_reason(exc: BaseException) -> str:
    return _sanitize(f"{type(exc).__name__}: {exc}")


def _require_text(text: str, label: str) -> str:
    if not text.strip():
        raise EmptyAnswer(f"{label} returned an empty answer")
    return text


async def _doctor() -> int:
    lines: list[str] = []
    failed = 0

    described = config.describe()
    unset = [name for name, state in described.items() if state == "unset"]
    config_ok = not unset
    if config_ok:
        reason = "all variables set"
    else:
        reason = "unset: " + ", ".join(unset)
    lines.append(_line(config_ok, "config", reason))
    if not config_ok:
        failed += 1

    try:
        health = await nightshift.health()
        ok = health == "online"
        lines.append(_line(ok, "nightshift health", health))
        if not ok:
            failed += 1
    except Exception as exc:
        lines.append(_line(False, "nightshift health", _exc_reason(exc)))
        failed += 1

    try:
        text, receipt = await nightshift.chat(
            [{"role": "user", "content": "Reply with one word: ready"}],
            config.NS_LIGHTNING_CLOUD,
            item_id=f"doctor-chat-{uuid4().hex[:8]}",
            max_tokens=_PING_MAX_TOKENS,
        )
        _require_text(text, "nightshift chat")
        reason = (
            f"model={receipt.winning_model!r} kind={receipt.winning_kind!r} "
            f"egress={receipt.egress_destination!r} sources={receipt.context_sources!r} "
            f"receipt_id={receipt.receipt_id!r}"
        )
        lines.append(_line(True, "nightshift chat", reason))
    except Exception as exc:
        lines.append(_line(False, "nightshift chat", _exc_reason(exc)))
        failed += 1

    try:
        text, _record = await nightshift.local_job(
            [{"role": "user", "content": "Reply with one word: ready"}],
            item_id=f"doctor-local-{uuid4().hex[:8]}",
        )
        _require_text(text, "nightshift local-job")
        lines.append(_line(True, "nightshift local-job", f"text={text!r}"))
    except Exception as exc:
        lines.append(_line(False, "nightshift local-job", _exc_reason(exc)))
        failed += 1

    try:
        text, served = await nvidia.chat(
            [{"role": "user", "content": "Reply with one word: ready"}],
            config.NV_SUPER,
            max_tokens=_PING_MAX_TOKENS,
        )
        _require_text(text, "nvidia chat")
        lines.append(_line(True, "nvidia chat", f"text={text!r} model={served!r}"))
    except Exception as exc:
        lines.append(_line(False, "nvidia chat", _exc_reason(exc)))
        failed += 1

    try:
        result = await zetaris.ping()
        lines.append(
            _line(True, "zetaris ping", f"rows={len(result.rows)} columns={result.columns!r}")
        )
    except Exception as exc:
        lines.append(_line(False, "zetaris ping", _exc_reason(exc)))
        failed += 1

    sys.stdout.write("\n".join(lines) + "\n")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check config and each external dependency")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return asyncio.run(_doctor())
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
