"""Locate a model's quote verbatim in the source text.

A quote is accepted only when, after ignoring case, punctuation and ALL whitespace
(OCR splits tokens like "pN x" / "pNx" at random), it is a contiguous substring of
the report. The returned offsets point into the ORIGINAL report text, so the UI can
highlight the exact span.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_QUOTE_CHARS = 4  # of letters/digits; shorter quotes prove nothing


@dataclass(frozen=True)
class Span:
    start: int
    end: int  # exclusive

    def text(self, source: str) -> str:
        return source[self.start : self.end]


def _normalise(text: str) -> tuple[str, list[int]]:
    """Lowercased letters/digits only, plus a map back to source indices."""
    chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        if char.isalnum():
            chars.append(char.lower())
            index_map.append(index)
    return "".join(chars), index_map


def is_too_short(quote: str | None) -> bool:
    """Quotes with fewer than 4 letters/digits prove nothing on their own."""
    return len(_normalise(quote or "")[0]) < _MIN_QUOTE_CHARS


def locate(quote: str | None, source: str) -> Span | None:
    """Span of `quote` inside `source`, or None if it is not there verbatim."""
    if not quote:
        return None
    needle, _ = _normalise(quote)
    if len(needle) < _MIN_QUOTE_CHARS:
        return None
    haystack, index_map = _normalise(source)
    at = haystack.find(needle)
    if at < 0:
        return None
    start = index_map[at]
    end = index_map[at + len(needle) - 1] + 1
    return Span(start=start, end=end)
