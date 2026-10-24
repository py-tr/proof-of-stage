"""The Ultra critic, v2: v1 unchanged except one Nightshift scope per call.

Pre-registered in docs/preregistration/ultra-critic-v2.md (frozen in ultra-critic-v2.json before
the first call). v1 (app/engine/critic.py, its run and its published result stand as they are)
built each call's item id from case + field + run, so a planted control and the real row with
the same case and field shared one scope and Nightshift's H-MEM attached the earlier answer; our
receipt check refused 5 calls, 3 of them planted. v2 reuses v1's prompt, guard check, planted
rows, interleaving, scoring and ship line unchanged, and gives every call its own item id.
Designed after the blind labels were known (disclosed): Ultra never sees the labels, and the
prompt and every rule are byte-identical to v1.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine import critic
from app.engine.dial import sha16
from app.providers import nightshift
from app.reader.reader import REPORT_CHARS, parse_answer

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "ultra-critic-v2.json"
LOG = ROOT / "logs" / "ultra-critic-v2.jsonl"
RUNS_LOG = ROOT / "logs" / "ultra-critic-v2-runs.jsonl"
FROZEN_FILES = (
    "app/engine/critic_v2.py",
    "app/engine/critic.py",
    "app/reader/reader.py",
    "app/reader/quotes.py",
)


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        path
        for path, digest in record["code_sha256_16"].items()
        if sha16((ROOT / path).read_text(encoding="utf-8")) != digest
    ]
    if record["prompt_sha256_16"] != sha16(critic.PROMPT):
        changed.append("PROMPT")
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    return record


def item_id(case_id: str, field: str, n: int, tag: str) -> str:
    """One Nightshift scope per call: the call's position makes it unique within the run."""
    return f"critic2-{case_id}-{field}-{n:02d}-{tag}-{uuid.uuid4().hex[:6]}"


async def ask(case_id: str, field: str, stored: str, quote: str, report: str, scope: str) -> dict:
    user = (
        f"Field: {critic.FIELD_NAME[field]}\nStored value: {stored}\n"
        f"The quote it rests on: {quote or '(none)'}\n\nPathology report:\n\n"
        + report[:REPORT_CHARS]
    )
    row: dict[str, Any] = {"case": case_id, "field": field, "stored": stored, "scope": scope}
    started = time.monotonic()
    try:
        text, receipt = await nightshift.chat(
            [{"role": "system", "content": critic.PROMPT}, {"role": "user", "content": user}],
            config.NV_ULTRA,
            item_id=scope,
            require_model=config.NV_ULTRA,
            require_kind="cloud",
            retry_on_mismatch=True,
            require_signature=True,
            pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
            allow_cache=False,
            max_tokens=critic.MAX_TOKENS,
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
        row["check"] = critic.verify_objection(
            field, answer.get("value"), answer.get("quote"), stored, report
        )
    return row


async def run_critic_v2() -> dict[str, Any]:
    record = frozen()
    real, reports = await critic.collect_rows(list(record["cases"]))
    planted = [dict(p) for p in record["planted"]]
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    failures, scopes = 0, set()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for n, item in enumerate(critic.interleave(real, planted)):
        scope = item_id(item["case"], item["field"], n, tag)
        scopes.add(scope)
        row = await ask(
            item["case"],
            item["field"],
            item["stored"],
            item["quote"] or "(none)",
            reports[item["case"]],
            scope,
        )
        row["run"] = tag
        row["planted"] = bool(item.get("planted"))
        if item.get("planted"):
            row["original"] = item.get("original")
        failures += "error" in row
        with LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "run": tag,
        "calls": len(real) + len(planted),
        "unique_scopes": len(scopes),
        "provider_failures": failures,
    }
    with RUNS_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(summary) + "\n")
    return summary
