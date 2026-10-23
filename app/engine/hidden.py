"""Hidden errors: do records whose two registry fields agree still contradict their report?

Pre-registered in docs/preregistration/hidden-errors.md (cases, seed and code hashes frozen in
hidden-cases.json before the first call). The cross-field rule can only see a record whose N
category and node count cannot both be true; a count that is wrong but stays in the same
category (7 recorded, the report says 6: both N2) is invisible to it. For each of 60 randomly
drawn consistent records not read before, the product's evidence ladder runs unchanged
through Nightshift (R1 Lightning may only clear a field that agrees with the registry; R2 and
R3 Super may close any guarded value). Measured: closed fields whose value contradicts the
registry, with the quote that closed them. Nothing is stored.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.engine.run_case import load_evidence, write_trace
from app.engine.rungs import NODES_POSITIVE, _comparable, climb

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "hidden-cases.json"
LOG = ROOT / "logs" / "hidden-errors.jsonl"
RUNS_LOG = ROOT / "logs" / "hidden-errors-runs.jsonl"
PROVIDER = "nightshift"
VOID_FAILURES = 20  # more provider failures than this voids the run (a third of 60)
FROZEN_FILES = (
    "app/engine/hidden.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
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


def registry_value(name: str, evidence: Any) -> str | None:
    if name == NODES_POSITIVE:
        count = evidence.registry_count
        return None if count is None else f"{count:g}"
    return evidence.recorded_n


def contradictions(closed: dict[str, dict[str, Any]], evidence: Any) -> dict[str, dict]:
    """Closed fields whose value differs from the registry (N by main category, count as int)."""
    out = {}
    for name, field in closed.items():
        recorded = registry_value(name, evidence)
        if recorded is None or field.get("value") is None:
            continue
        if _comparable(name, str(field["value"])) != _comparable(name, recorded):
            out[name] = {"registry": recorded, "report": str(field["value"]), "rung": field["rung"]}
    return out


async def run_one(case_id: str, tag: str) -> dict[str, Any]:
    evidence = await load_evidence(case_id)
    run_id = f"hidden-{tag}-{uuid.uuid4().hex[:6]}"
    ladder = await climb(evidence, run_id=run_id, provider=PROVIDER)
    write_trace(ladder, run_id, None)
    row: dict[str, Any] = {"case": case_id, "run": tag, "status": ladder.run.status}
    row["provider_failure"] = ladder.run.status != "completed"
    row["rungs"] = [c.get("rung") for c in ladder.chunks if c.get("rung")]
    row["closed"] = {
        n: {"rung": v["rung"], "value": str(v["value"])} for n, v in ladder.closed.items()
    }
    row["open"] = ladder.open_fields
    row["conflicts"] = ladder.conflicts
    found = contradictions(ladder.closed, evidence)
    for name, item in found.items():
        fr, _ = ladder.closings[name]
        item["quote"] = (fr.quote or "")[:300]
    row["contradicts_registry"] = found
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if not r["provider_failure"]]
    failures = len(rows) - len(scored)
    hits = [r for r in scored if r["contradicts_registry"]]
    fields = [f for r in hits for f in r["contradicts_registry"]]
    return {
        "records": len(rows),
        "provider_failures": failures,
        "void": failures > VOID_FAILURES,
        "scored": len(scored),
        "records_contradicting_registry": len(hits),
        "fields_contradicting_registry": {
            "N": fields.count("N"),
            NODES_POSITIVE: fields.count(NODES_POSITIVE),
        },
        "records_fully_settled": sum(not r["open"] for r in scored),
        "cases": [r["case"] for r in hits],
    }


async def run_hidden() -> dict[str, Any]:
    case_ids = frozen_case_ids()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        try:
            row = await run_one(case_id, tag)
        except Exception as exc:  # a provider failure: logged, never re-run
            row = {
                "case": case_id,
                "run": tag,
                "provider_failure": True,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "contradicts_registry": {},
                "open": [],
            }
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary
