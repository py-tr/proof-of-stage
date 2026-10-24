"""The reader benchmark's own reads as an independent second reader of the stored values.

Pre-registered as a dated addendum to docs/preregistration/reader-bench.md (and hash-frozen in
ultra-critic.json) before the blind labels were frozen, without opening the reader-benchmark log.
Lightning, Super VL and Ultra each read every queue report blind under the unchanged guard
(logs/reader-bench.jsonl). Where a model ACCEPTED a value for a field that differs from the value
the layer stored (stage_check.report_n / report_nodes_positive), that is an independent
disagreement: the second reader saw neither the stored value nor its quote. Scored against the
labels exactly like the Ultra critic: right when the label disagrees with the stored value, wrong
when it agrees; missed when the label disagrees and the model accepted the stored value or
nothing.
"""

from __future__ import annotations

from typing import Any

from app.engine.rungs import main_n
from app.reader.reader import normalise_category

MODELS = ("lightning", "super", "ultra")


def _key(field: str, value: Any) -> Any:
    if value in (None, ""):
        return None
    if field == "N":
        return main_n(normalise_category("N", str(value)) or str(value))
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _label(labels: dict[str, Any], case: str, field: str) -> Any:
    lab = labels.get(case) or {}
    raw = lab.get("n") if field == "N" else (str(lab.get("count") or "").strip() or None)
    return _key(field, raw)


def score(
    bench_rows: list[dict[str, Any]],
    stored: dict[str, dict[str, Any]],
    labels: dict[str, Any],
) -> dict[str, Any]:
    """Per model: disagreements with the stored values, and how the labels judge them.

    `stored` maps case -> {"N": report_n, "NPOS": report_nodes_positive}; only the first
    completed benchmark run's rows should be passed.
    """
    out: dict[str, Any] = {}
    for model in MODELS:
        tally = {"disagreements": 0, "right": 0, "wrong": 0, "unscored": 0, "missed": 0}
        listed = []
        for row in (r for r in bench_rows if r.get("model_key") == model and "error" not in r):
            for field in ("N", "NPOS"):
                kept = _key(field, (stored.get(row["case"]) or {}).get(field))
                if kept is None:
                    continue
                got = (row.get("fields") or {}).get(field) or {}
                read = _key(field, got.get("value")) if got.get("status") == "accepted" else None
                disagrees = read is not None and read != kept
                truth = _label(labels, row["case"], field)
                if disagrees:
                    tally["disagreements"] += 1
                    listed.append(
                        {
                            "case": row["case"],
                            "field": field,
                            "stored": kept,
                            "read": read,
                            "quote": got.get("quote"),
                        }
                    )
                if truth is None:
                    tally["unscored"] += disagrees
                    continue
                label_disagrees = truth != kept
                if disagrees:
                    tally["right" if label_disagrees else "wrong"] += 1
                elif label_disagrees:
                    tally["missed"] += 1
        out[model] = {**tally, "list": listed}
    return out
