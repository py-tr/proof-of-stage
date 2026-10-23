"""Where the evidence sits on the original scan: the Nemotron Parse block that holds a quote.

The scan rung (R3) reads Nemotron Parse's text of the original PDF; the guard locates its
accepted quote in that text, and the block(s) the quote falls in carry Parse's box (fractions
of the 1024x1280 page canvas, the same size as the saved page image). Only local files are
read (data/scans is not committed), so this shows in live mode on a machine that parsed
the scan, never in sample mode.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.reader.quotes import locate
from app.scans.scans import SCANS_DIR, blocks_for_span, join_pages
from app.web.trace import CHUNKS_LOG


def _scan_quotes(case_id: str, log: Path) -> list[tuple[str, str]]:
    """(field, quote) accepted by the latest scan rung of the case, newest run last."""
    found: list[tuple[str, str]] = []
    if not log.exists():
        return found
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("case") != case_id or row.get("rung") != "R3":
            continue
        quotes = [
            (name, field.get("quote") or "")
            for name, field in (row.get("fields") or {}).items()
            if name in ("NPOS", "N") and field.get("status") == "accepted" and field.get("quote")
        ]
        if quotes:
            found = quotes
    return found


def scan_box(
    case_id: str, scans: Path = SCANS_DIR, log: Path = CHUNKS_LOG
) -> dict[str, Any] | None:
    """The page and the Parse boxes holding the scan rung's accepted quote, or None."""
    blocks_file = scans / case_id / "blocks.json"
    if not blocks_file.exists():
        return None
    pages = json.loads(blocks_file.read_text(encoding="utf-8")).get("pages") or []
    text, refs = join_pages(pages)
    for field, quote in _scan_quotes(case_id, log):
        span = locate(quote, text)
        if span is None:
            continue
        hits = blocks_for_span(span, refs)
        if not hits:
            continue
        page = hits[0].page
        boxes = [
            {k: pages[h.page][h.block][k] for k in ("x0", "y0", "x1", "y1", "text")}
            for h in hits
            if h.page == page
        ]
        if not (scans / case_id / f"page-{page}.png").exists():
            return None
        return {"field": field, "quote": quote, "page": page, "boxes": boxes}
    return None


def page_image(case_id: str, page: int, scans: Path = SCANS_DIR) -> Path | None:
    path = scans / case_id / f"page-{page}.png"
    return path if path.exists() else None
