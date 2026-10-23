from __future__ import annotations

from app.providers.text import strip_think


def test_strip_think_empty_block() -> None:
    assert strip_think("<think></think>\nready") == "ready"
    assert strip_think("  <think></think>  ready  ") == "ready"


def test_strip_think_non_empty_block() -> None:
    assert strip_think("<think>scratchpad</think>\nready") == "ready"


def test_strip_think_no_block() -> None:
    assert strip_think("ready") == "ready"
    assert strip_think("  ready  ") == "ready"


def test_strip_think_multiline() -> None:
    raw = "<think>\nstep one\nstep two\n</think>\n\nfinal answer"
    assert strip_think(raw) == "final answer"


def test_strip_think_orphan_closing_tag() -> None:
    assert strip_think('We must output that JSON.</think>{"ok": true}') == '{"ok": true}'
    assert strip_think('{"ok": true}') == '{"ok": true}'
