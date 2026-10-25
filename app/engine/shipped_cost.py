"""The shipped evidence chain's cost and safety, measured (no longer an estimate).

Pre-registered in docs/preregistration/shipped-cost.md (code hashes and the prediction frozen in
shipped-cost.json before the first call). The dial test (docs/evidence/dial-sample-results.md)
measured the chain with Super VL at the first read; Lightning took that seat afterwards, so the
shipped chain's token saving was only estimated (docs/evidence/seat-cost-quality.md). This runs
the dial test's own procedure unchanged (app/engine/dial.py `run_one`, `summarise`, imported) on
the dial test's 30 frozen records with today's rungs: the evidence chain as shipped (first read
Lightning thinking off, deep read Super VL 4k on what stays open) against one always-4k Super VL
read of the same report, interleaved per record, the same session, through Nightshift. Nothing
is stored. Every envelope is kept.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine import dial
from app.engine.dial import sha16
from app.providers import envelope_tap

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "shipped-cost.json"
CASES = ROOT / "docs" / "preregistration" / "dial-cases.json"
LOG = ROOT / "logs" / "shipped-cost.jsonl"
RUNS_LOG = ROOT / "logs" / "shipped-cost-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "shipped-cost-envelopes.jsonl"
FROZEN_FILES = (
    "app/engine/shipped_cost.py",
    "app/engine/dial.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


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
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "cases_from": "docs/preregistration/dial-cases.json (the dial test's 30 frozen records)",
        "claim": "shipped chain completion tokens <= 60% of always-4k, and its first-read closings contradicted by the 4k read in at most 10%",
        "void": f"more than {dial.VOID_FAILURES} provider failures",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


async def run_shipped_cost() -> dict[str, Any]:
    frozen()
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for case_id in cases:
        with envelope_tap.capture() as calls:
            try:
                row = await dial.run_one(case_id, f"shipped-{tag}")
            except Exception as exc:  # a provider failure: logged, never re-run
                row = {
                    "case": case_id,
                    "run": tag,
                    "provider_failure": True,
                    "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                }
        for c in calls:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"case": case_id, "run": tag, **c}, sort_keys=True) + "\n")
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **dial.summarise(rows)}
    scored = summary["control_tokens"] or 1
    summary["tokens_vs_always_4k"] = round(summary["ladder_tokens"] / scored - 1, 3)
    closed = summary["fields_closed_at_r1"] or 1
    summary["claim_met"] = (
        not summary["void"]
        and summary["ladder_tokens"] <= 0.6 * summary["control_tokens"]
        and summary["r1_vs_control"]["disagree"] / closed <= 0.10
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
