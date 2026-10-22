"""Typed errors shared across providers."""


class EmptyAnswer(Exception):
    """The model returned empty or whitespace-only content."""
