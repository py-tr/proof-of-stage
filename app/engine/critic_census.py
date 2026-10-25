"""The shipped second reader on the census-2 hits: does Ultra object where the reading fell?

Pre-registered in docs/preregistration/critic-census.md (code hashes, the per-field verdicts and
the prediction frozen in critic-census.json before the first call). The census-2 deep read
closed 25 values that differ from the registry (`logs/hidden-2.jsonl`); the builder's review
(`docs/evidence/hidden-2-lay-reads.json`) says which readings stand and which fall. Ultra, the
shipped second reader, re-reads each value exactly as it re-read the stored values
(`critic_v2.ask` imported unchanged: the same prompt, model, thinking and objection check), with
the reading and its accepted quote as the value under review. It never sees the verdicts.
Nothing is stored. Every envelope is kept.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine import critic_v2
from app.engine.dial import sha16
from app.providers import envelope_tap

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "critic-census.json"
HITS_LOG = ROOT / "logs" / "hidden-2.jsonl"
READS = ROOT / "docs" / "evidence" / "hidden-2-lay-reads.json"
LOG = ROOT / "logs" / "critic-census.jsonl"
RUNS_LOG = ROOT / "logs" / "critic-census-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "critic-census-envelopes.jsonl"
FROZEN_FILES = (
    "app/engine/critic_census.py",
    "app/engine/critic_v2.py",
    "app/engine/critic.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)
# Field-level exception to the record-level read: TCGA-AC-A3EH's count stands, its N falls (the
# report prints pT3 N2, neither the registry's N3 nor the reading's N1A).
FIELD_OVERRIDES = {("TCGA-AC-A3EH", "N"): "falls"}


def hit_fields() -> list[dict[str, Any]]:
    """Every census-2 value that differs from the registry, with the review's verdict."""
    reads = json.loads(READS.read_text(encoding="utf-8"))["reads"]
    out = []
    for line in HITS_LOG.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for field, c in (row.get("contradicts_registry") or {}).items():
            case = row["case"]
            verdict = FIELD_OVERRIDES.get((case, field), reads[case]["read"])
            out.append(
                {
                    "case": case,
                    "field": field,
                    "registry": c["registry"],
                    "reading": c["report"],
                    "quote": c["quote"],
                    "verdict": verdict,
                }
            )
    return sorted(out, key=lambda f: (f["case"], f["field"]))


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for verdict in ("falls", "stands", "unsure"):
        mine = [r for r in rows if r["verdict"] == verdict]
        objected = [r for r in mine if r.get("ultra") == "contradiction"]
        out[verdict] = {
            "fields": len(mine),
            "failures": sum("error" in r for r in mine),
            "objected": len(objected),
            "objected_verified": sum(
                bool((r.get("check") or {}).get("verified")) for r in objected
            ),
            "agreed": sum(r.get("ultra") == "agree" for r in mine),
        }
    f, s = out["falls"], out["stands"]
    out["claim_met"] = f["objected"] * 2 >= f["fields"] and s["objected"] <= 2
    out["kill"] = f["objected"] <= s["objected"]
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
    if record["fields"] != hit_fields():
        raise RuntimeError("the census fields or their verdicts changed since the freeze")
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    fields = hit_fields()
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "fields": fields,
        "counts": {
            v: sum(f["verdict"] == v for f in fields) for v in ("falls", "stands", "unsure")
        },
        "claim": "Ultra says 'contradiction' on at least half of the fallen fields and on at most 2 standing fields",
        "kill": "objections on fallen fields not above objections on standing fields",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


async def run_critic_census() -> dict[str, Any]:
    from app.reports.ingest import read_reports_csv

    record = frozen()
    reports = read_reports_csv()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for f in record["fields"]:
        scope = f"critic-census-{f['case']}-{f['field']}-{tag}-{uuid.uuid4().hex[:6]}"
        with envelope_tap.capture() as calls:
            asked = await critic_v2.ask(
                f["case"],
                f["field"],
                f["reading"],
                f["quote"],
                reports[f["case"]].report_text,
                scope,
            )
        row = {**f, "run": tag, **{k: v for k, v in asked.items() if k not in ("case", "field")}}
        row["ultra"] = asked.get("verdict")
        for c in calls:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"case": f["case"], "run": tag, **c}, sort_keys=True) + "\n")
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **score(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
