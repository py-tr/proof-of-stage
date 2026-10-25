"""Freeze and score the second, independent blind labeller (docs/preregistration/second-labeller.md).

Written 2026-10-25, before any second label exists. `freeze` copies the file the blind sheet
downloads into docs/preregistration/second-labeller-labels.json byte for byte, with its sha16
beside it, and refuses to overwrite a different frozen file. `score` runs offline: the product's
verdict (A0), Super alone (M0, thinking off and 4k) and the rule alone (B0) are the per-case
answers already recorded when the first labels were scored (logs/label-scores.json), so nothing
is re-run and no model is called; the scoring rules are the frozen ones in app/engine/baseline.py
and app/engine/reader_bench.py, unchanged. Reported: agreement between the two labellers (raw
and Cohen's kappa over the three outcomes), each method against the second labeller, and each
method on the cases where both labellers agree.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine import baseline, labels, reader_bench

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "docs" / "preregistration" / "second-labeller-labels.json"
FROZEN_SHA = FROZEN.with_suffix(".sha16")
FIRST_SCORES = ROOT / "logs" / "label-scores.json"
SCORES = ROOT / "logs" / "second-labeller-scores.json"


def freeze(source: Path) -> dict[str, Any]:
    cases = list(json.loads(baseline.PREREG.read_text(encoding="utf-8"))["cases"])
    text = source.read_text(encoding="utf-8")
    problems = labels.check_labels(json.loads(text), cases)
    digest = baseline.sha16(text)
    if FROZEN.exists():
        if baseline.sha16(FROZEN.read_text(encoding="utf-8")) != digest:
            raise RuntimeError("different labels are already frozen; the first freeze stands")
        return {"frozen": str(FROZEN.relative_to(ROOT)), "sha16": digest, "already": True}
    FROZEN.write_text(text, encoding="utf-8", newline="")
    FROZEN_SHA.write_text(digest + "\n", encoding="utf-8")
    return {"frozen": str(FROZEN.relative_to(ROOT)), "sha16": digest, "problems": problems}


def frozen_second() -> dict[str, Any]:
    if not FROZEN.exists():
        raise RuntimeError("no second labels frozen yet: run `freeze <labels.json>` first")
    text = FROZEN.read_text(encoding="utf-8")
    if baseline.sha16(text) != FROZEN_SHA.read_text(encoding="utf-8").strip():
        raise RuntimeError("the second labels changed since they were frozen")
    return json.loads(text)["labels"]


def kappa(a: dict[str, str], b: dict[str, str]) -> dict[str, Any]:
    """Raw agreement and Cohen's kappa over the cases both labellers gave a field."""
    both = sorted(c for c in a if c in b)
    n = len(both)
    if not n:
        return {"cases": 0, "agree": 0, "kappa": None}
    agree = sum(a[c] == b[c] for c in both)
    pa, pb = Counter(a[c] for c in both), Counter(b[c] for c in both)
    expected = sum(pa[k] * pb[k] for k in labels.FAULTS) / (n * n)
    observed = agree / n
    k = None if expected == 1 else round((observed - expected) / (1 - expected), 3)
    return {"cases": n, "agree": agree, "kappa": k}


def _fields(raw: dict[str, Any]) -> dict[str, str]:
    return {c: v["field"] for c, v in raw.items() if (v or {}).get("field") in labels.FAULTS}


def score_with(
    first: dict[str, Any],
    second: dict[str, Any],
    per_case: dict[str, dict[str, Any]],
    bench_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    a0 = {c: v.get("A0") for c, v in per_case.items()}
    m0 = [
        {"case": c, **{arm: {"fault": v.get(f"M0_{arm}")} for arm in baseline.ARMS}}
        for c, v in per_case.items()
    ]
    f1, f2 = _fields(first), _fields(second)
    agreed = {c: second[c] for c in f2 if f1.get(c) == f2[c]}

    def methods(lab: dict[str, Any]) -> dict[str, Any]:
        s = baseline.score(m0, lab, a0)
        return {
            "labelled": s["labelled"],
            "product_A0": s["A0_ours"],
            "rule_alone_B0": s["B0_rule_alone"],
            **{
                f"super_alone_{arm}": {"agree": s[f"M0_{arm}"]["agree"], "of": s[f"M0_{arm}"]["of"]}
                for arm in baseline.ARMS
            },
        }

    return {
        "labellers": kappa(f1, f2),
        "vs_second": methods(second),
        "vs_both_agree": methods(agreed),
        "reader_bench_vs_second": reader_bench.score(bench_rows, second),
        "per_case": {
            c: {"first": f1.get(c), "second": f2.get(c), "A0": a0.get(c)} for c in sorted(per_case)
        },
    }


def score() -> dict[str, Any]:
    second = frozen_second()
    first = labels.frozen_labels()
    stored = json.loads(FIRST_SCORES.read_text(encoding="utf-8"))
    bench_rows = [
        json.loads(x) for x in reader_bench.LOG.read_text(encoding="utf-8").splitlines() if x
    ]
    result = {
        "scored_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "second_labels_sha16": FROZEN_SHA.read_text(encoding="utf-8").strip(),
        "first_labels_sha16": stored["labels_sha16"],
        "answers_from": "logs/label-scores.json per_case (recorded when the first labels were scored)",
        **score_with(first, second, stored["baseline_all"]["per_case"], bench_rows),
    }
    SCORES.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return result
