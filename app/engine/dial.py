"""Where the reasoning dial pays: the ladder on records that agree, against an always-4k read.

Pre-registered in docs/preregistration/dial-sample.md (cases, seed, code hashes frozen in
dial-cases.json before the first call). For each of 30 randomly drawn consistent records
(the registry's N and node count agree; edition 6th/7th; report text available):
- the real evidence ladder through Nightshift (R1 thinking off may close a field that agrees
  with the registry; R2 a 4k budget only for what is still open), and
- a control: one 4k read of the same report through Nightshift, on every record.
Nothing is stored. Measured: records settled at R1, fields closed at R1, whether the 4k
control agrees with every R1 closing, and completion tokens and seconds of the ladder
against the control (always-4k), from Nightshift's own usage.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.run_case import load_evidence, write_trace
from app.engine.rungs import OPEN_FIELDS, R1, _comparable, climb
from app.reader.reader import THINKING_BUDGET, read_report

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "dial-cases.json"
LOG = ROOT / "logs" / "dial-sample.jsonl"
RUNS_LOG = ROOT / "logs" / "dial-runs.jsonl"
PROVIDER = "nightshift"
KILL_DISAGREE = 0.10  # R1 closings the 4k control contradicts, above which R1 is unsafe here
VOID_FAILURES = 10  # more provider failures than this voids the run (a third of 30)
FROZEN_FILES = (
    "app/engine/dial.py",
    "app/engine/rungs.py",
    "app/engine/run_case.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def sha16(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def frozen_case_ids() -> list[str]:
    """The pre-registered sample; raises if the measured code changed since the freeze."""
    frozen = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in frozen["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return list(frozen["cases"])


def _tokens(usage: dict[str, Any] | None) -> int:
    value = (usage or {}).get("completion_tokens")
    return value if isinstance(value, int) else 0


def compare(closed_at_r1: dict[str, str], control: dict[str, Any]) -> dict[str, str]:
    """For each field R1 closed: agree / disagree / unconfirmed against the 4k control."""
    out = {}
    for name, value in closed_at_r1.items():
        fr = control.get(name) or {}
        if fr.get("status") != "accepted":
            out[name] = "unconfirmed"
        elif _comparable(name, fr.get("value")) == _comparable(name, value):
            out[name] = "agree"
        else:
            out[name] = "disagree"
    return out


async def run_one(case_id: str, run_tag: str) -> dict[str, Any]:
    """The ladder and the control for one record; a provider failure is recorded, not retried."""
    row: dict[str, Any] = {"case": case_id, "run": run_tag}
    evidence = await load_evidence(case_id)
    run_id = f"dial-{run_tag}-{uuid.uuid4().hex[:6]}"
    started = time.monotonic()
    ladder = await climb(evidence, run_id=run_id, provider=PROVIDER)
    write_trace(ladder, run_id, None)
    row["ladder_seconds"] = round(time.monotonic() - started, 2)
    row["ladder_status"] = ladder.run.status
    row["rungs"] = [c.get("rung") for c in ladder.chunks if c.get("rung")]
    row["ladder_tokens"] = sum(_tokens(c.get("usage")) for c in ladder.chunks)
    closed_r1 = {n: str(v["value"]) for n, v in ladder.closed.items() if v["rung"] == R1}
    row["closed_at_r1"] = closed_r1
    row["settled_at_r1"] = set(closed_r1) == set(OPEN_FIELDS)
    row["closed"] = {
        n: {"rung": v["rung"], "value": str(v["value"])} for n, v in ladder.closed.items()
    }
    row["open"] = ladder.open_fields
    try:
        started = time.monotonic()
        control = await read_report(
            case_id,
            evidence.report_text,
            provider=PROVIDER,
            budget=THINKING_BUDGET,
            run_id=f"{run_id}-control",
        )
        row["control_seconds"] = round(time.monotonic() - started, 2)
        row["control_tokens"] = _tokens(control.usage)
        row["control_signature"] = control.signature
        row["control"] = {
            name: {"status": fr.status, "value": fr.value, "reason": fr.reason[:80]}
            for name, fr in control.fields.items()
            if name in OPEN_FIELDS
        }
    except Exception as exc:  # a provider failure; the record is reported, never re-run
        row["control_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        row["control"] = {}
    row["provider_failure"] = row["ladder_status"] != "completed" or "control_error" in row
    row["agreement"] = compare(closed_r1, row["control"]) if not row["provider_failure"] else {}
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The pre-registered measures over the scored (no provider failure) records."""
    scored = [r for r in rows if not r["provider_failure"]]
    verdicts = [v for r in scored for v in r["agreement"].values()]
    closed = len(verdicts)
    disagree = verdicts.count("disagree")
    failures = len(rows) - len(scored)
    return {
        "records": len(rows),
        "provider_failures": failures,
        "void": failures > VOID_FAILURES,
        "scored": len(scored),
        "settled_at_r1": sum(r["settled_at_r1"] for r in scored),
        "fields_closed_at_r1": closed,
        "fields_needing_r2": sum(len(r["rungs"]) > 1 for r in scored),
        "r1_vs_control": {v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")},
        "r1_unsafe": closed > 0 and disagree / closed > KILL_DISAGREE,
        "ladder_tokens": sum(r["ladder_tokens"] for r in scored),
        "control_tokens": sum(r.get("control_tokens", 0) for r in scored),
        "ladder_seconds": round(sum(r["ladder_seconds"] for r in scored), 1),
        "control_seconds": round(sum(r.get("control_seconds", 0) for r in scored), 1),
    }


async def run_sample() -> dict[str, Any]:
    case_ids = frozen_case_ids()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        try:
            row = await run_one(case_id, tag)
        except Exception as exc:  # the ladder itself raised: a provider failure, logged
            row = {
                "case": case_id,
                "run": tag,
                "provider_failure": True,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            }
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"run": tag, **summarise(rows)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary
