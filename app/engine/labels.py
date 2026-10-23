"""Freeze the blind labels, then score every run that waits for them.

`python -m app.cli labels freeze <labels.json>` copies the file the labelling sheet downloads
into docs/preregistration/ground-truth-labels.json byte for byte and writes its hash beside it
(ground-truth-labels.sha16). It refuses to overwrite a frozen file with different content.
`python -m app.cli labels score` scores the pre-registered runs that were committed unread
before the labels existed: the Nemotron-alone baseline (A0 / B0 / M0, also without the three
cases the labeller may have seen verdicts for, as pre-registered) and the reader benchmark.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine import baseline, reader_bench

ROOT = Path(__file__).resolve().parents[2]
FROZEN = baseline.LABELS
FROZEN_SHA = FROZEN.with_suffix(".sha16")
SCORES = ROOT / "logs" / "label-scores.json"
# Disclosed in docs/preregistration/baseline-m0.md: the builder had discussed these before
# labelling; the baseline is reported with and without them.
DISCLOSED = ("TCGA-A2-A0CV", "TCGA-A1-A0SN", "TCGA-A7-A26E")
FAULTS = ("node_count", "pathologic_n", "review")


def check_labels(record: Any, cases: list[str]) -> list[str]:
    """Problems with a downloaded labels file (empty list when it is usable)."""
    problems = []
    labels = record.get("labels") if isinstance(record, dict) else None
    if not isinstance(labels, dict):
        return ["no 'labels' object"]
    unknown = sorted(set(labels) - set(cases))
    if unknown:
        problems.append(f"cases not in the queue: {', '.join(unknown)}")
    missing = sorted(set(cases) - set(labels))
    if missing:
        problems.append(f"{len(missing)} queue cases have no label: {', '.join(missing)}")
    no_field = sorted(c for c, v in labels.items() if (v or {}).get("field") not in FAULTS)
    if no_field:
        problems.append(f"{len(no_field)} labels choose no field: {', '.join(no_field)}")
    return problems


def freeze(source: Path) -> dict[str, Any]:
    cases = list(json.loads(baseline.PREREG.read_text(encoding="utf-8"))["cases"])
    text = source.read_text(encoding="utf-8")
    record = json.loads(text)
    problems = check_labels(record, cases)
    digest = baseline.sha16(text)
    if FROZEN.exists():
        if baseline.sha16(FROZEN.read_text(encoding="utf-8")) != digest:
            raise RuntimeError("different labels are already frozen; the first freeze stands")
        return {"frozen": str(FROZEN.relative_to(ROOT)), "sha16": digest, "already": True}
    FROZEN.write_text(text, encoding="utf-8", newline="")
    FROZEN_SHA.write_text(digest + "\n", encoding="utf-8")
    return {
        "frozen": str(FROZEN.relative_to(ROOT)),
        "sha16": digest,
        "labelled": len(record["labels"]),
        "problems": problems,
    }


def frozen_labels() -> dict[str, Any]:
    if not FROZEN.exists():
        raise RuntimeError("no frozen labels yet: run `labels freeze <labels.json>` first")
    text = FROZEN.read_text(encoding="utf-8")
    if baseline.sha16(text) != FROZEN_SHA.read_text(encoding="utf-8").strip():
        raise RuntimeError("the labels changed since they were frozen")
    return json.loads(text)["labels"]


async def score_all() -> dict[str, Any]:
    labels = frozen_labels()
    record = baseline.frozen()
    rows = await baseline.queue_rows(list(record["cases"]))
    a0 = {c: r.get("fault_field") for c, r in rows.items()}
    m0 = [json.loads(line) for line in baseline.LOG.read_text(encoding="utf-8").splitlines()]
    if len({r["run"] for r in m0}) != 1:
        raise RuntimeError("expected exactly one M0 run in the log")
    without = {c: v for c, v in labels.items() if c not in DISCLOSED}
    bench_rows = [
        json.loads(line) for line in reader_bench.LOG.read_text(encoding="utf-8").splitlines()
    ]
    reader_bench.frozen_case_ids()
    result = {
        "scored_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "labels_sha16": FROZEN_SHA.read_text(encoding="utf-8").strip(),
        "baseline_all": baseline.score(m0, labels, a0),
        "baseline_without_disclosed": baseline.score(m0, without, a0),
        "reader_bench": reader_bench.score(bench_rows, labels),
    }
    SCORES.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return result
