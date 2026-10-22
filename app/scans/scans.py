"""The original pathology-report scans: fetch from the GDC, render, read with Nemotron Parse.

Each page is centred on a white 1024x1280 canvas before Parse reads it, and every box is
stored relative to that canvas, so a box drawn on the saved page image lines up exactly.
Downloads are data only: written under data/scans/, never executed or imported.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.providers import nvidia
from app.reader.quotes import Span

ROOT = Path(__file__).resolve().parents[2]
SCANS_DIR = ROOT / "data" / "scans"
GDC_FILES = "https://api.gdc.cancer.gov/files"
GDC_DATA = "https://api.gdc.cancer.gov/data"
CANVAS = (1024, 1280)
MAX_PDF_BYTES = 20_000_000
_CASE_ID = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}$")


@dataclass(frozen=True)
class BlockRef:
    page: int  # 0-based
    block: int
    start: int  # offsets into the joined scan text
    end: int


def case_dir(case_id: str) -> Path:
    if not _CASE_ID.fullmatch(case_id):
        raise ValueError("not a TCGA case id")
    return SCANS_DIR / case_id


async def report_file_id(case_id: str, client: httpx.AsyncClient) -> str:
    filters = {
        "op": "and",
        "content": [
            {"op": "=", "content": {"field": "cases.submitter_id", "value": case_id}},
            {"op": "=", "content": {"field": "data_type", "value": "Pathology Report"}},
            {"op": "=", "content": {"field": "access", "value": "open"}},
        ],
    }
    response = await client.get(
        GDC_FILES, params={"filters": json.dumps(filters), "fields": "file_id", "size": "5"}
    )
    response.raise_for_status()
    hits = response.json()["data"]["hits"]
    if not hits:
        raise LookupError(f"{case_id}: no open-access pathology report PDF")
    return str(hits[0]["file_id"])


async def fetch_pdf(case_id: str) -> Path:
    """Download the case's open-access report PDF once (retries: the GDC resets connections)."""
    folder = case_dir(case_id)
    path = folder / "report.pdf"
    if path.exists() and path.read_bytes()[:4] == b"%PDF":
        return path
    folder.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        file_id = await report_file_id(case_id, client)
        for attempt in range(6):
            try:
                response = await client.get(f"{GDC_DATA}/{file_id}")
                body = response.content
                if response.status_code == 200 and body[:4] == b"%PDF":
                    if len(body) > MAX_PDF_BYTES:
                        raise ValueError(f"{case_id}: PDF larger than {MAX_PDF_BYTES} bytes")
                    path.write_bytes(body)
                    (folder / "source.json").write_text(
                        json.dumps({"case_id": case_id, "gdc_file_id": file_id}), encoding="utf-8"
                    )
                    return path
            except httpx.HTTPError:
                pass
            await asyncio.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{case_id}: PDF download failed")


def render_pages(pdf_path: Path) -> list[Path]:
    """Every page centred on the 1024x1280 canvas, saved as page-<n>.png next to the PDF."""
    import pypdfium2 as pdfium
    from PIL import Image

    out = []
    doc = pdfium.PdfDocument(str(pdf_path))
    for index in range(len(doc)):
        target = pdf_path.parent / f"page-{index}.png"
        if not target.exists():
            page = doc[index]
            width, height = page.get_size()
            scale = min(CANVAS[0] / width, CANVAS[1] / height)
            image = page.render(scale=scale).to_pil().convert("L")
            canvas = Image.new("L", CANVAS, 255)
            canvas.paste(image, ((CANVAS[0] - image.width) // 2, (CANVAS[1] - image.height) // 2))
            canvas.save(target)
        out.append(target)
    return out


def _jpeg(png: Path) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.open(png).convert("L").save(buffer, format="JPEG", quality=60)
    return buffer.getvalue()


async def parse_scan(case_id: str) -> dict[str, Any]:
    """Nemotron Parse on every page; cached in blocks.json. Returns {model, pages: [[block]]}."""
    folder = case_dir(case_id)
    cache = folder / "blocks.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    pages_png = render_pages(await fetch_pdf(case_id))
    pages, model = [], ""
    for png in pages_png:
        blocks, model = await nvidia.parse_page(_jpeg(png))
        pages.append(blocks)
    result = {"case_id": case_id, "model": model, "canvas": list(CANVAS), "pages": pages}
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result


def join_pages(pages: list[list[dict[str, Any]]]) -> tuple[str, list[BlockRef]]:
    """One text for the reader (page markers between pages) plus where each block sits in it."""
    parts: list[str] = []
    refs: list[BlockRef] = []
    cursor = 0
    for page_no, blocks in enumerate(pages):
        header = f"[page {page_no + 1}]\n"
        parts.append(header)
        cursor += len(header)
        for block_no, block in enumerate(blocks):
            text = str(block.get("text", ""))
            refs.append(BlockRef(page_no, block_no, cursor, cursor + len(text)))
            parts.append(text + "\n")
            cursor += len(text) + 1
    return "".join(parts), refs


def blocks_for_span(span: Span, refs: list[BlockRef]) -> list[BlockRef]:
    """The blocks a located quote touches, in reading order."""
    return [ref for ref in refs if ref.start < span.end and ref.end > span.start]


def write_parse_blocks_csv(path: Path | None = None) -> tuple[Path, int]:
    """Every parsed case's blocks as one CSV for the REG_FILES filestore (the USL parse_block)."""
    import csv

    from app.usl.model import PARSE_BLOCK_COLUMNS, PARSE_BLOCKS_CSV

    target = path or PARSE_BLOCKS_CSV
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PARSE_BLOCK_COLUMNS), lineterminator="\n")
        writer.writeheader()
        for cache in sorted(SCANS_DIR.glob("TCGA-*/blocks.json")):
            parsed = json.loads(cache.read_text(encoding="utf-8"))
            source = cache.parent / "source.json"
            file_id = (
                json.loads(source.read_text(encoding="utf-8"))["gdc_file_id"]
                if source.exists()
                else ""
            )
            for page_no, blocks in enumerate(parsed["pages"]):
                for index, block in enumerate(blocks):
                    writer.writerow(
                        {
                            "case_id": parsed["case_id"],
                            "page_no": page_no,
                            "block_index": index,
                            "block_text": block.get("text", ""),
                            "block_kind": block.get("kind", ""),
                            "xmin": block["x0"],
                            "ymin": block["y0"],
                            "xmax": block["x1"],
                            "ymax": block["y1"],
                            "model": parsed.get("model", ""),
                            "gdc_file_id": file_id,
                        }
                    )
                    rows += 1
    return target, rows
