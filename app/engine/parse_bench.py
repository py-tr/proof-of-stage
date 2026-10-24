"""Nemotron Parse 2.0 vs Parse v1 in the shipped scan pipeline, on 7 cases.

Pre-registered in docs/preregistration/parse-bench.md (cases, frozen layer values, the 2.0
prompt and converter, the box rubric and code hashes frozen in parse-bench.json before the first
call). Both models read every page fresh, from the same image the pipeline already sends (the
page centred on the 1024x1280 canvas, greyscale JPEG quality 60): v1 through its markdown_bbox
tool as shipped, 2.0 with NVIDIA's documented prompt. Then the shipped pipeline runs on each
model's own text: Super (4k thinking, through Nightshift) reads the joined pages, the guard
locates the accepted quote in that text, and the box is the Parse block(s) holding it. A pair
(case x field) passes when the accepted value equals the frozen layer value and a blind judge
scores the box "on the line". The judging packet is written after the run with the case/model
map hashed first. Nothing is stored in the layer.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import sha16
from app.engine.rungs import _comparable
from app.providers import nvidia
from app.reader.reader import THINKING_BUDGET, read_report
from app.scans.scans import SCANS_DIR, _jpeg, blocks_for_span, join_pages

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "parse-bench.json"
LOG = ROOT / "logs" / "parse-bench.jsonl"
RUNS_LOG = ROOT / "logs" / "parse-bench-runs.jsonl"
PACKET = SCANS_DIR / "_parse_bench"  # data/scans is not committed (scan images)
PARSE2 = "nvidia/nemotron-parse-2.0"
PARSE2_PROMPT = "</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>"
PARSE2_MAX_TOKENS = 3500
BLOCK = re.compile(r"<x_([\d.]+)><y_([\d.]+)>(.*?)<x_([\d.]+)><y_([\d.]+)><class_([^>]+)>", re.S)
VOID_PAGE_FAILURES = 2
FROZEN_FILES = (
    "app/engine/parse_bench.py",
    "app/scans/scans.py",
    "app/providers/nvidia.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def parse2_blocks(content: str) -> tuple[list[dict[str, Any]], bool]:
    """2.0's tagged markdown -> blocks in v1's shape; True when text is left unparsed."""
    blocks = [
        {
            "x0": float(m.group(1)),
            "y0": float(m.group(2)),
            "x1": float(m.group(4)),
            "y1": float(m.group(5)),
            "text": m.group(3).strip(),
            "kind": m.group(6),
        }
        for m in BLOCK.finditer(content)
    ]
    leftover = BLOCK.sub("", content).strip()
    return blocks, bool(leftover)


async def parse2_page(jpeg: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One page through hosted Parse 2.0, documented prompt. Returns (blocks, page facts)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = config.getenv("NVIDIA_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    body = {
        "model": PARSE2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PARSE2_PROMPT},
                    {"type": "image_url", "image_url": {"url": uri}},
                ],
            }
        ],
        "max_tokens": PARSE2_MAX_TOKENS,
        "temperature": 0,
    }
    payload = await nvidia._post(headers, body)
    choice = payload["choices"][0]
    content = choice["message"].get("content") or ""
    blocks, leftover = parse2_blocks(content)
    usage = payload.get("usage") or {}
    finish = choice.get("finish_reason")
    truncated = (
        finish == "length" or leftover or (usage.get("completion_tokens") or 0) >= PARSE2_MAX_TOKENS
    )
    facts = {"model": payload.get("model"), "finish_reason": finish, "usage": usage}
    return blocks, {**facts, "truncated": bool(truncated), "empty": not blocks}


async def v1_page(jpeg: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    blocks, served = await nvidia.parse_page(jpeg)
    return blocks, {"model": served, "truncated": False, "empty": not blocks}


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if record["parse2_prompt_sha256_16"] != sha16(PARSE2_PROMPT):
        changed.append("PARSE2_PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


def value_matches(field: str, accepted: Any, frozen_value: Any) -> bool:
    if accepted is None or frozen_value is None:
        return False
    if field == "NPOS":
        return str(accepted).split(".")[0] == str(frozen_value).split(".")[0]
    return _comparable(field, str(accepted)) == _comparable(field, str(frozen_value))


async def read_model(case_id: str, model: str, run: str) -> dict[str, Any]:
    """Parse every page with one model, then the shipped reader and box on its text."""
    pages, facts = [], []
    for png in sorted((SCANS_DIR / case_id).glob("page-*.png"), key=lambda p: int(p.stem[5:])):
        jpeg = _jpeg(png)
        started = time.monotonic()
        try:
            blocks, fact = await (v1_page(jpeg) if model == "v1" else parse2_page(jpeg))
        except Exception as exc:  # a provider failure on this page: recorded, never re-run
            blocks, fact = [], {"error": f"{type(exc).__name__}: {str(exc)[:160]}", "empty": True}
        fact["seconds"] = round(time.monotonic() - started, 2)
        pages.append(blocks)
        facts.append(fact)
    text, refs = join_pages(pages)
    result = await read_report(
        case_id,
        text,
        provider="nightshift",
        budget=THINKING_BUDGET,
        run_id=f"pbench-{run}-{model}",
    )
    fields = {}
    for name in ("N", "NPOS"):
        fr = result.fields.get(name)
        box = None
        if fr and fr.status == "accepted" and fr.span is not None:
            hits = blocks_for_span(fr.span, refs)
            if hits:
                page = hits[0].page
                box = {
                    "page": page,
                    "boxes": [
                        {k: pages[h.page][h.block][k] for k in ("x0", "y0", "x1", "y1")}
                        for h in hits
                        if h.page == page
                    ],
                }
        fields[name] = {
            "status": fr.status if fr else None,
            "value": fr.value if fr else None,
            "quote": fr.quote if fr else None,
            "reason": (fr.reason if fr else "")[:80],
            "box": box,
        }
    return {
        "pages": facts,
        "fields": fields,
        "receipt_id": result.receipt_id,
        "signature": result.signature,
        "blocks": pages,
    }


def write_packet(rows: list[dict[str, Any]], record: dict[str, Any], tag: str) -> dict[str, Any]:
    """One overlay per (case, field, model) with an accepted, boxed value; shuffled, map hashed."""
    from PIL import Image, ImageDraw

    out_dir = PACKET / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for row in rows:
        for model in ("v1", "v2"):
            for name, field in (row.get(model) or {}).get("fields", {}).items():
                if field.get("box") and [row["case"], name] in record["pairs"]:
                    items.append((row["case"], name, model, field))
    rng = random.Random(record["packet_seed"])
    rng.shuffle(items)
    mapping, sheet = {}, []
    for i, (case_id, name, model, field) in enumerate(items, 1):
        key = f"item-{i:02d}"
        page = field["box"]["page"]
        img = Image.open(SCANS_DIR / case_id / f"page-{page}.png").convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        for b in field["box"]["boxes"]:
            draw.rectangle(
                [b["x0"] * w, b["y0"] * h, b["x1"] * w, b["y1"] * h], outline="red", width=3
            )
        img.save(out_dir / f"{key}.png")
        mapping[key] = {"case": case_id, "field": name, "model": model}
        sheet.append({"item": key, "quote": field.get("quote"), "score": ""})
    map_text = json.dumps(mapping, sort_keys=True)
    (out_dir / "map.json").write_text(map_text, encoding="utf-8")
    (out_dir / "sheet.json").write_text(json.dumps(sheet, indent=1), encoding="utf-8")
    return {
        "packet": str(out_dir.relative_to(ROOT)),
        "items": len(items),
        "map_sha256": hashlib.sha256(map_text.encode()).hexdigest(),
    }


async def run_parse_bench() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in record["cases"]:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        for model in ("v1", "v2"):
            try:
                row[model] = await read_model(case_id, model, tag)
            except Exception as exc:  # the read failed: recorded, never re-run
                row[model] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            fields = (row[model] or {}).get("fields") or {}
            row[model + "_value_ok"] = {
                name: value_matches(name, (fields.get(name) or {}).get("value"), want)
                for name, want in record["frozen_values"][case_id].items()
            }
        rows.append(row)
        slim = {k: v for k, v in row.items()}
        for model in ("v1", "v2"):
            if isinstance(slim.get(model), dict):
                slim[model] = {k: v for k, v in slim[model].items() if k != "blocks"}
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(slim, ensure_ascii=False, default=str) + "\n")
    packet = write_packet(rows, record, tag)
    summary = {"run": tag, **packet}
    for model in ("v1", "v2"):
        pages = [p for r in rows for p in (r.get(model) or {}).get("pages", [])]
        summary[model] = {
            "pages": len(pages),
            "page_failures": sum("error" in p for p in pages),
            "empty_pages": sum(bool(p.get("empty")) for p in pages),
            "truncated_pages": sum(bool(p.get("truncated")) for p in pages),
            "value_ok_pairs": sum(v for r in rows for v in r[model + "_value_ok"].values()),
        }
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
