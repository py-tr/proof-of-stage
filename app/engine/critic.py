"""A second reader that can only object: Nemotron Ultra checks each stored value on the queue.

Pre-registered in docs/preregistration/ultra-critic.md (the prompt and this code frozen in
ultra-critic.json before the first call, and before the blind labels are frozen). For every report
value the layer has stored for the 25 review-queue cases (stage_check.report_n and
report_nodes_positive, first write kept), Ultra, through Nightshift (pinned, signed, no cache,
thinking on without a budget: the hosted Ultra rejects one), reads the report, the field, the
stored value and the quote it rests on, and answers agree, contradiction (a different value with
ONE verbatim quote) or cannot tell. Code checks an objection with the same guard as the reader:
the quote must be in the report and show the objecting value. A verified objection can only send
the case to a person; it never accepts or changes a value. In this run nothing is written: the
answers are logged unread and scored only against the frozen labels.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine.dial import sha16
from app.engine.rungs import main_n
from app.providers import nightshift
from app.reader.reader import (
    REPORT_CHARS,
    judge_count,
    judge_field,
    normalise_category,
    parse_answer,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "ultra-critic.json"
LOG = ROOT / "logs" / "ultra-critic.jsonl"
RUNS_LOG = ROOT / "logs" / "ultra-critic-runs.jsonl"
MAX_TOKENS = 8000
VOID_FAILURES = 8
SHIP_MAX_OBJECTIONS = 8  # more verified objections than this and the critic is noise
FROZEN_FILES = ("app/engine/critic.py", "app/reader/reader.py", "app/reader/quotes.py")
FIELD_NAME = {
    "N": "the pathologic N category",
    "NPOS": "the number of positive regional lymph nodes",
}

PROMPT = (
    "You are a second reader checking one value another reader took from a breast cancer "
    "pathology report. You get the report, the field, the stored value and the quote it rests "
    "on. Decide whether the report as a whole supports that value for that field.\n"
    "Return ONLY a JSON object:\n"
    '{"verdict": "agree" | "contradiction" | "cannot_tell", "value": "...", "quote": "...", '
    '"reason": "one sentence"}\n'
    "Rules:\n"
    "- agree: the report supports the stored value. value and quote may be empty.\n"
    "- contradiction: the report states a DIFFERENT value for this field (for example a total "
    "elsewhere in the report, or a printed category). value: that value (an N category like "
    "N1A, or an integer count); quote: ONE contiguous passage copied character for character "
    "from the report that states it. No paraphrase, no ellipsis.\n"
    "- cannot_tell: the report does not settle it.\n"
    "Isolated tumour cells are not positive nodes; micrometastases are."
)


def frozen() -> dict[str, Any]:
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


def verify_objection(field: str, value: Any, quote: Any, stored: Any, report: str) -> dict:
    """The guard on an objection: the quote is in the report, shows the value, and the value
    differs from the stored one."""
    if field == "N":
        result = judge_field("N", {"N": value, "N_quote": quote}, report)
        new = main_n(result.value) if result.value else None
        old = main_n(normalise_category("N", str(stored)) or str(stored))
    else:
        result = judge_count({"N_positive": value, "N_positive_quote": quote}, report)
        new = None if result.value is None else int(float(result.value))
        old = None if stored in (None, "") else int(float(stored))
    verified = result.status == "accepted" and new is not None and new != old
    reason = result.reason if result.status != "accepted" else ("" if verified else "same_value")
    return {"verified": verified, "value": None if new is None else str(new), "reason": reason}


async def ask(case_id: str, field: str, stored: str, quote: str, report: str, tag: str) -> dict:
    user = (
        f"Field: {FIELD_NAME[field]}\nStored value: {stored}\n"
        f"The quote it rests on: {quote or '(none)'}\n\nPathology report:\n\n"
        + report[:REPORT_CHARS]
    )
    row: dict[str, Any] = {"case": case_id, "field": field, "stored": stored, "run": tag}
    started = time.monotonic()
    try:
        text, receipt = await nightshift.chat(
            [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}],
            config.NV_ULTRA,
            item_id=f"critic-{case_id}-{field}-{tag}",
            require_model=config.NV_ULTRA,
            require_kind="cloud",
            retry_on_mismatch=True,
            require_signature=True,
            pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
            allow_cache=False,
            max_tokens=MAX_TOKENS,
            chat_template_kwargs={"enable_thinking": True},
        )
    except Exception as exc:  # a provider failure: recorded, never re-run
        row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return row
    row["seconds"] = round(time.monotonic() - started, 2)
    row["tokens"] = (receipt.usage or {}).get("completion_tokens") or 0
    row["served"], row["signature"], row["receipt_id"] = (
        receipt.winning_model,
        receipt.signature,
        receipt.receipt_id,
    )
    answer = parse_answer(text) or {}
    verdict = str(answer.get("verdict") or "").strip().lower()
    row["verdict"] = verdict if verdict in ("agree", "contradiction", "cannot_tell") else "unusable"
    row["value"], row["quote"] = answer.get("value"), answer.get("quote")
    row["reason"] = str(answer.get("reason") or "")[:300]
    if row["verdict"] == "contradiction":
        row["check"] = verify_objection(
            field, answer.get("value"), answer.get("quote"), stored, report
        )
    return row


SEED = 20261024
PLANTED_COUNT = {"NPOS": 3, "N": 2}
PLANTS_NEEDED = 4  # of 5


def _key(field: str, value: Any) -> Any:
    """N by main category, a count as an integer: what decides agreement."""
    if value in (None, ""):
        return None
    if field == "N":
        return main_n(normalise_category("N", str(value)) or str(value))
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def build_planted(real: list[dict[str, Any]], seed: int = SEED) -> list[dict[str, Any]]:
    """The positive control: 3 count and 2 N rows from real (case, field) pairs that have a quote;
    each gets another queue case's stored value for the same field that differs (the quote shown
    stays the real one). Deterministic for a seed."""
    import random

    rng = random.Random(seed)
    planted = []
    for field, n in PLANTED_COUNT.items():
        pool = sorted(
            (r for r in real if r["field"] == field and r.get("quote")),
            key=lambda r: r["case"],
        )
        values = sorted({r["stored"] for r in real if r["field"] == field}, key=str)
        for row in rng.sample(pool, n):
            options = [v for v in values if _key(field, v) != _key(field, row["stored"])]
            planted.append({**row, "original": row["stored"], "stored": rng.choice(options)})
    return planted


def interleave(real: list[dict], planted: list[dict]) -> list[dict]:
    """Planted rows spread through the real ones at fixed positions (every ~8th call)."""
    out, step = list(real), max(1, len(real) // (len(planted) + 1))
    for n, row in enumerate(planted, start=1):
        out.insert(min(len(out), n * step + n - 1), {**row, "planted": True})
    return out


def first_completed_run(rows: list[dict], runs: list[dict]) -> list[dict]:
    """Only the first run that wrote a summary counts; an aborted run is excluded."""
    if not runs:
        return []
    tag = runs[0]["run"]
    return [r for r in rows if r.get("run") == tag]


def verdict_class(row: dict[str, Any]) -> str:
    if "error" in row:
        return "error"
    if row.get("verdict") == "contradiction":
        return (
            "contradiction_verified"
            if (row.get("check") or {}).get("verified")
            else "contradiction_unverified"
        )
    return row.get("verdict") or "unusable"


def score(rows: list[dict[str, Any]], labels: dict[str, Any]) -> dict[str, Any]:
    """The pre-registered measures over one run's rows (docs/preregistration/ultra-critic.md)."""
    real = [r for r in rows if not r.get("planted")]
    planted = [r for r in rows if r.get("planted")]
    classes: dict[str, int] = {}
    for r in real:
        classes[verdict_class(r)] = classes.get(verdict_class(r), 0) + 1

    def label_value(case: str, field: str) -> Any:
        lab = labels.get(case) or {}
        return (
            _key(field, lab.get("n"))
            if field == "N"
            else _key(field, str(lab.get("count") or "").strip() or None)
        )

    out: dict[str, Any] = {"classes": classes, "right": 0, "wrong": 0, "unscored": 0, "missed": 0}
    objections = []
    for r in real:
        if verdict_class(r) == "error":
            continue
        truth = label_value(r["case"], r["field"])
        objected = verdict_class(r) == "contradiction_verified"
        if objected:
            objections.append(
                {
                    "case": r["case"],
                    "field": r["field"],
                    "stored": r["stored"],
                    "objection": (r.get("check") or {}).get("value"),
                    "quote": r.get("quote"),
                }
            )
        if truth is None:
            out["unscored"] += objected
            continue
        label_disagrees = truth != _key(r["field"], r["stored"])
        if objected:
            out["right" if label_disagrees else "wrong"] += 1
        elif label_disagrees and verdict_class(r) in ("agree", "cannot_tell"):
            out["missed"] += 1
    detected = [p for p in planted if verdict_class(p) == "contradiction_verified"]
    out["objections"] = len(objections)
    out["objection_list"] = objections
    out["plants"] = {
        "planted": len(planted),
        "detected": len(detected),
        "objected_value_is_original": sum(
            _key(p["field"], (p.get("check") or {}).get("value"))
            == _key(p["field"], p.get("original"))
            for p in detected
        ),
    }
    out["void"] = (
        classes.get("error", 0) > VOID_FAILURES or classes.get("unusable", 0) > VOID_FAILURES
    )
    out["ships"] = (
        not out["void"]
        and len(detected) >= PLANTS_NEEDED
        and out["objections"] <= SHIP_MAX_OBJECTIONS
        and out["right"] > out["wrong"]
        and out["wrong"] <= 1
    )
    return out


async def collect_rows(case_ids: list[str]) -> tuple[list[dict], dict[str, str]]:
    """Every stored report value for the queue with its accepted quote, and each case's report."""
    from app.web.api import _rechecked
    from app.web.data import LiveData

    data, rows, reports = LiveData(), [], {}
    for case_id in case_ids:
        found = await data.case(case_id) or {}
        reports[case_id] = found.get("report_text") or ""
        accepted = {r["field"]: r for r in _rechecked(found) if r.get("field") in FIELD_NAME}
        stage = found.get("check") or {}
        for field, value in (
            ("N", stage.get("report_n")),
            ("NPOS", stage.get("report_nodes_positive")),
        ):
            if value in (None, ""):
                continue
            quote = (accepted.get(field) or {}).get("quote") or ""
            rows.append({"case": case_id, "field": field, "stored": str(value), "quote": quote})
    return rows, reports


async def run_critic() -> dict[str, Any]:
    record = frozen()
    real, reports = await collect_rows(list(record["cases"]))
    planted = [dict(p) for p in record["planted"]]
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    failures = 0
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for item in interleave(real, planted):
        row = await ask(
            item["case"],
            item["field"],
            item["stored"],
            item["quote"] or "(none)",
            reports[item["case"]],
            tag,
        )
        row["planted"] = bool(item.get("planted"))
        if item.get("planted"):
            row["original"] = item.get("original")
        if not item["quote"]:
            row["quote_missing"] = True
        failures += "error" in row
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "run": tag,
        "calls": len(real) + len(planted),
        "real": len(real),
        "planted": len(planted),
        "provider_failures": failures,
    }
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary
