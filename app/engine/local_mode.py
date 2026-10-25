"""Local first read as a product mode: the evidence chain with its first read on this PC.

`python -m app.cli run --case <id> --local` runs the shipped evidence chain with one change: the
first read (thinking off) goes to local Nemotron Lightning through Nightshift's Jobs API with
"privacy": "local-only" and the on-PC focus step (`local_focus.read_focused`, imported unchanged:
code cuts a long report to its node and staging sentences to fit the local 4,096-token window;
the quote check still uses the full report). What stays open goes to the cloud deep read as
shipped. Nothing is stored. The pre-registered test (docs/preregistration/local-mode.md) runs it on
20 census-2 records never read locally and compares every local closing with the census's cloud
closing for the same field.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.engine.local_focus import read_focused
from app.engine.run_case import load_evidence, write_trace
from app.engine.rungs import R1, _comparable, climb
from app.reader.reader import ReadResult, read_report

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "local-mode.json"
HITS_LOG = ROOT / "logs" / "hidden-2.jsonl"
LOG = ROOT / "logs" / "local-mode.jsonl"
RUNS_LOG = ROOT / "logs" / "local-mode-runs.jsonl"
SEED = 20261025
SAMPLE = 20
FROZEN_FILES = (
    "app/engine/local_mode.py",
    "app/engine/local_focus.py",
    "app/engine/local_r1.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)
LOCAL_INFO: dict[str, dict[str, Any]] = {}  # run_id -> the local job's checklist and focus info


async def local_reader(
    case_id: str,
    report: str,
    *,
    provider: str = "nightshift",
    budget: int = 0,
    run_id: str | None = None,
    model: str | None = None,
) -> ReadResult:
    """The first read (budget 0) on this PC; every other read as shipped."""
    if budget == 0:
        rid = run_id or uuid.uuid4().hex[:8]
        result, info = await read_focused(case_id, report, rid)
        LOCAL_INFO[rid] = info
        return result
    return await read_report(
        case_id, report, provider=provider, budget=budget, run_id=run_id, model=model
    )


async def run_local(case_id: str) -> dict[str, Any]:
    """One case through the chain with the first read local; nothing is stored."""
    evidence = await load_evidence(case_id)
    run_id = f"local-{uuid.uuid4().hex[:8]}"
    ladder = await climb(evidence, run_id=run_id, reader=local_reader)
    write_trace(ladder, run_id, None)
    info = LOCAL_INFO.get(f"{run_id}-{R1}", {})
    attempts = info.get("attempts", [])
    return {
        "case": case_id,
        "run_id": run_id,
        "status": ladder.run.status,
        "rungs": [c.get("rung") for c in ladder.chunks if c.get("rung")],
        "closed": {
            n: {"rung": v["rung"], "value": str(v["value"])} for n, v in ladder.closed.items()
        },
        "open": ladder.open_fields,
        "first_read_local": bool(attempts) and all(all(a["checks"].values()) for a in attempts),
        "local_attempts": attempts,
        "focused": info.get("focused"),
    }


def draw() -> list[str]:
    rows = [json.loads(x) for x in HITS_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    scored = sorted(r["case"] for r in rows if not r.get("provider_failure"))
    return sorted(random.Random(SEED).sample(scored, SAMPLE))


def referee() -> dict[str, dict[str, str]]:
    """The census's cloud closings per record (the shipped chain, 2026-10-25)."""
    out = {}
    for x in HITS_LOG.read_text(encoding="utf-8").splitlines():
        r = json.loads(x)
        out[r["case"]] = {n: str(v["value"]) for n, v in (r.get("closed") or {}).items()}
    return out


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


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "seed": SEED,
        "cases": draw(),
        "referee": "the census-2 cloud closings for the same records (logs/hidden-2.jsonl)",
        "claim": "every first read local by the job checklist, and 0 local first-read closings that differ from the census's cloud closing",
        "kill": "any first read not local, or any disagreement",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


async def run_local_mode() -> dict[str, Any]:
    record = frozen()
    ref = referee()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for case_id in record["cases"]:
        try:
            row = await run_local(case_id)
        except Exception as exc:  # a provider failure: logged, never re-run
            row = {"case": case_id, "provider_failure": f"{type(exc).__name__}: {str(exc)[:200]}"}
        row["run"] = tag
        if "provider_failure" not in row:
            local = {n: v["value"] for n, v in row["closed"].items() if v["rung"] == R1}
            row["vs_cloud"] = {
                n: (
                    "agree"
                    if _comparable(n, v) == _comparable(n, ref.get(case_id, {}).get(n))
                    else ("disagree" if ref.get(case_id, {}).get(n) is not None else "unconfirmed")
                )
                for n, v in local.items()
            }
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    scored = [r for r in rows if "provider_failure" not in r]
    verdicts = [v for r in scored for v in r["vs_cloud"].values()]
    summary = {
        "run": tag,
        "records": len(rows),
        "failures": len(rows) - len(scored),
        "first_read_local": sum(r["first_read_local"] for r in scored),
        "settled_by_local_first_read": sum(
            set(n for n, v in r["closed"].items() if v["rung"] == R1) >= {"N", "NPOS"}
            for r in scored
        ),
        "vs_cloud": {v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")},
    }
    summary["claim_met"] = (
        bool(scored)
        and summary["first_read_local"] == len(scored)
        and summary["vs_cloud"]["disagree"] == 0
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
