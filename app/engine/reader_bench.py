"""Which Nemotron should do the deep read? The guarded reader on the queue, scored against labels.

Pre-registered in docs/preregistration/reader-bench.md (cases, models and code hashes frozen in
reader-bench.json before the first call, and before the blind labels are frozen). Each of the
25 review-queue reports is read once by Lightning and Super VL (4k thinking budget, the deep
rung's setting) and by Ultra (thinking on without a budget: the hosted Ultra rejects a
reasoning budget), all through Nightshift (pinned in the signed receipt, cloud, no cache), with
the reader's prompt and guard unchanged. The three reads of a case run side by side. The
readings are logged unread and scored only against the frozen labels: per model, accepted
values that match the label, accepted values that contradict it, and fields not accepted.
Nothing is stored.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import sha16
from app.engine.run_case import load_evidence
from app.engine.rungs import main_n
from app.providers import nightshift
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    REPORT_CHARS,
    SYSTEM_PROMPT,
    THINKING_BUDGET,
    ReadResult,
    judge_count,
    judge_field,
    normalise_category,
    parse_answer,
    read_report,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "reader-bench.json"
CASES = ROOT / "docs" / "preregistration" / "baseline-cases.json"
LOG = ROOT / "logs" / "reader-bench.jsonl"
RUNS_LOG = ROOT / "logs" / "reader-bench-runs.jsonl"
MODELS = {
    "lightning": config.NS_LIGHTNING_CLOUD,
    "super": config.NS_SUPER_VL,
    "ultra": config.NV_ULTRA,
}
ULTRA_MAX_TOKENS = 8000
VOID_FAILURES = 8  # more provider failures than this voids that model's arm (a third of 25)
FROZEN_FILES = (
    "app/engine/reader_bench.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def frozen_case_ids() -> list[str]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return list(record["cases"])


async def read_ultra(case_id: str, report: str, run_id: str) -> ReadResult:
    """The reader's call with Ultra pinned, thinking on without a budget; same prompt and guard."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
    ]
    text, receipt = await nightshift.chat(
        messages,
        config.NV_ULTRA,
        item_id=f"bench-{case_id}-{run_id}-ultra",
        require_model=config.NV_ULTRA,
        require_kind="cloud",
        retry_on_mismatch=True,
        require_signature=True,
        pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
        allow_cache=False,
        max_tokens=ULTRA_MAX_TOKENS,
        chat_template_kwargs={"enable_thinking": True},
    )
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=receipt.winning_model or "",
        receipt_id=receipt.receipt_id,
        provider="nightshift",
        raw_text=text,
        budget=-1,
        usage=receipt.usage,
        from_cache=receipt.from_cache,
        signature=receipt.signature,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)
    result.fields[NODES_POSITIVE] = judge_count(answer, report)
    return result


async def read_one(name: str, case_id: str, report: str, run_id: str) -> dict[str, Any]:
    row: dict[str, Any] = {"case": case_id, "model_key": name}
    started = time.monotonic()
    try:
        if name == "ultra":
            result = await read_ultra(case_id, report, run_id)
        else:
            result = await read_report(
                case_id,
                report,
                provider="nightshift",
                budget=THINKING_BUDGET,
                run_id=f"{run_id}-{name}",
                model=MODELS[name],
            )
    except Exception as exc:  # a provider failure: recorded, never re-run
        row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return row
    row["seconds"] = round(time.monotonic() - started, 2)
    row["tokens"] = (result.usage or {}).get("completion_tokens") or 0
    row["served"], row["signature"] = result.model, result.signature
    row["receipt_id"] = result.receipt_id
    row["fields"] = {
        n: {"status": f.status, "value": f.value, "reason": f.reason[:80], "quote": f.quote}
        for n, f in result.fields.items()
        if n in ("N", NODES_POSITIVE)
    }
    return row


async def run_bench() -> dict[str, Any]:
    case_ids = frozen_case_ids()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    failures = dict.fromkeys(MODELS, 0)
    for case_id in case_ids:
        report = (await load_evidence(case_id)).report_text
        run_id = f"bench-{tag}-{uuid.uuid4().hex[:4]}"
        rows = await asyncio.gather(*(read_one(n, case_id, report, run_id) for n in MODELS))
        with LOG.open("a", encoding="utf-8") as log:
            for row in rows:
                row["run"] = tag
                failures[row["model_key"]] += "error" in row
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "run": tag,
        "cases": len(case_ids),
        "provider_failures": failures,
        "void": {n: f > VOID_FAILURES for n, f in failures.items()},
    }
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary


def _label_count(label: dict[str, Any]) -> int | None:
    text = str(label.get("count") or "").strip()
    return int(text) if text.isdigit() else None


def _label_n(label: dict[str, Any]) -> str | None:
    value = normalise_category("N", str(label.get("n") or ""))
    return main_n(value) if value else None


def score(rows: list[dict[str, Any]], labels: dict[str, Any]) -> dict[str, Any]:
    """Per model and field: correct accepts, wrong accepts, not accepted, against the labels.

    A field is scored on a case when the label states a value for it (a count, or a printed
    N category). N is compared by its main category (N1A and N1 are the same N1).
    """
    out: dict[str, Any] = {}
    for name in MODELS:
        tally = {
            f: {"correct": 0, "wrong": 0, "not_accepted": 0, "scored": 0}
            for f in ("N", NODES_POSITIVE)
        }
        failures, tokens = 0, 0
        for row in (r for r in rows if r["model_key"] == name):
            label = labels.get(row["case"]) or {}
            truth = {"N": _label_n(label), NODES_POSITIVE: _label_count(label)}
            if "error" in row:
                failures += 1
            tokens += row.get("tokens", 0)
            for field, want in truth.items():
                if want is None:
                    continue
                tally[field]["scored"] += 1
                got = (row.get("fields") or {}).get(field) or {}
                if got.get("status") != "accepted" or got.get("value") is None:
                    tally[field]["not_accepted"] += 1
                elif field == "N":
                    ok = main_n(str(got["value"])) == want
                    tally[field]["correct" if ok else "wrong"] += 1
                else:
                    ok = int(float(got["value"])) == want
                    tally[field]["correct" if ok else "wrong"] += 1
        out[name] = {
            "fields": tally,
            "correct": sum(t["correct"] for t in tally.values()),
            "wrong": sum(t["wrong"] for t in tally.values()),
            "provider_failures": failures,
            "completion_tokens": tokens,
        }
    sup = out["super"]
    eligible = [
        n
        for n in MODELS
        if out[n]["wrong"] <= sup["wrong"] and out[n]["provider_failures"] <= VOID_FAILURES
    ]
    best = max(eligible, key=lambda n: (out[n]["correct"], -out[n]["completion_tokens"]))
    out["deep_read_seat"] = best if out[best]["correct"] > sup["correct"] else "super"
    return out
