"""Super VL reads the scan itself: the original pages as images, against Parse + Super on text.

Pre-registered in docs/preregistration/vision-scan.md (cases, prompt and code hashes frozen in
vision-scan.json before the first model call). Today the scan rung reads Nemotron Parse's text
of the original PDF; Super VL, a vision model, never sees a page. For each of 6 queue cases
never scanned before: path A (today's R3) = Parse reads every page (NVIDIA direct), Super VL
reads Parse's text through Nightshift with a 4k budget; path B = Super VL reads the page images
directly (NVIDIA direct: Nightshift returns 502 on images) with a 4k budget. Both paths use the
reader's prompt and the same guard, run on Parse's text of the same pages (a quote must be
found there and show its value). Nothing is stored.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import sha16
from app.providers import nvidia
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    SYSTEM_PROMPT,
    THINKING_BUDGET,
    ReadResult,
    judge_count,
    judge_field,
    parse_answer,
    read_report,
    thinking_args,
)
from app.scans.scans import _jpeg, join_pages, parse_scan, render_pages
from app.scans.scans import fetch_pdf as _fetch_pdf

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "vision-scan.json"
LOG = ROOT / "logs" / "vision-scan.jsonl"
RUNS_LOG = ROOT / "logs" / "vision-scan-runs.jsonl"
FROZEN_FILES = (
    "app/engine/vision.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
    "app/scans/scans.py",
)
IMAGE_PROMPT = "Pathology report, the scanned pages in order:"
PASS_CASES = 4  # path B must match path A on at least 4 of 6 cases, with 0 contradictions


def frozen_case_ids() -> list[str]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if record["prompt_sha256_16"] != sha16(SYSTEM_PROMPT + IMAGE_PROMPT):
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return list(record["cases"])


async def read_images(case_id: str, pages: list[Path], parse_text: str) -> ReadResult:
    """Super VL on the page images (NVIDIA direct); the guard runs on Parse's text."""
    content: list[dict[str, Any]] = [{"type": "text", "text": IMAGE_PROMPT}]
    for png in pages:
        data = base64.b64encode(_jpeg(png)).decode()
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}
        )
    extra, max_tokens = thinking_args(THINKING_BUDGET)
    text, served, usage = await nvidia.chat_with_usage(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
        config.NV_SUPER,
        max_tokens=max_tokens,
        **extra,
    )
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=served,
        receipt_id=None,
        provider="nvidia",
        raw_text=text,
        budget=THINKING_BUDGET,
        usage=usage,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, parse_text)
    result.fields[NODES_POSITIVE] = judge_count(answer, parse_text)
    return result


def _fields(result: ReadResult) -> dict[str, dict[str, Any]]:
    return {
        n: {"status": f.status, "value": f.value, "reason": f.reason[:80], "quote": f.quote}
        for n, f in result.fields.items()
        if n in ("N", NODES_POSITIVE)
    }


def compare_paths(a: dict[str, dict], b: dict[str, dict]) -> dict[str, str]:
    """Per field: same / contradicts (both accepted, different values) / only_a / only_b / none."""
    out = {}
    for name in ("N", NODES_POSITIVE):
        fa, fb = a.get(name) or {}, b.get(name) or {}
        ok_a, ok_b = fa.get("status") == "accepted", fb.get("status") == "accepted"
        if ok_a and ok_b:
            same = str(fa.get("value")).upper() == str(fb.get("value")).upper()
            out[name] = "same" if same else "contradicts"
        else:
            out[name] = "only_a" if ok_a else "only_b" if ok_b else "none"
    return out


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if "error" not in r]
    verdicts = [v for r in scored for v in r["compare"].values()]
    # a case passes when B accepts the same value as A on every field A accepted, none contradicts
    passing = [
        r
        for r in scored
        if all(v in ("same", "none", "only_b") for v in r["compare"].values())
        and any(v == "same" for v in r["compare"].values())
    ]
    return {
        "cases": len(rows),
        "failures": len(rows) - len(scored),
        "fields": {
            v: verdicts.count(v) for v in ("same", "contradicts", "only_a", "only_b", "none")
        },
        "cases_matching": len(passing),
        "image_read_passes": len(passing) >= PASS_CASES and "contradicts" not in verdicts,
        "seconds": {
            "a": round(sum(r["a_seconds"] for r in scored), 1),
            "b": round(sum(r["b_seconds"] for r in scored), 1),
        },
        "tokens": {
            "a": sum(r["a_tokens"] for r in scored),
            "b": sum(r["b_tokens"] for r in scored),
        },
    }


async def run_vision() -> dict[str, Any]:
    case_ids = frozen_case_ids()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        try:
            parsed = await parse_scan(case_id)
            parse_text, _ = join_pages(parsed["pages"])
            pages = render_pages(await _fetch_pdf(case_id))
            row["pages"] = len(pages)
            started = time.monotonic()
            a = await read_report(
                case_id,
                parse_text,
                provider="nightshift",
                budget=THINKING_BUDGET,
                run_id=f"vision-{tag}-a",
            )
            row["a_seconds"] = round(time.monotonic() - started, 2)
            row["a_tokens"] = (a.usage or {}).get("completion_tokens") or 0
            row["a_signature"] = a.signature
            started = time.monotonic()
            b = await read_images(case_id, pages, parse_text)
            row["b_seconds"] = round(time.monotonic() - started, 2)
            row["b_tokens"] = (b.usage or {}).get("completion_tokens") or 0
            row["b_served"] = b.model
            row["a"], row["b"] = _fields(a), _fields(b)
            row["compare"] = compare_paths(row["a"], row["b"])
        except Exception as exc:  # a failure: recorded, never re-run
            row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary
