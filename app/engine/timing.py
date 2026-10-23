"""R1 timing, controlled: Lightning and Super with thinking off, the same records, the same hour.

Pre-registered in docs/preregistration/r1-timing.md (cases, trials and code hashes frozen in
r1-timing.json before the first call). The Lightning R1 result (18 of 28 settled vs 15) compared
two runs made hours apart under different guard versions, so its seconds were not a controlled
comparison. Here both models read each of the dial test's 28 records once per trial, back to
back, through Nightshift (each pinned in its signed receipt, cloud, no cache), thinking off, with
the reader's prompt and the current guard; the order alternates per trial. R1's closing rule is
applied to every read; the dial run's stored 4k Super read is the referee. Nothing is stored.
"""

from __future__ import annotations

import json
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import compare, sha16
from app.engine.lightning import r1_closings
from app.engine.run_case import load_evidence
from app.engine.rungs import OPEN_FIELDS
from app.reader.reader import THINKING_OFF, read_report

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "r1-timing.json"
DIAL_LOG = ROOT / "logs" / "dial-sample.jsonl"
LOG = ROOT / "logs" / "r1-timing.jsonl"
RUNS_LOG = ROOT / "logs" / "r1-timing-runs.jsonl"
MODELS = {"lightning": config.NS_LIGHTNING_CLOUD, "super": config.NS_SUPER_VL}
TRIALS = 3
KILL_DISAGREE = 0.10
VOID_FAILURES = 28  # more failed reads than this (a sixth of 168) voids the run
FROZEN_FILES = (
    "app/engine/timing.py",
    "app/engine/lightning.py",
    "app/engine/rungs.py",
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


def order(trial: int) -> tuple[str, str]:
    """Lightning first on odd trials, Super first on even ones."""
    return ("lightning", "super") if trial % 2 else ("super", "lightning")


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"reads": len(rows)}
    failed = [r for r in rows if "error" in r]
    out["failed_reads"] = len(failed)
    out["void"] = len(failed) > VOID_FAILURES
    for name in MODELS:
        ok = [r for r in rows if r["model_key"] == name and "error" not in r]
        verdicts = [v for r in ok for v in r["agreement"].values()]
        per_trial = {}
        for trial in range(1, TRIALS + 1):
            t = [r for r in ok if r["trial"] == trial]
            per_trial[trial] = {
                "settled": sum(r["settled"] for r in t),
                "seconds": round(sum(r["seconds"] for r in t), 1),
                "tokens": sum(r["tokens"] for r in t),
            }
        settled = [p["settled"] for p in per_trial.values()]
        out[name] = {
            "reads": len(ok),
            "settled_per_trial": settled,
            "seconds_per_trial": [p["seconds"] for p in per_trial.values()],
            "tokens_per_trial": [p["tokens"] for p in per_trial.values()],
            "median_seconds_per_read": round(statistics.median(r["seconds"] for r in ok), 2)
            if ok
            else None,
            "closings_vs_control": {
                v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")
            },
            "unsafe": bool(verdicts) and verdicts.count("disagree") / len(verdicts) > KILL_DISAGREE,
        }
    lt, st = out["lightning"], out["super"]
    out["lightning_faster"] = (
        lt["median_seconds_per_read"] is not None
        and st["median_seconds_per_read"] is not None
        and lt["median_seconds_per_read"] < st["median_seconds_per_read"]
    )
    return out


async def run_timing() -> dict[str, Any]:
    case_ids = frozen_case_ids()
    dial = {
        r["case"]: r
        for r in (json.loads(line) for line in DIAL_LOG.read_text(encoding="utf-8").splitlines())
    }
    evidence = {c: await load_evidence(c) for c in case_ids}
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for trial in range(1, TRIALS + 1):
        for case_id in case_ids:
            for name in order(trial):
                row: dict[str, Any] = {
                    "case": case_id,
                    "trial": trial,
                    "model_key": name,
                    "run": tag,
                }
                started = time.monotonic()
                try:
                    result = await read_report(
                        case_id,
                        evidence[case_id].report_text,
                        provider="nightshift",
                        budget=THINKING_OFF,
                        run_id=f"timing-{tag}-{trial}-{name}-{uuid.uuid4().hex[:4]}",
                        model=MODELS[name],
                    )
                except Exception as exc:  # a failed read: recorded, never re-run
                    row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                    rows.append(row)
                    with LOG.open("a", encoding="utf-8") as log:
                        log.write(json.dumps(row, ensure_ascii=False) + "\n")
                    continue
                row["seconds"] = round(time.monotonic() - started, 2)
                row["tokens"] = (result.usage or {}).get("completion_tokens") or 0
                row["served"], row["signature"] = result.model, result.signature
                closed = r1_closings(result, evidence[case_id])
                row["closed"] = closed
                row["settled"] = set(closed) == set(OPEN_FIELDS)
                row["agreement"] = compare(closed, dial[case_id]["control"])
                rows.append(row)
                with LOG.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary
