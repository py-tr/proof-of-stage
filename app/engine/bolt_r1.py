"""Nemotron 3.5 Bolt at the first read: one size down from Lightning, measured, not shipped.

Pre-registered in docs/preregistration/bolt-r1.md (code hashes and prediction in bolt-r1.json,
frozen before the first call). NVIDIA's pattern routes execution down to the smallest model that
does the job; Bolt (E4B) is the edge-sized Nemotron. This runs the shipped evidence chain's first
read only (`rungs.climb(..., abort_after=1)`, its closing rule unchanged: the first read may close
only a field that agrees with the registry) with Bolt in Lightning's place, thinking off, NVIDIA
direct (Nightshift has no Bolt lane, so even a pass cannot ship under decision 0004: it would be
an edge candidate, measured). Records: the dial test's 30 frozen records, the same ones the
shipped-cost run read today. Referee: that run's logged always-4k Super VL read per record (no new
referee calls); comparator: that run's Lightning first read. Nothing is stored.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import _tokens, compare, sha16
from app.engine.run_case import load_evidence
from app.engine.rungs import OPEN_FIELDS, R1, climb
from app.reader.reader import ReadResult, read_report

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "bolt-r1.json"
CASES = ROOT / "docs" / "preregistration" / "dial-cases.json"
REFEREE = ROOT / "logs" / "shipped-cost.jsonl"
LOG = ROOT / "logs" / "bolt-r1.jsonl"
RUNS_LOG = ROOT / "logs" / "bolt-r1-runs.jsonl"
BOLT = "nvidia/nemotron-3.5-bolt-e4b"
FROZEN_FILES = (
    "app/engine/bolt_r1.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
    "app/engine/dial.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


async def bolt_reader(
    case_id: str,
    report: str,
    *,
    provider: str = "nvidia",
    budget: int = 0,
    run_id: str | None = None,
    model: str | None = None,
) -> ReadResult:
    """The first read with Bolt (the rung asks for Lightning; Bolt takes its place here)."""
    return await read_report(
        case_id, report, provider="nvidia", budget=budget, run_id=run_id, model=BOLT
    )


def referee() -> dict[str, dict[str, Any]]:
    out = {}
    for x in REFEREE.read_text(encoding="utf-8").splitlines():
        r = json.loads(x)
        out[r["case"]] = r
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
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    ref = referee()
    lightning = {
        "settled": sum(
            bool(r.get("settled_at_r1")) for r in ref.values() if not r.get("provider_failure")
        ),
        "closings": sum(len(r.get("closed_at_r1") or {}) for r in ref.values()),
    }
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "model": BOLT,
        "cases_from": "docs/preregistration/dial-cases.json",
        "referee": "logs/shipped-cost.jsonl control (always-4k Super VL, 2026-10-25)",
        "lightning_same_records": lightning,
        "claim": "Bolt settles at least 14 of 30 records at the first read with 0 closings contradicted by the 4k read",
        "kill": "fewer than 12 settled, or any closing contradicted",
        "void": "more than 5 provider failures",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


async def run_bolt_r1() -> dict[str, Any]:
    frozen()
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    ref = referee()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for case_id in cases:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        try:
            evidence = await load_evidence(case_id)
            ladder = await climb(
                evidence,
                run_id=f"bolt-{tag}-{uuid.uuid4().hex[:6]}",
                reader=bolt_reader,
                abort_after=1,
            )
            closed = {n: str(v["value"]) for n, v in ladder.closed.items() if v["rung"] == R1}
            tokens = sum(_tokens(c.get("usage")) for c in ladder.chunks)
            row.update(
                {
                    "closed_at_r1": closed,
                    "settled_at_r1": set(closed) >= set(OPEN_FIELDS),
                    "tokens": tokens,
                    "agreement": compare(closed, (ref.get(case_id) or {}).get("control") or {}),
                }
            )
        except Exception as exc:  # a provider failure: logged, never re-run
            row["provider_failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    scored = [r for r in rows if "provider_failure" not in r]
    verdicts = [v for r in scored for v in r["agreement"].values()]
    summary = {
        "run": tag,
        "records": len(rows),
        "failures": len(rows) - len(scored),
        "settled_at_r1": sum(r["settled_at_r1"] for r in scored),
        "closings": len(verdicts),
        "vs_4k": {v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")},
        "tokens": sum(r["tokens"] for r in scored),
    }
    summary["void"] = summary["failures"] > 5
    summary["claim_met"] = (
        not summary["void"] and summary["settled_at_r1"] >= 14 and summary["vs_4k"]["disagree"] == 0
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
