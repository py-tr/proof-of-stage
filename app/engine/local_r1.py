"""Local Nemotron as the first read: Lightning on this PC in R1's place, on the dial test's records.

Pre-registered in docs/preregistration/local-r1.md (cases, checklist and code hashes frozen in
local-r1.json before the first call). On each of the 28 records the dial test scored, one read
by the local Nemotron Lightning lane through Nightshift's Jobs API ("privacy": "local-only"),
with the reader's prompt and guard unchanged and R1's closing rule applied as in the ladder.
The referee is the dial run's logged 4k Super read (no new cloud call on the report text).
Every record's job record and attempt must pass a frozen local-only checklist; one failure
voids the claim. Compared, as an honesty row, with cloud Lightning on the same records.
Nothing is stored.

The job body mirrors app/providers/nightshift.local_job (best_of_n, n=1, auto_synthesize off,
an empty assistant think turn, no max_tokens), but each attempt gets its own item id (a retry
of an empty answer never reuses a Nightshift scope) and the job record is kept for the
checklist. local_job itself is frozen by an earlier pre-registration and is not changed.
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
from app.engine.dial import compare, sha16
from app.engine.lightning import r1_closings
from app.engine.run_case import load_evidence
from app.engine.rungs import OPEN_FIELDS
from app.providers import nightshift
from app.providers.text import strip_think
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    REPORT_CHARS,
    SYSTEM_PROMPT,
    ReadResult,
    judge_count,
    judge_field,
    parse_answer,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "local-r1.json"
DIAL_LOG = ROOT / "logs" / "dial-sample.jsonl"
LOG = ROOT / "logs" / "local-r1.jsonl"
RUNS_LOG = ROOT / "logs" / "local-r1-runs.jsonl"
SETTLED_FLOOR = 15  # the bar that put Lightning into R1 (Super's 15 of 28), set before this test
VOID_FAILURES = 9  # more failures than this voids the run (a third of 28), as for cloud Lightning
EMPTY_RETRIES = 1
JOB_TIMEOUT_S = 180.0
POLL_S = 2.0
DONE = {"completed", "succeeded", "success", "done"}
FAILED = {"errored", "failed", "error", "cancelled", "canceled"}
FROZEN_FILES = (
    "app/engine/local_r1.py",
    "app/engine/lightning.py",
    "app/engine/rungs.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


def checklist(job: dict[str, Any], attempt: dict[str, Any]) -> dict[str, bool]:
    """The frozen local-only checks on one job record and its attempt; a missing field fails."""
    model = attempt.get("model") if isinstance(attempt.get("model"), dict) else {}
    policy = job.get("policy") if isinstance(job.get("policy"), dict) else {}
    resolved = model.get("resolved")
    return {
        "privacy_local_only": job.get("privacy") == "local-only",
        "lanes_resolved_local": job.get("lanes_resolved") == [config.NS_LOCAL_LANE],
        "attempt_lane_local": attempt.get("lane") == config.NS_LOCAL_LANE,
        "model_resolved_local_nemotron": isinstance(resolved, str)
        and resolved.startswith(config.LOCAL_RUNTIME_NEMOTRON_PREFIX),
        "model_honored": model.get("honored") is True,
        "egress_honored": policy.get("egress_honored") is True,
        "not_truncated": attempt.get("finish_reason") not in (None, "length"),
    }


async def run_job(messages: list[dict[str, Any]], item_id: str) -> tuple[dict, dict]:
    """One local-only job: create, poll, read attempt 1. Returns (job record, attempt)."""
    base = (config.getenv("METERLESS_BASE_URL") or "").rstrip("/")
    headers = nightshift._headers(item_id)
    body = {
        "kind": "best_of_n",
        "n": 1,
        "window": "now",
        "privacy": "local-only",
        "auto_synthesize": "off",
        "messages": [*messages, {"role": "assistant", "content": "<think></think>"}],
    }
    async with httpx.AsyncClient(timeout=JOB_TIMEOUT_S) as client:
        created = await client.post(f"{base}/jobs", headers=headers, json=body)
        created.raise_for_status()
        job_id = created.json().get("id") or created.json().get("job_id")
        if not job_id:
            raise RuntimeError("job create response has no id")
        deadline = time.monotonic() + JOB_TIMEOUT_S
        while True:
            job = (await client.get(f"{base}/jobs/{job_id}", headers=headers)).json()
            status = str(job.get("status") or "").lower()
            if status in DONE:
                break
            if status in FAILED:
                raise RuntimeError(f"local job {status}")
            if time.monotonic() >= deadline:
                await client.post(f"{base}/jobs/{job_id}/cancel", headers=headers)
                raise TimeoutError("local job timed out")
            await asyncio.sleep(POLL_S)
        attempt = (await client.get(f"{base}/jobs/{job_id}/attempts/1", headers=headers)).json()
    return job, attempt


async def read_local(case_id: str, report: str, run_id: str) -> tuple[ReadResult, list[dict]]:
    """The reader's prompt and guard on the local lane; each attempt gets a fresh item id."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
    ]
    attempts: list[dict[str, Any]] = []
    text = ""
    for n in range(1 + EMPTY_RETRIES):
        item_id = f"localr1-{case_id}-{run_id}-a{n}"
        job, attempt = await run_job(messages, item_id)
        text = strip_think(str(attempt.get("text") or ""))
        attempts.append(
            {
                "item_id": item_id,
                "job_id": job.get("id"),
                "checks": checklist(job, attempt),
                "model_resolved": (attempt.get("model") or {}).get("resolved"),
                "elapsed_ms": attempt.get("elapsed_ms"),
                "tokens": attempt.get("tokens"),
                "tokens_source": attempt.get("tokens_source"),
                "finish_reason": attempt.get("finish_reason"),
                "receipt_id": attempt.get("receipt_id"),
                "empty": not text.strip(),
            }
        )
        if text.strip():
            break
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=str(attempts[-1]["model_resolved"] or ""),
        receipt_id=str(attempts[-1]["receipt_id"] or ""),
        provider="nightshift-local",
        raw_text=text,
        budget=0,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)
    result.fields[NODES_POSITIVE] = judge_count(answer, report)
    return result, attempts


def summarise(rows: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    scored = [r for r in rows if "error" not in r]
    verdicts = [v for r in scored for v in r["agreement"].values()]
    failures = len(rows) - len(scored)
    checks_ok = all(all(a["checks"].values()) for r in scored for a in r["attempts"])
    settled = sum(r["settled"] for r in scored)
    contradicted = verdicts.count("disagree")
    return {
        "records": len(rows),
        "failures": failures,
        "void": failures > VOID_FAILURES,
        "settled": settled,
        "fields_closed": len(verdicts),
        "vs_referee": {v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")},
        "every_record_local": checks_ok and failures == 0,
        "retries": sum(len(r["attempts"]) - 1 for r in scored),
        "seconds": round(sum(r["seconds"] for r in scored), 1),
        "cloud_lightning_settled_row": record.get("cloud_lightning_settled"),
        "claim_met": failures <= VOID_FAILURES
        and settled >= SETTLED_FLOOR
        and contradicted == 0
        and checks_ok,
    }


async def run_local_r1() -> dict[str, Any]:
    record = frozen()
    dial_rows = [json.loads(line) for line in DIAL_LOG.read_text(encoding="utf-8").splitlines()]
    dial = {r["case"]: r for r in dial_rows}
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run = f"{tag}-{uuid.uuid4().hex[:6]}"
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in record["cases"]:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        try:
            evidence = await load_evidence(case_id)
            started = time.monotonic()
            result, attempts = await read_local(case_id, evidence.report_text, run)
            row["seconds"] = round(time.monotonic() - started, 2)
            row["attempts"] = attempts
            row["fields"] = {
                n: {"status": f.status, "value": f.value, "reason": f.reason[:80]}
                for n, f in result.fields.items()
                if n in OPEN_FIELDS
            }
            closed = r1_closings(result, evidence)
            row["closed"] = closed
            row["settled"] = set(closed) == set(OPEN_FIELDS)
            row["agreement"] = compare(closed, dial[case_id]["control"])
        except Exception as exc:  # a failure: recorded, never re-run
            row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows, record)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
