"""Capability retests from the 2026-10-24 claims audit (open-agent/research/claims-audit-2026-10-24.md).

Each probe is ONE raw POST with no client retries, so a failure keeps its status and body.
Everything the server returned is logged to logs/capability-retest-2026-10-24.jsonl (answer text
truncated; request headers never logged). Not a scored test: it re-checks whether a limit we
recorded is real.

    python scripts/capability_retest.py images|ultra-budget|all
"""

from __future__ import annotations

import base64
import io
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402

LOG = ROOT / "logs" / "capability-retest-2026-10-24.jsonl"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
SCAN = ROOT / "data" / "scans" / "TCGA-A2-A0CV" / "page-0.png"


def _ns_headers(ttfb_ms: int | None) -> dict[str, str]:
    h = {
        "meterless-app": config.METERLESS_APP,
        "meterless-scope": f"item-retest-{uuid.uuid4().hex[:10]}",
        "Content-Type": "application/json",
    }
    token = config.getenv("METERLESS_RUNTIME_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    if ttfb_ms:
        h["meterless-ttfb-ms"] = str(ttfb_ms)
    return h


def _nv_headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    key = config.getenv("NVIDIA_API_KEY")
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _data_uri(img: Image.Image, fmt: str) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt, quality=85) if fmt == "JPEG" else img.save(buf, fmt)
    kind = "jpeg" if fmt == "JPEG" else "png"
    return f"data:image/{kind};base64," + base64.b64encode(buf.getvalue()).decode()


def _tiny_png() -> str:
    img = Image.new("RGB", (320, 80), "white")
    ImageDraw.Draw(img).text((20, 30), "SETUP CHECK 4417", fill="black")
    return _data_uri(img, "PNG")


def _summarise(response: httpx.Response) -> dict:
    out: dict = {"status": response.status_code}
    try:
        body = response.json()
    except ValueError:
        out["body_text"] = response.text[:2000]
        return out
    choices = body.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        out["content"] = content[:1500]
        out["content_chars"] = len(content)
        out["has_open_think"] = "<think>" in content
        out["has_close_think"] = "</think>" in content
        rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
        out["reasoning_chars"] = len(rc)
        out["finish_reason"] = choices[0].get("finish_reason")
    out["model"] = body.get("model")
    out["usage"] = body.get("usage")
    meta = body.get("meterless") or body.get("receipt")
    if meta is not None:
        out["meterless"] = meta
    if not choices:
        out["body"] = body
    return out


def probe(name: str, url: str, headers: dict, payload: dict, note: str) -> dict:
    started = time.monotonic()
    row: dict = {"probe": name, "note": note, "at": datetime.now(UTC).isoformat(), "url": url}
    row["request"] = {k: v for k, v in payload.items() if k != "messages"}
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, headers=headers, json=payload)
        row.update(_summarise(response))
    except httpx.HTTPError as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:500]
    row["seconds"] = round(time.monotonic() - started, 2)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    shown = {k: row.get(k) for k in ("probe", "status", "seconds", "model", "finish_reason",
                                     "content_chars", "reasoning_chars", "has_close_think", "error")}
    print(json.dumps(shown, ensure_ascii=False))
    if row.get("status", 200) >= 400 or "body" in row or "body_text" in row:
        print("   body:", json.dumps(row.get("body") or row.get("body_text"), ensure_ascii=False)[:800])
    else:
        print("   answer:", (row.get("content") or "")[:300].replace("\n", " "))
    return row


def images() -> None:
    ns = config.getenv("METERLESS_BASE_URL").rstrip("/") + "/chat/completions"
    off = {"enable_thinking": False}
    tiny = [{"role": "user", "content": [
        {"type": "text", "text": "What text is written in this image? Answer with the text only."},
        {"type": "image_url", "image_url": {"url": _tiny_png()}}]}]
    probe("img-tiny-ns", ns, _ns_headers(120000),
          {"model": config.NS_SUPER_VL, "messages": tiny, "max_tokens": 4000,
           "chat_template_kwargs": off},
          "tiny PNG, pinned Super VL via Nightshift, thinking off, ttfb header 120 s")
    scan = Image.open(SCAN)
    page = [{"role": "user", "content": [
        {"type": "text", "text": "This is page 1 of a pathology report scan. Quote the line that "
                                 "states the lymph node status, exactly as printed."},
        {"type": "image_url", "image_url": {"url": _data_uri(scan, "JPEG")}}]}]
    probe("img-scan-ns", ns, _ns_headers(120000),
          {"model": config.NS_SUPER_VL, "messages": page, "max_tokens": 4000,
           "chat_template_kwargs": off},
          "TCGA-A2-A0CV page-0 as JPEG, pinned Super VL via Nightshift, thinking off, ttfb 120 s")


def ultra_budget() -> None:
    ns = config.getenv("METERLESS_BASE_URL").rstrip("/") + "/chat/completions"
    q = [{"role": "user", "content": "A report says 3 of 14 lymph nodes are positive. "
                                     "How many nodes were examined? Answer with one number."}]
    kw = {"enable_thinking": True, "reasoning_budget": 1024}
    probe("ultra-budget-direct", NVIDIA_URL, _nv_headers(),
          {"model": config.NV_ULTRA, "messages": q, "max_tokens": 3000, "chat_template_kwargs": kw},
          "Ultra direct, chat_template_kwargs reasoning_budget 1024")
    probe("ultra-budget-ns", ns, _ns_headers(120000),
          {"model": config.NV_ULTRA, "messages": q, "max_tokens": 3000, "chat_template_kwargs": kw},
          "Ultra via Nightshift, same kwargs; raw content kept to check </think> claim")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("images", "all"):
        images()
    if which in ("ultra-budget", "all"):
        ultra_budget()
