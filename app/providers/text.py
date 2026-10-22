"""Helpers for model answer text."""

from __future__ import annotations

import re

_THINK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Remove a leading <think>…</think> block (empty or not) and surrounding whitespace."""
    return _THINK_RE.sub("", text, count=1).strip()
