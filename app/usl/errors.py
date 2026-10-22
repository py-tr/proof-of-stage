"""Errors for semantic-layer setup. Messages stay free of secrets and URLs."""

from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


class SetupError(Exception):
    """Setup or teardown failed. The message names the step and SQL file."""

    def __init__(
        self,
        message: str,
        *,
        step: str | None = None,
        sql_file: str | None = None,
    ) -> None:
        self.step = step
        self.sql_file = sql_file
        parts: list[str] = []
        if step:
            parts.append(f"step={step}")
        if sql_file:
            parts.append(f"sql={sql_file}")
        prefix = " ".join(parts)
        super().__init__(f"{prefix}: {message}" if prefix else message)


def public_error(text: str, secrets: list[str] | None = None) -> str:
    """Drop URLs, bearer tokens, and known secret values from a message."""
    cleaned = _URL_RE.sub("", text)
    cleaned = _BEARER_RE.sub("Bearer <redacted>", cleaned)
    for secret in secrets or []:
        if secret:
            cleaned = cleaned.replace(secret, "<redacted>")
    return " ".join(cleaned.split())
