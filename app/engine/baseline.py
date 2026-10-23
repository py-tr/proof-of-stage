"""Nemotron alone (M0): what Super says about a queue case without our guard or the USL.

Pre-registered in docs/preregistration/baseline-m0.md (cases, prompt and code hashes frozen
in baseline-cases.json before the first call; the scoring rule fixed before the blind labels
were frozen). For each review-queue case, one prompt gives Super what the labeller had
(the registry's recorded N and positive-node count, the paraphrased count rule, the full
report) and asks which registry field the report contradicts, with one verbatim quote.
Two arms: thinking off and a 4k budget, both through Nightshift (Super VL pinned, signed
receipt, no cache). Nothing is stored; no guard runs. Scored afterwards against the blind
labels, next to A0 (our stage_check.fault_field) and B0 (the USL rule alone: recompute N
from the count, i.e. always "the N category is wrong").
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.run_case import _rows
from app.providers import nightshift
from app.reader.quotes import is_too_short, locate
from app.reader.reader import REPORT_CHARS, parse_answer, thinking_args

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "baseline-cases.json"
LABELS = ROOT / "docs" / "preregistration" / "ground-truth-labels.json"
LOG = ROOT / "logs" / "baseline-m0.jsonl"
RUNS_LOG = ROOT / "logs" / "baseline-m0-runs.jsonl"
ARMS = {"off": 0, "4k": 4000}
FAULTS = ("node_count", "pathologic_n", "review")
VOID_FAILURES = 8  # more provider failures than this in an arm voids that arm (a third of 25)
FROZEN_FILES = ("app/engine/baseline.py", "app/reader/quotes.py")

PROMPT = (
    "A cancer registry recorded two fields for one breast cancer case: the pathologic N "
    "category (AJCC) and the number of positive regional lymph nodes. The two disagree "
    "under the count rule (N0 = no positive nodes, N1 = 1-3, N2 = 4-9, N3 = 10 or more; "
    "micrometastases and isolated tumour cells are their own categories), or the N is "
    "missing. Read the pathology report and decide which registry field the report "
    "contradicts.\n"
    "Return ONLY a JSON object with these keys:\n"
    '{"fault": "...", "report_count": 0, "report_n": "...", "quote": "...", "reason": "..."}\n'
    "Rules:\n"
    '- fault is "node_count" (the report backs the recorded N, so the recorded count is '
    'wrong), "pathologic_n" (the report backs the recorded count, so the recorded N is '
    'wrong or missing) or "review" (the report settles neither, contradicts both, or is '
    "unclear: a person must decide).\n"
    "- report_count: the total positive regional lymph nodes the report states (integer), "
    'or null; report_n: the N category the report prints (e.g. "pN1a"), or "".\n'
    "- quote: ONE contiguous passage copied character-for-character from the report that "
    "supports your decision. No ellipsis, no paraphrase.\n"
    "- reason: one short sentence."
)


def sha16(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def frozen() -> dict[str, Any]:
    """The pre-registration; raises if the measured code or the prompt changed since."""
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if record["prompt_sha256_16"] != sha16(PROMPT):
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


def _number(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return None


def user_message(row: dict[str, Any], report: str) -> str:
    return (
        f"AJCC edition: {row.get('edition_code') or 'unknown'}\n"
        f"Registry recorded N category: {row.get('recorded_n') or 'missing'}\n"
        f"Registry recorded positive lymph nodes: {_number(row.get('lymph_nodes_positive'))}\n"
        f"Registry recorded lymph nodes examined: {_number(row.get('lymph_nodes_tested'))}\n"
        f"The count rule turns the recorded count into: {row.get('derived_n') or 'unknown'}\n\n"
        "Pathology report:\n\n" + report[:REPORT_CHARS]
    )


def judge(text: str, report: str) -> dict[str, Any]:
    """The answer's fault, and whether its quote is in the report (no other check)."""
    answer = parse_answer(text)
    if answer is None:
        return {"fault": None, "parsed": False, "quote_in_report": False}
    fault = str(answer.get("fault") or "").strip().lower()
    quote = answer.get("quote") if isinstance(answer.get("quote"), str) else ""
    located = bool(quote) and not is_too_short(quote) and locate(quote, report) is not None
    return {
        "fault": fault if fault in FAULTS else None,
        "parsed": True,
        "quote": quote[:300],
        "quote_in_report": located,
        "report_count": answer.get("report_count"),
        "report_n": str(answer.get("report_n") or "")[:20],
        "reason": str(answer.get("reason") or "")[:200],
    }


async def ask(case_id: str, row: dict[str, Any], report: str, arm: str, run: str) -> dict:
    extra, max_tokens = thinking_args(ARMS[arm])
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": user_message(row, report)},
    ]
    started = time.monotonic()
    text, receipt = await nightshift.chat(
        messages,
        config.NS_SUPER_VL,
        item_id=f"m0-{case_id}-{run}-{arm}",
        require_model=config.NS_SUPER_VL,
        retry_on_mismatch=True,
        require_signature=True,
        pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
        allow_cache=False,
        max_tokens=max_tokens,
        **extra,
    )
    return {
        "seconds": round(time.monotonic() - started, 2),
        "completion_tokens": (receipt.usage or {}).get("completion_tokens"),
        "signature": receipt.signature,
        "model": receipt.winning_model,
        **judge(text, report),
    }


async def queue_rows(case_ids: list[str]) -> dict[str, dict[str, Any]]:
    from app.usl.client import select
    from app.usl.model import table_fqn

    rows = _rows(
        await select(
            "SELECT case_id, edition_code, recorded_n, lymph_nodes_positive, "
            f"lymph_nodes_tested, derived_n, fault_field FROM {table_fqn('stage_check')} "
            "WHERE reason_class IN ('n_count_contradiction', 'n_missing_derivable')",
            limit=100,
        )
    )
    return {r["case_id"]: r for r in rows if r["case_id"] in case_ids}


async def run_baseline() -> dict[str, Any]:
    from app.reports.ingest import read_reports_csv

    record = frozen()
    case_ids = list(record["cases"])
    rows = await queue_rows(case_ids)
    reports = read_reports_csv()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run = f"{tag}-{uuid.uuid4().hex[:6]}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    failures = dict.fromkeys(ARMS, 0)
    for case_id in case_ids:
        out: dict[str, Any] = {"case": case_id, "run": tag}
        for arm in ARMS:
            try:
                out[arm] = await ask(case_id, rows[case_id], reports[case_id].report_text, arm, run)
            except Exception as exc:  # a provider failure: recorded, never re-run
                out[arm] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                failures[arm] += 1
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(out, ensure_ascii=False) + "\n")
    summary = {
        "run": tag,
        "cases": len(case_ids),
        "provider_failures": failures,
        "void": {arm: n > VOID_FAILURES for arm, n in failures.items()},
    }
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary


def score(
    m0_rows: list[dict[str, Any]], labels: dict[str, Any], a0: dict[str, str | None]
) -> dict[str, Any]:
    """The pre-registered measures: each method's agreement with the blind labels.

    A case is scored when the labeller chose a field. M0 per arm counts a provider failure
    or an unusable answer as a miss (it is reported separately too). B0 always says
    pathologic_n. Quote-not-in-report is over M0's parsed answers.
    """
    labelled = {c: v["field"] for c, v in labels.items() if v.get("field") in FAULTS}
    by_case = {r["case"]: r for r in m0_rows}
    out: dict[str, Any] = {"labelled": len(labelled)}

    def tally(say: dict[str, str | None]) -> dict[str, Any]:
        hits = sum(say.get(c) == f for c, f in labelled.items())
        return {"agree": hits, "of": len(labelled)}

    out["A0_ours"] = tally(a0)
    out["B0_rule_alone"] = tally(dict.fromkeys(labelled, "pathologic_n"))
    for arm in ARMS:
        answers = {c: (by_case.get(c) or {}).get(arm) or {} for c in labelled}
        parsed = [a for a in answers.values() if a.get("parsed")]
        out[f"M0_{arm}"] = {
            **tally({c: a.get("fault") for c, a in answers.items()}),
            "provider_failures": sum("error" in a for a in answers.values()),
            "unusable": sum("error" not in a and a.get("fault") is None for a in answers.values()),
            "quote_not_in_report": sum(not a["quote_in_report"] for a in parsed),
            "parsed": len(parsed),
        }
    out["per_case"] = {
        c: {
            "label": f,
            "A0": a0.get(c),
            **{f"M0_{arm}": ((by_case.get(c) or {}).get(arm) or {}).get("fault") for arm in ARMS},
        }
        for c, f in sorted(labelled.items())
    }
    return out
