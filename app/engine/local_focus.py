"""Local first read with a focus step: long reports fit the local Nemotron's small window.

Pre-registered in docs/preregistration/local-focus.md (cases, rule and code hashes frozen in
local-focus.json before the first call). Designed after the local R1 test, where the 4 longest
reports never reached the model: on this PC's 16 GB GPU Nightshift loads the local Lightning lane
with a 4,096-token window. Here a report longer than FOCUS_OVER characters is cut down on this
PC, by code, to the sentences that mention lymph nodes, nodal stage or metastasis (each with its
neighbours), before the local Nemotron reads it; shorter reports go whole. The guard checks every
quote against the FULL report, so an excerpt can only cost an acceptance, never add a false one.
Records: the 60 of the hidden-errors test (never used by the local R1 test). Referee: the cloud
ladder's closed values from that run (Lightning R1, then Super R2). Nothing is stored.
"""

from __future__ import annotations

import json
import math
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.dial import sha16
from app.engine.lightning import r1_closings
from app.engine.local_r1 import EMPTY_RETRIES, checklist, run_job
from app.engine.run_case import load_evidence
from app.engine.rungs import OPEN_FIELDS, _comparable
from app.providers.text import strip_think
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    SYSTEM_PROMPT,
    ReadResult,
    judge_count,
    judge_field,
    parse_answer,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "local-focus.json"
HIDDEN_LOG = ROOT / "logs" / "hidden-errors.jsonl"
LOG = ROOT / "logs" / "local-focus.jsonl"
RUNS_LOG = ROOT / "logs" / "local-focus-runs.jsonl"
FOCUS_OVER = 7000  # characters; 8,046 fit the 4,096-token window in the local R1 run, 8,116 did not
FOCUS_BUDGET = 7000
CUE = re.compile(
    r"(?i)lymph|node|nodal|axill|sentinel|\by?p?N\s?[0-3X]\b|N[- ]?stage|patholog\w*\s+stag"
    r"|AJCC|TNM|metasta"
)
SETTLED_SHARE = 15 / 28  # the bar that put Lightning into R1, scaled to this set
VOID_SHARE = 1 / 3
FROZEN_FILES = (
    "app/engine/local_focus.py",
    "app/engine/local_r1.py",
    "app/engine/lightning.py",
    "app/engine/rungs.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def focus(text: str, over: int = FOCUS_OVER, budget: int = FOCUS_BUDGET) -> tuple[str, bool]:
    """The whole report if short; else the cue sentences with their neighbours, in order."""
    if len(text) <= over:
        return text, False
    sentences = re.split(r"(?<=[.;])\s+", text)
    keep: set[int] = set()
    for i, sentence in enumerate(sentences):
        if CUE.search(sentence):
            keep.update({i - 1, i, i + 1})
    picked = [sentences[i] for i in sorted(k for k in keep if 0 <= k < len(sentences))]
    return " ".join(picked)[:budget], True


def referee(row: dict[str, Any]) -> dict[str, Any]:
    """The cloud ladder's closed values as a control: field -> accepted value."""
    return {name: {"status": "accepted", "value": v["value"]} for name, v in row["closed"].items()}


def compare(closed: dict[str, str], control: dict[str, Any]) -> dict[str, str]:
    out = {}
    for name, value in closed.items():
        ref = control.get(name)
        if not ref:
            out[name] = "unconfirmed"
        elif _comparable(name, str(ref["value"])) == _comparable(name, str(value)):
            out[name] = "agree"
        else:
            out[name] = "disagree"
    return out


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


async def read_focused(case_id: str, report: str, run_id: str) -> tuple[ReadResult, dict]:
    text_in, focused = focus(report)
    label = "Pathology report (excerpt)" if focused else "Pathology report"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{label}:\n\n" + text_in},
    ]
    attempts: list[dict[str, Any]] = []
    text = ""
    for n in range(1 + EMPTY_RETRIES):
        item_id = f"localfocus-{case_id}-{run_id}-a{n}"
        job, attempt = await run_job(messages, item_id)
        text = strip_think(str(attempt.get("text") or ""))
        attempts.append(
            {
                "item_id": item_id,
                "checks": checklist(job, attempt),
                "model_resolved": (attempt.get("model") or {}).get("resolved"),
                "elapsed_ms": attempt.get("elapsed_ms"),
                "finish_reason": attempt.get("finish_reason"),
                "empty": not text.strip(),
            }
        )
        if text.strip():
            break
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=str(attempts[-1]["model_resolved"] or ""),
        receipt_id=None,
        provider="nightshift-local",
        raw_text=text,
        budget=0,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)  # the FULL report
    result.fields[NODES_POSITIVE] = judge_count(answer, report)
    info = {"focused": focused, "chars_in": len(text_in), "chars_full": len(report)}
    return result, {"attempts": attempts, **info}


def summarise(rows: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    n = len(rows)
    scored = [r for r in rows if "error" not in r]
    verdicts = [v for r in scored for v in r["agreement"].values()]
    failures = n - len(scored)
    checks_ok = all(all(a["checks"].values()) for r in scored for a in r["attempts"])
    settled = sum(r["settled"] for r in scored)
    floor = math.ceil(n * SETTLED_SHARE)
    focused = [r for r in scored if r["focused"]]
    return {
        "records": n,
        "failures": failures,
        "void": failures > n * VOID_SHARE,
        "settled": settled,
        "settled_floor": floor,
        "fields_closed": len(verdicts),
        "vs_referee": {v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")},
        "focused_records": len(focused),
        "focused_settled": sum(r["settled"] for r in focused),
        "every_record_local": checks_ok and failures == 0,
        "seconds": round(sum(r["seconds"] for r in scored), 1),
        "cloud_r1_settled_row": record.get("cloud_r1_settled"),
        "claim_met": failures <= n * VOID_SHARE
        and settled >= floor
        and verdicts.count("disagree") == 0
        and checks_ok
        and failures == 0,
    }


async def run_local_focus() -> dict[str, Any]:
    record = frozen()
    hidden = {r["case"]: r for r in map(json.loads, HIDDEN_LOG.read_text("utf-8").splitlines())}
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run = f"{tag}-{uuid.uuid4().hex[:6]}"
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in record["cases"]:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        try:
            evidence = await load_evidence(case_id)
            started = time.monotonic()
            result, info = await read_focused(case_id, evidence.report_text, run)
            row["seconds"] = round(time.monotonic() - started, 2)
            row.update(info)
            row["fields"] = {
                k: {"status": f.status, "value": f.value, "reason": f.reason[:80]}
                for k, f in result.fields.items()
                if k in OPEN_FIELDS
            }
            closed = r1_closings(result, evidence)
            row["closed"] = closed
            row["settled"] = set(closed) == set(OPEN_FIELDS)
            row["agreement"] = compare(closed, referee(hidden[case_id]))
        except Exception as exc:  # a failure: recorded, never re-run
            row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = {"run": tag, **summarise(rows, record)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, default=str) + "\n")
    return summary
