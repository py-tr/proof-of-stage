"""Lightning as the cheap rung: Nemotron Lightning in R1's place, on the dial test's records.

Pre-registered in docs/preregistration/lightning-r1.md (cases, code hashes frozen in
lightning-cases.json before the first call). On each of the 28 records the dial test scored,
one read by `nvidia/nemotron-3.5-lightning-30b-a3b` through Nightshift (pinned in the signed
receipt, cloud, no cache), thinking off, with the reader's prompt and guard unchanged. R1's
closing rule is applied as in the ladder: a field closes only if its accepted value agrees
with the registry and the reading is self-consistent under the count rule. Compared with
Super's R1 in the dial run (same records) and with the dial run's always-4k control.
Nothing is stored.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import compare, sha16
from app.engine.run_case import load_evidence
from app.engine.rungs import OPEN_FIELDS, agrees_with_registry, self_consistent
from app.providers import nightshift
from app.reader.reader import (
    FIELDS,
    NODES_POSITIVE,
    REPORT_CHARS,
    SYSTEM_PROMPT,
    THINKING_OFF,
    ReadResult,
    judge_count,
    judge_field,
    parse_answer,
    thinking_args,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "lightning-cases.json"
DIAL_LOG = ROOT / "logs" / "dial-sample.jsonl"
CHUNKS = ROOT / "logs" / "markovian-chunks.jsonl"
LOG = ROOT / "logs" / "lightning-r1.jsonl"
RUNS_LOG = ROOT / "logs" / "lightning-r1-runs.jsonl"
MODEL = config.NS_LIGHTNING_CLOUD
KILL_DISAGREE = 0.10  # the dial test's line: control contradicts more than 10% of closings
VOID_FAILURES = 9  # more provider failures than this voids the run (a third of 28)
FROZEN_FILES = (
    "app/engine/lightning.py",
    "app/engine/rungs.py",
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


async def read_lightning(case_id: str, report: str, run_id: str) -> ReadResult:
    """read_report's call with Lightning pinned instead of Super VL; same prompt and guard."""
    extra, max_tokens = thinking_args(THINKING_OFF)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
    ]
    text, receipt = await nightshift.chat(
        messages,
        MODEL,
        item_id=f"lightning-{case_id}-{run_id}",
        require_model=MODEL,
        require_kind="cloud",
        retry_on_mismatch=True,
        require_signature=True,
        pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
        allow_cache=False,
        max_tokens=max_tokens,
        **extra,
    )
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=receipt.winning_model or "",
        receipt_id=receipt.receipt_id,
        provider="nightshift",
        raw_text=text,
        budget=THINKING_OFF,
        usage=receipt.usage,
        from_cache=receipt.from_cache,
        signature=receipt.signature,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)
    result.fields[NODES_POSITIVE] = judge_count(answer, report)
    return result


def r1_closings(result: ReadResult, evidence: Any) -> dict[str, str]:
    """The fields R1's rule would close on this reading (field -> value)."""
    if not self_consistent(result, evidence.edition):
        return {}
    return {
        name: str(result.fields[name].value)
        for name in OPEN_FIELDS
        if agrees_with_registry(name, result.fields[name], evidence)
    }


def super_r1(dial_run: str, chunks: Path = CHUNKS) -> dict[str, dict[str, Any]]:
    """Super's R1 per case in the dial run: completion tokens and seconds."""
    out: dict[str, dict[str, Any]] = {}
    for line in chunks.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("rung") == "R1" and str(row.get("run_id", "")).startswith(f"dial-{dial_run}-"):
            usage = row.get("usage") or {}
            out[row["case"]] = {
                "tokens": usage.get("completion_tokens") or 0,
                "seconds": row.get("seconds") or 0,
            }
    return out


def summarise(rows: list[dict[str, Any]], dial: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if "error" not in r]
    verdicts = [v for r in scored for v in r["agreement"].values()]
    disagree = verdicts.count("disagree")
    failures = len(rows) - len(scored)
    return {
        "records": len(rows),
        "provider_failures": failures,
        "void": failures > VOID_FAILURES,
        "scored": len(scored),
        "lightning_settled": sum(r["settled"] for r in scored),
        "super_settled": sum(bool(dial[r["case"]]["settled_at_r1"]) for r in scored),
        "lightning_fields_closed": len(verdicts),
        "super_fields_closed": sum(len(dial[r["case"]]["closed_at_r1"]) for r in scored),
        "lightning_vs_control": {
            v: verdicts.count(v) for v in ("agree", "disagree", "unconfirmed")
        },
        "unsafe": bool(verdicts) and disagree / len(verdicts) > KILL_DISAGREE,
        "lightning_tokens": sum(r["tokens"] for r in scored),
        "super_r1_tokens": sum(r["super_r1_tokens"] for r in scored),
        "lightning_seconds": round(sum(r["seconds"] for r in scored), 1),
        "super_r1_seconds": round(sum(r["super_r1_seconds"] for r in scored), 1),
    }


async def run_lightning() -> dict[str, Any]:
    case_ids = frozen_case_ids()
    dial_rows = [json.loads(line) for line in DIAL_LOG.read_text(encoding="utf-8").splitlines()]
    dial = {r["case"]: r for r in dial_rows}
    dial_run = dial_rows[0]["run"]
    super_rows = super_r1(dial_run)
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run = f"{tag}-{uuid.uuid4().hex[:6]}"
    rows = []
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        row: dict[str, Any] = {"case": case_id, "run": tag}
        try:
            evidence = await load_evidence(case_id)
            started = time.monotonic()
            result = await read_lightning(case_id, evidence.report_text, run)
            row["seconds"] = round(time.monotonic() - started, 2)
            row["tokens"] = (result.usage or {}).get("completion_tokens") or 0
            row["model"], row["signature"] = result.model, result.signature
            row["fields"] = {
                n: {"status": f.status, "value": f.value, "reason": f.reason[:80]}
                for n, f in result.fields.items()
                if n in OPEN_FIELDS
            }
            closed = r1_closings(result, evidence)
            row["closed"] = closed
            row["settled"] = set(closed) == set(OPEN_FIELDS)
            row["agreement"] = compare(closed, dial[case_id]["control"])
            row["super_closed"] = dial[case_id]["closed_at_r1"]
            row["super_r1_tokens"] = super_rows.get(case_id, {}).get("tokens", 0)
            row["super_r1_seconds"] = super_rows.get(case_id, {}).get("seconds", 0)
        except Exception as exc:  # a provider failure: recorded, never re-run
            row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"run": tag, **summarise(rows, dial)}
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary
