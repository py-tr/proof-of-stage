"""The scan witness, two sizes: Nemotron 3 Nano Omni vs Super VL reading the scanned pages.

Pre-registered in docs/preregistration/scan-witness.md (code hashes, cases and prediction in
scan-witness.json, frozen before the first call). Super VL reading page images already passed a
written-down line as a second witness on scans (vision-scan: 4 of 6 cases matched, 0
contradictions). NVIDIA's pattern routes work to the smallest model that does the job; Nano Omni
(3B active) is the small multimodal Nemotron. Both read the cached page images of the 13 review-
queue cases with scans (`data/scans/`), the reader's prompt and a 4k thinking budget, NVIDIA
direct (Nightshift refuses pinned image requests); the quote check runs on Nemotron Parse's text
of the same pages, unchanged (a quote must be found there and show its value). Each value is
scored against the frozen blind labels (the builder, a lay reader): correct, wrong, or not
accepted. Nothing is stored.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.engine.reader_bench import _label_count, _label_n
from app.providers import nvidia
from app.reader.reader import (
    NODES_POSITIVE,
    SYSTEM_PROMPT,
    THINKING_BUDGET,
    judge_count,
    judge_field,
    parse_answer,
    thinking_args,
)
from app.scans.scans import _jpeg, join_pages
from app.web.evidence import main_n

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "scan-witness.json"
LABELS = ROOT / "docs" / "preregistration" / "ground-truth-labels.json"
SCANS = ROOT / "data" / "scans"
LOG = ROOT / "logs" / "scan-witness.jsonl"
RUNS_LOG = ROOT / "logs" / "scan-witness-runs.jsonl"
MODELS = {
    "omni": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "super_vl": "nvidia/nemotron-3.5-super-vl-120b-a12b",
}
IMAGE_PROMPT = "Pathology report, the scanned pages in order:"
FROZEN_FILES = (
    "app/engine/scan_witness.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
    "app/scans/scans.py",
)


def scan_cases() -> list[str]:
    return sorted(
        d.name
        for d in SCANS.iterdir()
        if d.is_dir() and (d / "blocks.json").exists() and list(d.glob("page-*.png"))
    )


async def read_pages(model: str, case_id: str) -> dict[str, Any]:
    folder = SCANS / case_id
    parse_text, _ = join_pages(
        json.loads((folder / "blocks.json").read_text(encoding="utf-8"))["pages"]
    )
    pages = sorted(folder.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[1]))
    content: list[dict[str, Any]] = [{"type": "text", "text": IMAGE_PROMPT}]
    for png in pages:
        data = base64.b64encode(_jpeg(png)).decode()
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}
        )
    extra, max_tokens = thinking_args(THINKING_BUDGET)
    started = time.monotonic()
    text, served, usage = await nvidia.chat_with_usage(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
        model,
        max_tokens=max_tokens,
        **extra,
    )
    answer = parse_answer(text)
    n = judge_field("N", answer, parse_text)
    k = judge_count(answer, parse_text)
    return {
        "served": served,
        "pages": len(pages),
        "seconds": round(time.monotonic() - started, 2),
        "tokens": (usage or {}).get("completion_tokens") or 0,
        "fields": {
            "N": {"status": n.status, "value": n.value, "reason": n.reason[:80], "quote": n.quote},
            NODES_POSITIVE: {
                "status": k.status,
                "value": k.value,
                "reason": k.reason[:80],
                "quote": k.quote,
            },
        },
    }


def score(rows: list[dict[str, Any]], labels: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key in MODELS:
        t = {
            "correct": 0,
            "wrong": 0,
            "not_accepted": 0,
            "failures": 0,
            "tokens": 0,
            "seconds": 0.0,
        }
        for r in rows:
            got = r.get(key) or {}
            if "error" in got:
                t["failures"] += 1
                continue
            t["tokens"] += got.get("tokens", 0)
            t["seconds"] += got.get("seconds", 0)
            label = labels.get(r["case"]) or {}
            for field, want in (("N", _label_n(label)), (NODES_POSITIVE, _label_count(label))):
                if want is None:
                    continue
                f = (got.get("fields") or {}).get(field) or {}
                if f.get("status") != "accepted" or f.get("value") is None:
                    t["not_accepted"] += 1
                elif field == "N":
                    t["correct" if main_n(str(f["value"])) == want else "wrong"] += 1
                else:
                    t["correct" if int(float(f["value"])) == want else "wrong"] += 1
        t["seconds"] = round(t["seconds"], 1)
        out[key] = t
    o, s = out["omni"], out["super_vl"]
    out["void"] = o["failures"] > 4 or s["failures"] > 4
    out["claim_met"] = (
        not out["void"]
        and o["wrong"] <= s["wrong"]
        and o["correct"] >= s["correct"] - 2
        and o["tokens"] < s["tokens"]
    )
    out["kill"] = o["wrong"] > s["wrong"] + 1 or o["correct"] * 2 < s["correct"]
    return out


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "prompt_sha256_16": sha16(SYSTEM_PROMPT + IMAGE_PROMPT),
        "models": MODELS,
        "cases": scan_cases(),
        "claim": "Nano Omni: wrong at most Super VL's wrong, correct at least Super VL's correct minus 2, and fewer completion tokens",
        "kill": "Omni wrong more than Super VL's wrong + 1, or Omni correct below half of Super VL's",
        "void": "more than 4 failures for either model",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        p
        for p, d in record["code_sha256_16"].items()
        if sha16((ROOT / p).read_text(encoding="utf-8")) != d
    ]
    if sha16(SYSTEM_PROMPT + IMAGE_PROMPT) != record["prompt_sha256_16"]:
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


async def run_scan_witness() -> dict[str, Any]:
    record = frozen()
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for case_id in record["cases"]:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        for key, model in MODELS.items():  # interleaved per case
            try:
                row[key] = await read_pages(model, case_id)
            except Exception as exc:  # a provider failure: logged, never re-run
                row[key] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"run": tag, "cases": len(rows), **score(rows, labels)}
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
