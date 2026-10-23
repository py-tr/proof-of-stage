"""Helpers for model answer text."""

from __future__ import annotations

import re

# The opening tag is optional: Ultra through Nightshift 1.2.3 sends its reasoning inside the
# answer text ending in "</think>" with no "<think>" before it (probe 2026-10-23).
_THINK_RE = re.compile(r"^\s*(?:<think>)?.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Remove leading reasoning up to the first </think> (with or without <think>)."""
    return _THINK_RE.sub("", text, count=1).strip()
