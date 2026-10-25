"""ClinicalTrials.gov read v2: v1 unchanged except the quote check's cue vocabulary, on new records.

Pre-registered in docs/preregistration/ctgov-read-v2.md (frozen in ctgov-read-v2.json before the
first call). v1 (app/engine/ctgov_read.py, its run and its published result stand as they are)
named the wrong field on none of 30 multi-arm records but accepted only 14 (bar 24): its cue check
required "randomiz-" and a two-groups word, and turned away correct statements such as "randomly
assigned … or to the control group" and "randomized to 1 of 3 routes". v2 keeps v1's prompt,
reader, model, budget, records source and bar, and widens only the cue vocabulary (below). It reads
30 NEW multi-arm records (drawn with a new seed from the pool minus all of v1's records), never the ones the
vocabulary was widened on. Designed after v1's miss; disclosed.
"""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.engine import ctgov_read as v1
from app.engine.dial import sha16
from app.providers import envelope_tap, nightshift
from app.reader.quotes import is_too_short, locate
from app.reader.reader import parse_answer, thinking_args

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "ctgov-read-v2.json"
RECORDS = ROOT / "docs" / "evidence" / "ctgov" / "records-v2.json"
LOG = ROOT / "logs" / "ctgov-read-v2.jsonl"
RUNS_LOG = ROOT / "logs" / "ctgov-read-v2-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "ctgov-read-v2-envelopes.jsonl"
SEED = 20261027
SAMPLE = 30
FROZEN_FILES = ("app/engine/ctgov_read_v2.py", "app/engine/ctgov_read.py")
RANDOM_CUE = re.compile(r"\brandom(?:i[sz](?:ed|ation|ing|e)?|ly)\b", re.I)
GROUP_CUE = re.compile(
    r"\b(two|three|four|five|one of|\d+|both|either|each|groups?|arms?|placebo|versus|vs\.?|or|"
    r"control(?:led|s)?|comparator|ratio)\b",
    re.I,
)
SINGLE_CUE = re.compile(
    r"\b(single[- ]arm|single group|single[- ]cohort|one arm|one group|one cohort|"
    r"non[- ]?randomi[sz]ed|uncontrolled|open[- ]label,? single|"
    r"all (participants|patients|subjects) (will )?(receive|be treated))\b",
    re.I,
)


def check(field: str, quote: str, text: str) -> dict[str, Any]:
    """v1's check with the widened cue vocabulary; nothing else changed."""
    if field not in ("model", "allocation"):
        return {"verified": False, "reason": "unclear_or_invalid"}
    if is_too_short(quote):
        return {"verified": False, "reason": "quote_too_short"}
    span = locate(quote, text)
    if span is None:
        return {"verified": False, "reason": "quote_not_in_text"}
    q = span.text(text)
    if field == "model" and not (RANDOM_CUE.search(q) and GROUP_CUE.search(q)):
        return {"verified": False, "reason": "quote_lacks_randomized_groups_cue"}
    if field == "allocation" and not SINGLE_CUE.search(q):
        return {"verified": False, "reason": "quote_lacks_single_arm_cue"}
    return {"verified": True, "reason": "", "quote": q}


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    v1_record = json.loads(v1.PREREG.read_text(encoding="utf-8"))
    seen = set(v1_record["multi_arm"]) | set(v1_record["one_arm"])
    records = v1.fetch()
    pool = sorted(
        r["nct"] for r in records if v1.eligible(r) == "multi_arm" and r["nct"] not in seen
    )
    drawn = sorted(random.Random(SEED).sample(pool, SAMPLE))
    RECORDS.write_text(
        json.dumps([r for r in records if r["nct"] in set(drawn)], indent=1, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "prompt_sha256_16": sha16(v1.PROMPT),
        "records_sha256_16": sha16(RECORDS.read_text(encoding="utf-8")),
        "pool_after_v1": len(pool),
        "multi_arm": drawn,
        "claim": "the reader names the model field with a verified quote on at least 24 of 30 new multi-arm records, and the allocation field on at most 2",
        "kill": "fewer than 18 of 30 named the model field, or more than 4 named the allocation field",
        "void": "more than 8 provider failures",
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
    if sha16(v1.PROMPT) != record["prompt_sha256_16"]:
        changed.append("PROMPT")
    if sha16(RECORDS.read_text(encoding="utf-8")) != record["records_sha256_16"]:
        changed.append(RECORDS.name)
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


async def read_one(rec: dict[str, Any], item_id: str) -> dict[str, Any]:
    extra, max_tokens = thinking_args(v1.BUDGET)
    text, receipt = await nightshift.chat(
        [
            {"role": "system", "content": v1.PROMPT},
            {"role": "user", "content": "Record text:\n\n" + rec["text"][:24000]},
        ],
        config.NS_SUPER_VL,
        item_id=item_id,
        require_model=config.NS_SUPER_VL,
        retry_on_mismatch=True,
        require_signature=True,
        pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
        allow_cache=False,
        max_tokens=max_tokens,
        **extra,
    )
    answer = parse_answer(text) or {}
    field = str(answer.get("field") or "").strip().lower()
    quote = answer.get("quote") if isinstance(answer.get("quote"), str) else ""
    return {
        "receipt_id": receipt.receipt_id,
        "signature": receipt.signature,
        "field": field,
        "quote": quote,
        "reason": str(answer.get("reason") or "")[:200],
        "check": check(field, quote, rec["text"]),
        "check_v1": v1.check(field, quote, rec["text"]),
    }


async def run_ctgov_read_v2() -> dict[str, Any]:
    record = frozen()
    records = {r["nct"]: r for r in json.loads(RECORDS.read_text(encoding="utf-8"))}
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for nct in record["multi_arm"]:
        rec = records[nct]
        row: dict[str, Any] = {"nct": nct, "slice": "multi_arm", "arms": rec["arms"], "run": tag}
        with envelope_tap.capture() as calls:
            try:
                row.update(await read_one(rec, f"ctgov2-{tag}-{nct}-{uuid.uuid4().hex[:6]}"))
            except Exception as exc:  # a provider failure: logged, never re-run
                row["provider_failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        for c in calls:
            with ENVELOPES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"nct": nct, "run": tag, **c}, sort_keys=True) + "\n")
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def named(field: str, key: str = "check") -> int:
        return sum(r.get("field") == field and (r.get(key) or {}).get("verified") for r in rows)

    summary = {
        "run": tag,
        "records": len(rows),
        "failures": sum("provider_failure" in r for r in rows),
        "model_verified": named("model"),
        "allocation_verified": named("allocation"),
        "model_verified_under_v1_check": named("model", "check_v1"),
    }
    summary["void"] = summary["failures"] > 8
    summary["claim_met"] = (
        not summary["void"]
        and summary["model_verified"] >= 24
        and summary["allocation_verified"] <= 2
    )
    summary["kill"] = summary["model_verified"] < 18 or summary["allocation_verified"] > 4
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
