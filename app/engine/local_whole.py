"""Local first read on whole reports: the local-mode test again, with no cut.

Pre-registered in docs/preregistration/local-whole.md (code hashes, records and prediction frozen
in local-whole.json before the first call). The published local mode (local_mode.py, result in
docs/evidence/local-mode-results.md, which stands) cut reports longer than 7,000 characters to
their node and staging sentences, because on this PC's 16 GB GPU Nightshift loaded the local
Lightning lane with a 4,096-token window (6 of its 20 records were cut). After the Nightshift
2026-10-26 release and a lane restart, probes show the local lane answering ~13,000-token prompts
(logs/probe-nightshift-update-2026-10-26.txt). This test sends every report WHOLE to the local
first read, on 20 NEW census-2 records (local mode's 20 excluded) and against the same referee (the census's cloud closings),
with the same prompt, guard, job checklist and chain; only the cut is gone. A gate probe of about
13,000 tokens runs first; if the local lane refuses it, the run is void. Nothing is stored.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.engine.local_mode import HITS_LOG, referee
from app.engine.local_mode import draw as local_mode_draw
from app.engine.local_r1 import EMPTY_RETRIES, checklist, run_job
from app.engine.run_case import load_evidence, write_trace
from app.engine.rungs import R1, _comparable, climb
from app.providers.text import strip_think
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    SYSTEM_PROMPT,
    ReadResult,
    judge_count,
    judge_field,
    parse_answer,
    read_report,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "local-whole.json"
LOG = ROOT / "logs" / "local-whole.jsonl"
RUNS_LOG = ROOT / "logs" / "local-whole-runs.jsonl"
LOCAL_MODEL = "local-runtime/nemotron-3.5-lightning-30b-a3b"
GATE_SENTENCE = "The specimen was examined and no further findings are described in this paragraph."
GATE_REPEATS = 800  # about 13,000 tokens
FROZEN_FILES = (
    "app/engine/local_whole.py",
    "app/engine/local_mode.py",
    "app/engine/local_r1.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)
SEED = 20261026
SAMPLE = 20
INFO: dict[str, dict[str, Any]] = {}  # run id -> the local job's checklist per attempt


def draw() -> list[str]:
    """20 census-2 records the local first read has never seen (local mode's 20 excluded)."""
    import random

    seen = set(local_mode_draw())
    rows = [json.loads(x) for x in HITS_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    pool = sorted(
        r["case"] for r in rows if not r.get("provider_failure") and r["case"] not in seen
    )
    return sorted(random.Random(SEED).sample(pool, SAMPLE))


async def read_whole(case_id: str, report: str, run_id: str) -> tuple[ReadResult, dict]:
    """The local first read (thinking off) on the whole report; the guard on the whole report."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report},
    ]
    attempts: list[dict[str, Any]] = []
    text = ""
    for n in range(1 + EMPTY_RETRIES):
        item_id = f"localwhole-{case_id}-{run_id}-a{n}"
        job, attempt = await run_job(messages, item_id)
        text = strip_think(str(attempt.get("text") or ""))
        resolved = (attempt.get("model") or {}).get("resolved")
        attempts.append(
            {
                "item_id": item_id,
                "checks": {
                    **checklist(job, attempt),
                    "model_is_local_lightning": resolved == LOCAL_MODEL,
                },
                "model_resolved": resolved,
                "elapsed_ms": attempt.get("elapsed_ms"),
                "finish_reason": attempt.get("finish_reason"),
                "empty": not text.strip(),
            }
        )
        if text.strip():
            break
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=str(attempts[-1]["model_resolved"] or ""),
        receipt_id=None,
        provider="nightshift-local",
        raw_text=text,
        budget=0,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)
    result.fields[NODES_POSITIVE] = judge_count(answer, report)
    return result, {"attempts": attempts, "chars_in": len(report), "chars_full": len(report)}


async def whole_reader(
    case_id: str,
    report: str,
    *,
    provider: str = "nightshift",
    budget: int = 0,
    run_id: str | None = None,
    model: str | None = None,
) -> ReadResult:
    """The first read (budget 0) on this PC, whole report; every other read as shipped."""
    if budget == 0:
        rid = run_id or uuid.uuid4().hex[:8]
        result, info = await read_whole(case_id, report, rid)
        INFO[rid] = info
        return result
    return await read_report(
        case_id, report, provider=provider, budget=budget, run_id=run_id, model=model
    )


async def run_whole(case_id: str) -> dict[str, Any]:
    evidence = await load_evidence(case_id)
    run_id = f"localwhole-{uuid.uuid4().hex[:8]}"
    ladder = await climb(evidence, run_id=run_id, reader=whole_reader)
    write_trace(ladder, run_id, None)
    info = INFO.get(f"{run_id}-{R1}", {})
    attempts = info.get("attempts", [])
    return {
        "case": case_id,
        "run_id": run_id,
        "status": ladder.run.status,
        "closed": {
            n: {"rung": v["rung"], "value": str(v["value"])} for n, v in ladder.closed.items()
        },
        "open": ladder.open_fields,
        "first_read_local": bool(attempts) and all(all(a["checks"].values()) for a in attempts),
        "whole_report": bool(info) and info.get("chars_in") == info.get("chars_full"),
        "chars": info.get("chars_full"),
        "local_attempts": attempts,
    }


async def gate() -> dict[str, Any]:
    content = (
        " ".join([GATE_SENTENCE] * GATE_REPEATS)
        + "\n\nFINAL LINE: the code word is HERON. Reply with the code word only."
    )
    started = time.monotonic()
    try:
        job, attempt = await run_job(
            [{"role": "user", "content": content}], f"localwhole-gate-{uuid.uuid4().hex[:6]}"
        )
    except Exception as exc:
        return {"passed": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    text = strip_think(str(attempt.get("text") or ""))
    resolved = (attempt.get("model") or {}).get("resolved")
    return {
        "passed": "HERON" in text.upper() and resolved == LOCAL_MODEL,
        "prompt_chars": len(content),
        "model_resolved": resolved,
        "lanes": job.get("lanes_resolved"),
        "seconds": round(time.monotonic() - started, 1),
    }


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "cases": draw(),
        "referee": "the census-2 cloud closings for the same records (logs/hidden-2.jsonl), as in local-mode",
        "gate": "one ~13,000-token local job first; void if it is refused or not answered by local Lightning",
        "claim": "every first read local by the frozen job checklist AND answered by local Lightning, every report sent whole, and 0 local first-read closings that differ from the census's cloud closing",
        "kill": "any first read not local or not local Lightning, or any disagreement",
        "void": "the gate fails, or more than 6 of 20 provider failures",
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
    if record["cases"] != draw():
        raise RuntimeError("the drawn records changed since the freeze")
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


def verdict(field: str, local: str, cloud: str | None) -> str:
    """A local closing against the census's cloud closing; no cloud closing is "unconfirmed"."""
    if cloud is None:
        return "unconfirmed"
    return "agree" if _comparable(field, local) == _comparable(field, cloud) else "disagree"


async def run_local_whole() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    g = await gate()
    if not g["passed"]:
        summary = {"run": tag, "gate": g, "void": True, "claim_met": False}
        with RUNS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary) + "\n")
        return summary
    ref = referee()
    rows = []
    for case_id in record["cases"]:
        try:
            row = await run_whole(case_id)
        except Exception as exc:  # a provider failure: logged, never re-run
            row = {"case": case_id, "provider_failure": f"{type(exc).__name__}: {str(exc)[:200]}"}
        row["run"] = tag
        if "provider_failure" not in row:
            local = {n: v["value"] for n, v in row["closed"].items() if v["rung"] == R1}
            row["vs_cloud"] = {
                n: verdict(n, v, ref.get(case_id, {}).get(n)) for n, v in local.items()
            }
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    scored = [r for r in rows if "provider_failure" not in r]
    verdicts = [v for r in scored for v in r["vs_cloud"].values()]
    summary = {
        "run": tag,
        "gate": g,
        "records": len(rows),
        "failures": len(rows) - len(scored),
        "first_read_local": sum(r["first_read_local"] for r in scored),
        "whole_reports": sum(r["whole_report"] for r in scored),
        "longest_report_chars": max((r["chars"] or 0) for r in scored) if scored else None,
        "settled_by_local_first_read": sum(
            set(n for n, v in r["closed"].items() if v["rung"] == R1) >= {"N", "NPOS"}
            for r in scored
        ),
        "vs_cloud": {v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")},
    }
    summary["void"] = summary["failures"] > 6
    summary["claim_met"] = (
        not summary["void"]
        and bool(scored)
        and summary["first_read_local"] == len(rows)
        and summary["whole_reports"] == len(rows)
        and summary["vs_cloud"]["disagree"] == 0
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
