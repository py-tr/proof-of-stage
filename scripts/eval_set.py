"""The evaluation set people's judgements make, exported, and any reader re-scored on it in one command.

NVIDIA's guidance is that models earn their place when they are adapted to the job; the first step
of that loop is an evaluation set built from the people who check the output. This exports ours:
- `docs/evidence/eval-set/labels.jsonl`: the frozen blind labels on the 25 review-queue records
  (the builder, a lay reader: field, positive count, printed N, the supporting line);
- `docs/evidence/eval-set/census-reviews.jsonl`: the 25 census-2 hit fields with the review's
  verdict (AI-drafted from excerpts, confirmed by the builder);
- `docs/evidence/eval-set/decisions.jsonl`: every decision a person recorded on the case page
  (read from the layer when live; skipped offline).
Report text is not included (licence and size); every row names its case id in the public
TCGA-Reports corpus.

`python scripts/eval_set.py score <log.jsonl> [model_key ...]` re-scores any logged reader run
whose rows carry `case`, `model_key` and `fields` (`logs/reader-bench.jsonl`, for example) against
the labels with the same rules as the pre-registered bench. No model call; no training.

    python scripts/eval_set.py export
    python scripts/eval_set.py score logs/reader-bench.jsonl
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.reader_bench import _label_count, _label_n  # noqa: E402
from app.web.evidence import main_n  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "eval-set"
LABELS = ROOT / "docs" / "preregistration" / "ground-truth-labels.json"


def _write(name: str, rows: list[dict]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


async def _decisions() -> list[dict]:
    try:
        from app.usl.client import select
        from app.usl.model import table_fqn
        from app.web.data import DECISION_RULE

        res = await select(
            "SELECT case_id, field, recorded_value, derived_value, reason, created_at "
            f"FROM {table_fqn('flag')} WHERE rule_id = '{DECISION_RULE}' ORDER BY created_at",
            limit=1000,
        )
        cols = ("case_id", "field", "recorded_value", "derived_value", "reason", "created_at")
        return [dict(zip(cols, r)) if not isinstance(r, dict) else r for r in res.rows]
    except Exception as exc:  # offline or Zetaris down: the export notes it
        return [{"note": f"decisions not exported: {type(exc).__name__}"}]


def export() -> None:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    n1 = _write(
        "labels.jsonl",
        [
            {
                "case": c,
                "field": v.get("field"),
                "positive_count": _label_count(v),
                "n_main": _label_n(v),
                "supporting_line": v.get("quote"),
                "note": v.get("note"),
                "labeller": labels.get("labeller"),
            }
            for c, v in sorted(labels["labels"].items())
        ],
    )
    from app.engine.critic_census import hit_fields

    n2 = _write("census-reviews.jsonl", hit_fields())
    n3 = _write("decisions.jsonl", asyncio.run(_decisions()))
    print(f"labels {n1}, census reviews {n2}, decisions {n3} -> {OUT.relative_to(ROOT)}")


def score(log: Path, keys: list[str]) -> dict:
    labels = {
        json.loads(x)["case"]: json.loads(x)
        for x in (OUT / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    }
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    keys = keys or sorted({r.get("model_key") for r in rows if r.get("model_key")})
    out = {}
    for key in keys:
        t = {"correct": 0, "wrong": 0, "not_accepted": 0}
        for r in (x for x in rows if x.get("model_key") == key):
            label = labels.get(r.get("case")) or {}
            for field, want in (("N", label.get("n_main")), ("NPOS", label.get("positive_count"))):
                if want is None:
                    continue
                got = (r.get("fields") or {}).get(field) or {}
                if got.get("status") != "accepted" or got.get("value") is None:
                    t["not_accepted"] += 1
                elif field == "N":
                    t["correct" if main_n(str(got["value"])) == want else "wrong"] += 1
                else:
                    t["correct" if int(float(got["value"])) == want else "wrong"] += 1
        out[key] = t
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "export":
        export()
    elif cmd == "score" and len(sys.argv) > 2:
        print(json.dumps(score(Path(sys.argv[2]), sys.argv[3:]), indent=1))
    else:
        print(__doc__)
