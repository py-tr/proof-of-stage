"""The deep read on this PC: local Lightning at a 4k thinking budget, scored like the cloud bench.

Pre-registered in docs/preregistration/local-deep.md (code hashes and prediction frozen in
local-deep.json before the first call). The deep-read bench (reader_bench.py, result in
docs/evidence/reader-bench-results.md, which stands) read the 25 review-queue reports with cloud
Lightning, Super VL and Ultra at a 4k thinking budget through Nightshift and scored the accepted
values against the blind labels. After the Nightshift 2026-10-26 release, the local Lightning lane
holds ~13,000-token prompts and honours a thinking budget (probes in
logs/probe-nightshift-update-2026-10-26.txt). This test reads the same 25 reports with LOCAL
Lightning (Jobs API, "privacy": "local-only"), the same system prompt, report text, 4k budget and
guard, and scores them with the bench's rules against both blind labellers. It measures what
moving the deep read onto a 16 GB PC costs; Parse and Ultra are not part of it. A ~13,000-token
gate probe runs first; if the local lane refuses it, the run is void. Nothing is stored.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app import config
from app.engine import labels as labels_mod
from app.engine import second_labeller
from app.engine.dial import sha16
from app.engine.local_r1 import checklist
from app.engine.local_whole import LOCAL_MODEL, gate
from app.engine.reader_bench import _label_count, _label_n, frozen_case_ids
from app.engine.run_case import load_evidence
from app.providers import nightshift
from app.providers.text import strip_think
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    REPORT_CHARS,
    SYSTEM_PROMPT,
    THINKING_BUDGET,
    judge_count,
    judge_field,
    parse_answer,
)
from app.web.evidence import main_n

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "local-deep.json"
LOG = ROOT / "logs" / "local-deep.jsonl"
RUNS_LOG = ROOT / "logs" / "local-deep-runs.jsonl"
JOB_TIMEOUT_S = 600
FROZEN_FILES = (
    "app/engine/local_deep.py",
    "app/engine/local_whole.py",
    "app/engine/local_r1.py",
    "app/engine/reader_bench.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)
# the cloud arms, as published (docs/evidence/reader-bench-results.md, second-labeller-results.md)
CLOUD_ROWS = {
    "builder": {"cloud_lightning": (24, 3), "super": (32, 3), "ultra": (32, 4)},
    "second": {"cloud_lightning": (25, 2), "super": (33, 2), "ultra": (33, 3)},
}


async def local_think_job(messages: list[dict[str, Any]], item_id: str) -> tuple[dict, dict]:
    """One local-only job with thinking on at the bench's budget: (job record, attempt 1)."""
    base = (config.getenv("METERLESS_BASE_URL") or "").rstrip("/")
    headers = nightshift._headers(item_id)
    body = {
        "kind": "best_of_n",
        "n": 1,
        "window": "now",
        "privacy": "local-only",
        "auto_synthesize": "off",
        "messages": messages,
        "chat_template_kwargs": {"enable_thinking": True, "reasoning_budget": THINKING_BUDGET},
        "max_tokens": THINKING_BUDGET + 3000,
    }
    async with httpx.AsyncClient(timeout=JOB_TIMEOUT_S) as client:
        created = await client.post(f"{base}/jobs", headers=headers, json=body)
        created.raise_for_status()
        job_id = created.json().get("id") or created.json().get("job_id")
        deadline = time.monotonic() + JOB_TIMEOUT_S
        while True:
            job = (await client.get(f"{base}/jobs/{job_id}", headers=headers)).json()
            status = str(job.get("status") or "").lower()
            if status in ("completed", "done", "succeeded"):
                break
            if status in ("failed", "errored", "error", "cancelled", "canceled"):
                raise RuntimeError(f"local job {status}")
            if time.monotonic() >= deadline:
                await client.post(f"{base}/jobs/{job_id}/cancel", headers=headers)
                raise TimeoutError("local job timed out")
            await asyncio.sleep(1.0)
        attempt = (await client.get(f"{base}/jobs/{job_id}/attempts/1", headers=headers)).json()
    return job, attempt


async def read_one(case_id: str, report: str, tag: str) -> dict[str, Any]:
    row: dict[str, Any] = {"case": case_id, "run": tag}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
    ]
    started = time.monotonic()
    try:
        job, attempt = await local_think_job(
            messages, f"localdeep-{tag}-{case_id}-{uuid.uuid4().hex[:6]}"
        )
    except Exception as exc:  # a provider failure: logged, never re-run
        row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return row
    resolved = (attempt.get("model") or {}).get("resolved")
    row["seconds"] = round(time.monotonic() - started, 1)
    row["checks"] = {**checklist(job, attempt), "model_is_local_lightning": resolved == LOCAL_MODEL}
    row["model_resolved"] = resolved
    row["finish_reason"] = attempt.get("finish_reason")
    answer = parse_answer(strip_think(str(attempt.get("text") or "")))
    fields = {name: judge_field(name, answer, report) for name in FIELDS}
    fields[NODES_POSITIVE] = judge_count(answer, report)
    row["fields"] = {
        n: {"status": f.status, "value": f.value, "reason": f.reason[:80], "quote": f.quote}
        for n, f in fields.items()
        if n in ("N", NODES_POSITIVE)
    }
    return row


def score(rows: list[dict[str, Any]], labels: dict[str, Any]) -> dict[str, Any]:
    """The bench's rules (reader_bench.score) for one arm: correct / wrong / not accepted."""
    tally = {
        f: {"correct": 0, "wrong": 0, "not_accepted": 0, "scored": 0} for f in ("N", NODES_POSITIVE)
    }
    for row in rows:
        label = labels.get(row["case"]) or {}
        truth = {"N": _label_n(label), NODES_POSITIVE: _label_count(label)}
        for field, want in truth.items():
            if want is None:
                continue
            tally[field]["scored"] += 1
            got = (row.get("fields") or {}).get(field) or {}
            if got.get("status") != "accepted" or got.get("value") is None:
                tally[field]["not_accepted"] += 1
            elif field == "N":
                tally[field]["correct" if main_n(str(got["value"])) == want else "wrong"] += 1
            else:
                tally[field]["correct" if int(float(got["value"])) == want else "wrong"] += 1
    return {
        "fields": tally,
        "correct": sum(t["correct"] for t in tally.values()),
        "wrong": sum(t["wrong"] for t in tally.values()),
    }


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "cases": frozen_case_ids(),
        "labels_sha16": {
            "builder": labels_mod.FROZEN_SHA.read_text(encoding="utf-8").strip(),
            "second": second_labeller.FROZEN_SHA.read_text(encoding="utf-8").strip(),
        },
        "cloud_rows": CLOUD_ROWS,
        "gate": "one ~13,000-token local job first; void if refused or not answered by local Lightning",
        "claim": "every read local by the frozen job checklist and answered by local Lightning, and against BOTH labellers local Lightning's wrong accepts are no more than cloud Lightning's (3 builder, 2 second)",
        "kill": "any read not local or not local Lightning, or 5 or more wrong accepts against either labeller",
        "void": "the gate fails, or more than 8 of 25 provider failures",
        "reported_not_claimed": "correct accepts, not accepted, seconds per read",
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
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    if record["cases"] != frozen_case_ids():
        raise RuntimeError("the bench cases changed since the freeze")
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


async def run_local_deep() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    g = await gate()
    if not g["passed"]:
        summary = {"run": tag, "gate": g, "void": True, "claim_met": False}
        with RUNS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary) + "\n")
        return summary
    rows = []
    for case_id in record["cases"]:
        report = (await load_evidence(case_id)).report_text
        row = await read_one(case_id, report, tag)
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    ok = [r for r in rows if "error" not in r]
    local = sum(all(r["checks"].values()) for r in ok)
    builder = score(ok, labels_mod.frozen_labels())
    second = score(ok, second_labeller.frozen_second())
    summary = {
        "run": tag,
        "gate": g,
        "cases": len(rows),
        "failures": len(rows) - len(ok),
        "every_read_local": local == len(rows),
        "reads_local": local,
        "vs_builder": builder,
        "vs_second": second,
        "cloud_rows": CLOUD_ROWS,
        "median_seconds": sorted(r["seconds"] for r in ok)[len(ok) // 2] if ok else None,
    }
    summary["void"] = summary["failures"] > 8
    summary["kill"] = (
        not summary["every_read_local"] or builder["wrong"] >= 5 or second["wrong"] >= 5
    )
    summary["claim_met"] = (
        not summary["void"]
        and summary["every_read_local"]
        and builder["wrong"] <= CLOUD_ROWS["builder"]["cloud_lightning"][1]
        and second["wrong"] <= CLOUD_ROWS["second"]["cloud_lightning"][1]
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
