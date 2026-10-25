"""Hidden errors, second census: 300 more records the cross-field rule calls consistent.

Pre-registered in docs/preregistration/hidden-2.md (population rule, the frozen 300 ids and code
hashes in hidden-2.json, before the first call). The first hidden-errors test (60 records, 1 hit,
TCGA-A2-A25D, confirmed by the builder's lay read) gave an interval of 0.04-9%. This run reads 300
more with the same steps, reusing app/engine/hidden.py's `run_one` unchanged (the evidence steps
through Nightshift, signed receipts; nothing stored), with every envelope kept. A hit is a closed
field whose value differs from the registry; it is called a contradiction only after a lay read
of the report (logged separately, after the run).
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine import hidden
from app.engine.dial import sha16
from app.providers import envelope_tap

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "hidden-2.json"
LOG = ROOT / "logs" / "hidden-2.jsonl"
RUNS_LOG = ROOT / "logs" / "hidden-2-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "hidden-2-envelopes.jsonl"
SEED = 20261025
SAMPLE_SIZE = 300
VOID_FAILURES = 100  # a third, as in the first run
MIN_SCORED_FOR_RATE = 240
FROZEN_FILES = (
    "app/engine/hidden2.py",
    "app/engine/hidden.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)
POOL_SQL = (
    "SELECT case_id FROM lightning.metastore.registry_audit.stage_audit.stage_check "
    "WHERE reason_class = 'consistent' AND edition_code IN ('6', '7') "
    "AND recorded_n_main IS NOT NULL AND recorded_n_main <> 'NX' "
    "AND lymph_nodes_positive IS NOT NULL AND trim(lymph_nodes_positive) <> ''"
)


def already_read() -> set[str]:
    """Every case id any committed run log has read (ladder chunks and test logs)."""
    seen: set[str] = set()
    for path in (ROOT / "logs").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            case = row.get("case") or row.get("case_id")
            if isinstance(case, str) and case.startswith("TCGA-"):
                seen.add(case)
    return seen


async def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    from app.reports.ingest import read_reports_csv
    from app.usl.client import select

    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    consistent = sorted(r[0] for r in (await select(POOL_SQL, limit=5000)).rows)
    reports = read_reports_csv()
    read = already_read()
    pool = [c for c in consistent if c in reports and c not in read]
    cases = sorted(random.Random(SEED).sample(pool, min(SAMPLE_SIZE, len(pool))))
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "population_sql": POOL_SQL,
        "population": {
            "consistent_records": len(consistent),
            "with_report_text": sum(c in reports for c in consistent),
            "already_read_by_a_logged_run": sum(c in read for c in consistent),
            "pool": len(pool),
        },
        "seed": SEED,
        "cases": cases,
        "void": f"more than {VOID_FAILURES} provider failures",
        "rate_rule": f"an interval only if at least {MIN_SCORED_FOR_RATE} records are scored",
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
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = hidden.summarise(rows)
    base["void"] = base["provider_failures"] > VOID_FAILURES
    base["rate_allowed"] = base["scored"] >= MIN_SCORED_FOR_RATE
    return base


async def run_hidden2() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for case_id in record["cases"]:
        with envelope_tap.capture() as calls:
            try:
                row = await hidden.run_one(case_id, f"h2-{tag}")
            except Exception as exc:  # a provider failure: logged, never re-run
                row = {
                    "case": case_id,
                    "run": tag,
                    "provider_failure": True,
                    "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "closed": {},
                    "open": [],
                    "contradicts_registry": {},
                }
        for c in calls:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"case": case_id, "run": tag, **c}, sort_keys=True) + "\n")
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, default=str) + "\n")
    return summary
