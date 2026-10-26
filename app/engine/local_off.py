"""The local read on the hard cases, thinking off: what it accepts, and whether that is right.

Pre-registered in docs/preregistration/local-off.md (code hashes, cases and prediction frozen in
local-off.json before the first call). After the Nightshift 2026-10-26 release the local Lightning
lane reads whole reports with thinking off (docs/evidence/local-whole-results.md); with thinking on
a local attempt does not finish (docs/evidence/local-deep-results.md). A demonstration on the
first 5 of the 25 review-queue cases (logs/local-thinkoff-demo-2026-10-26.jsonl, not part of this
test) accepted 6 values, all matching both labellers. This test reads the OTHER 20 queue cases with
local Lightning, thinking off, the shipped prompt and guard on the whole report, and scores the
accepted values with the deep-read bench's rules against both blind labellers. Nothing is stored.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine import labels as labels_mod
from app.engine import second_labeller
from app.engine.dial import sha16
from app.engine.local_deep import score
from app.engine.local_r1 import checklist, run_job
from app.engine.local_whole import LOCAL_MODEL
from app.engine.reader_bench import frozen_case_ids
from app.engine.run_case import load_evidence
from app.providers.text import strip_think
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    SYSTEM_PROMPT,
    judge_count,
    judge_field,
    parse_answer,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "local-off.json"
LOG = ROOT / "logs" / "local-off.jsonl"
RUNS_LOG = ROOT / "logs" / "local-off-runs.jsonl"
DEMO_SEEN = 5  # the first 5 bench cases were read in the demonstration
FROZEN_FILES = (
    "app/engine/local_off.py",
    "app/engine/local_deep.py",
    "app/engine/local_whole.py",
    "app/engine/local_r1.py",
    "app/engine/reader_bench.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def cases() -> list[str]:
    return frozen_case_ids()[DEMO_SEEN:]


async def read_one(case_id: str, tag: str) -> dict[str, Any]:
    row: dict[str, Any] = {"case": case_id, "run": tag}
    report = (await load_evidence(case_id)).report_text
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report},
    ]
    started = time.monotonic()
    try:
        job, attempt = await run_job(messages, f"localoff-{tag}-{case_id}-{uuid.uuid4().hex[:6]}")
    except Exception as exc:  # a provider failure: logged, never re-run
        row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return row
    resolved = (attempt.get("model") or {}).get("resolved")
    row["seconds"] = round(time.monotonic() - started, 1)
    row["chars"] = len(report)
    row["checks"] = {**checklist(job, attempt), "model_is_local_lightning": resolved == LOCAL_MODEL}
    answer = parse_answer(strip_think(str(attempt.get("text") or "")))
    fields = {name: judge_field(name, answer, report) for name in FIELDS}
    fields[NODES_POSITIVE] = judge_count(answer, report)
    row["fields"] = {
        n: {"status": f.status, "value": f.value, "reason": f.reason[:80], "quote": f.quote}
        for n, f in fields.items()
        if n in ("N", NODES_POSITIVE)
    }
    return row


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "cases": cases(),
        "labels_sha16": {
            "builder": labels_mod.FROZEN_SHA.read_text(encoding="utf-8").strip(),
            "second": second_labeller.FROZEN_SHA.read_text(encoding="utf-8").strip(),
        },
        "claim": "every read local by the frozen job checklist and answered by local Lightning, and wrong accepts at most 3 against the builder's labels and at most 2 against the second labeller (cloud Lightning's 4k bench counts on all 25)",
        "kill": "any read not local or not local Lightning, or 5 or more wrong accepts against either labeller",
        "void": "more than 6 of 20 provider failures",
        "reported_not_claimed": "correct accepts, not accepted, seconds per read",
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
    if record["cases"] != cases():
        raise RuntimeError("the cases changed since the freeze")
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


async def run_local_off() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for case_id in record["cases"]:
        row = await read_one(case_id, tag)
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    ok = [r for r in rows if "error" not in r]
    local = sum(all(r["checks"].values()) for r in ok)
    builder = score(ok, labels_mod.frozen_labels())
    second = score(ok, second_labeller.frozen_second())
    summary = {
        "run": tag,
        "cases": len(rows),
        "failures": len(rows) - len(ok),
        "every_read_local": local == len(rows),
        "reads_local": local,
        "vs_builder": builder,
        "vs_second": second,
        "median_seconds": sorted(r["seconds"] for r in ok)[len(ok) // 2] if ok else None,
    }
    summary["void"] = summary["failures"] > 6
    summary["kill"] = (
        not summary["every_read_local"] or builder["wrong"] >= 5 or second["wrong"] >= 5
    )
    summary["claim_met"] = (
        not summary["void"]
        and summary["every_read_local"]
        and builder["wrong"] <= 3
        and second["wrong"] <= 2
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
