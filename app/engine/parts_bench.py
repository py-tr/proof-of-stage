"""Pre-registered test of the part-aware count (app/reader/parts.py) on three sets.

docs/preregistration/parts-bench.md (code hashes, the three frozen sets, each record's GDC side
and the prediction frozen in parts-bench.json before the first call). One Super VL call per
record, through Nightshift; nothing is stored; every envelope kept.
- A (designed on, disclosed): the 18 census-2 hit records, scored per field against the review
  (fallen fields fixed = now matches the registry or is left open; standing fields kept = still
  the reading's value). TCGA-AC-A3EH's N is excluded (the report prints N2: neither value).
- B (blind labels): the 25 review-queue records, the count scored against the frozen blind label.
- C (regression): 40 census-2 records the shipped reader agreed with whose reports state two or
  more node fractions; a new count that differs from the registry is a new disagreement.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.critic_census import hit_fields
from app.engine.dial import sha16
from app.providers import envelope_tap
from app.reader.parts import read_parts
from app.reader.reader import _FRACTION, _NEGATIVE_AFTER, _NODE_WORD, _as_number
from app.web.evidence import main_n

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "parts-bench.json"
LABELS = ROOT / "docs" / "preregistration" / "ground-truth-labels.json"
HITS_LOG = ROOT / "logs" / "hidden-2.jsonl"
LOG = ROOT / "logs" / "parts-bench.jsonl"
RUNS_LOG = ROOT / "logs" / "parts-bench-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "parts-bench-envelopes.jsonl"
SEED = 20261026
C_SIZE = 40
FROZEN_FILES = (
    "app/engine/parts_bench.py",
    "app/reader/parts.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)
EXCLUDED_FIELDS = {("TCGA-AC-A3EH", "N")}


def node_fractions(report: str) -> int:
    """Node fractions the report states ("2/18 lymph nodes", "one of two nodes")."""
    n = 0
    for m in _FRACTION.finditer(report):
        top, bottom = _as_number(m.group(1)), _as_number(m.group(2))
        if top is None or bottom is None or top > bottom:
            continue
        window = report[max(0, m.start() - 60) : m.end() + 60]
        if _NODE_WORD.search(window) and not _NEGATIVE_AFTER.search(report[m.end() : m.end() + 50]):
            n += 1
    return n


def sets(reports: dict[str, str]) -> dict[str, Any]:
    fields = [f for f in hit_fields() if (f["case"], f["field"]) not in EXCLUDED_FIELDS]
    a_cases = sorted({f["case"] for f in fields})
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    b = {c: v.get("count") for c, v in sorted(labels.items())}
    rows = [json.loads(x) for x in HITS_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    pool = sorted(
        r["case"]
        for r in rows
        if not r.get("provider_failure")
        and not r.get("contradicts_registry")
        and "NPOS" in (r.get("closed") or {})
        and node_fractions(reports.get(r["case"], "")) >= 2
    )
    c = sorted(random.Random(SEED).sample(pool, min(C_SIZE, len(pool))))
    return {
        "A_fields": fields,
        "A_cases": a_cases,
        "B_labels": b,
        "C_cases": c,
        "C_pool": len(pool),
    }


def gdc_sides(case_ids: list[str]) -> dict[str, str | None]:
    """The registry record's breast from the public GDC API (the diagnosis with a pathologic N)."""
    import httpx

    filt = json.dumps({"op": "in", "content": {"field": "submitter_id", "value": case_ids}})
    r = httpx.get(
        "https://api.gdc.cancer.gov/cases",
        params={
            "filters": filt,
            "fields": "submitter_id,diagnoses.laterality,diagnoses.ajcc_pathologic_n",
            "size": str(len(case_ids) + 5),
            "format": "json",
        },
        timeout=120,
    )
    r.raise_for_status()
    out: dict[str, str | None] = {c: None for c in case_ids}
    for hit in r.json()["data"]["hits"]:
        diags = hit.get("diagnoses") or []
        chosen = next((d for d in diags if d.get("ajcc_pathologic_n")), diags[0] if diags else {})
        side = (chosen.get("laterality") or "").lower()
        out[hit["submitter_id"]] = side if side in ("left", "right") else None
    return out


def registry_values() -> dict[str, dict[str, str]]:
    out = {}
    for x in HITS_LOG.read_text(encoding="utf-8").splitlines():
        r = json.loads(x)
        reg = {f: c["registry"] for f, c in (r.get("contradicts_registry") or {}).items()}
        out[r["case"]] = reg
    return out


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    from app.reports.ingest import read_reports_csv

    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    reports = {c: r.report_text for c, r in read_reports_csv().items()}
    s = sets(reports)
    every = sorted(set(s["A_cases"]) | set(s["B_labels"]) | set(s["C_cases"]))
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "seed": SEED,
        **s,
        "sides": gdc_sides(every),
        "claims": {
            "A": "at least 8 of the 11 fallen fields fixed and at least 10 of the 12 standing fields kept",
            "B": "count correct on at least 15 labelled cases and wrong on at most 1 (the shipped deep read: 16 correct, 0 wrong of 17)",
            "C": "at most 2 new disagreements with the registry among the 40",
        },
        "kill": "A: fewer than 6 fallen fields fixed or more than 3 standing lost; B: more than 2 wrong; C: more than 3 new disagreements",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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


def _value(field: str, res: dict[str, Any]) -> str | None:
    if res.get("count") is None:
        return None
    return str(res["count"]) if field == "NPOS" else main_n(res["n_by_rule"])


def score(record: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fixed = kept = 0
    fallen = standing = 0
    a_rows = []
    for f in record["A_fields"]:
        res = results.get(f["case"]) or {}
        got = _value(f["field"], res)
        reg = f["registry"] if f["field"] == "NPOS" else main_n(f["registry"])
        reading = f["reading"] if f["field"] == "NPOS" else main_n(f["reading"])
        if f["verdict"] == "falls":
            fallen += 1
            ok = got is None or got == reg
            fixed += ok
        elif f["verdict"] == "stands":
            standing += 1
            ok = got == reading
            kept += ok
        else:
            ok = None
        a_rows.append({**f, "new": got, "how": res.get("how"), "ok": ok})
    correct = wrong = open_ = 0
    for case, want in record["B_labels"].items():
        if want in (None, ""):
            continue
        got = (results.get(case) or {}).get("count")
        if got is None:
            open_ += 1
        elif int(got) == int(want):
            correct += 1
        else:
            wrong += 1
    new_dis = 0
    for case in record["C_cases"]:
        res = results.get(case) or {}
        if res.get("count") is None:
            continue
        registry = res.get("registry_count")
        if registry is not None and int(res["count"]) != int(float(registry)):
            new_dis += 1
    out = {
        "A": {"fallen": fallen, "fixed": fixed, "standing": standing, "kept": kept},
        "B": {"correct": correct, "wrong": wrong, "open": open_},
        "C": {"records": len(record["C_cases"]), "new_disagreements": new_dis},
        "A_rows": a_rows,
    }
    out["claims_met"] = {
        "A": fixed >= 8 and kept >= 10,
        "B": correct >= 15 and wrong <= 1,
        "C": new_dis <= 2,
    }
    return out


async def run_parts_bench() -> dict[str, Any]:
    from app.reports.ingest import read_reports_csv
    from app.usl.client import select
    from app.usl.model import table_fqn

    record = frozen()
    reports = {c: r.report_text for c, r in read_reports_csv().items()}
    every = sorted(set(record["A_cases"]) | set(record["B_labels"]) | set(record["C_cases"]))
    ids = ", ".join(f"'{c}'" for c in record["C_cases"])
    counts = {
        str(r[0]): r[1]
        for r in (
            await select(
                f"SELECT case_id, lymph_nodes_positive FROM {table_fqn('stage_check')} "
                f"WHERE case_id IN ({ids})",
                limit=100,
            )
        ).rows
    }
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    results: dict[str, dict[str, Any]] = {}
    for case in every:
        item = f"parts-{tag}-{case}-{uuid.uuid4().hex[:6]}"
        with envelope_tap.capture() as calls:
            try:
                res = await read_parts(case, reports[case], record["sides"].get(case), item)
            except Exception as exc:  # a provider failure: logged, never re-run
                res = {"case": case, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        res["run"] = tag
        res["side"] = record["sides"].get(case)
        if case in counts:
            res["registry_count"] = counts[case]
        results[case] = res
        for c in calls:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"case": case, "run": tag, **c}, sort_keys=True) + "\n")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
    scored = score(record, results)
    summary = {
        "run": tag,
        "records": len(every),
        "failures": sum("error" in r for r in results.values()),
        **{k: v for k, v in scored.items() if k != "A_rows"},
    }
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    with (ROOT / "logs" / "parts-bench-a-rows.json").open("w", encoding="utf-8") as fh:
        json.dump(scored["A_rows"], fh, indent=1, ensure_ascii=False)
    return summary
