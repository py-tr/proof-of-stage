"""A second domain with clean text: ClinicalTrials.gov records coded both Randomized and Single Group.

Pre-registered in docs/preregistration/ctgov-read.md (the frozen records, code hashes and the
prediction in ctgov-read.json before the first call). ClinicalTrials.gov's own Protocol
Registration Data Element Definitions say "Single Group: Clinical trials with a single arm",
Allocation "N/A (not applicable): For a single-arm trial", and "Randomized: Participants are
assigned to intervention groups by chance". A record coded Allocation = Randomized and
Interventional Model = Single Group cannot be true as written: either the trial randomized people
to two or more groups (the model field is wrong) or it has one arm (the allocation field is wrong).

Nemotron Super VL (through Nightshift, pinned, signed, no cache, thinking on with a 4k budget)
reads the record's own sponsor-typed text (brief summary, detailed description, arm group
descriptions) and names the field the text contradicts, with ONE verbatim quote. Code checks the
quote is in the text and carries the cue for that verdict. Referee for multi-arm records: the
record's structured arm count (2+ arms means the model field is the wrong one), a field
independent of the two that contradict. One-arm records have no automatic referee: reported as
found. The text is public domain (US government), typed, not scanned. Nothing is stored.
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
from app.engine.dial import sha16
from app.providers import envelope_tap, nightshift
from app.reader.quotes import is_too_short, locate
from app.reader.reader import parse_answer, thinking_args

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "ctgov-read.json"
RECORDS = ROOT / "docs" / "evidence" / "ctgov" / "records.json"
LOG = ROOT / "logs" / "ctgov-read.jsonl"
RUNS_LOG = ROOT / "logs" / "ctgov-read-runs.jsonl"
ENVELOPES = ROOT / "docs" / "evidence" / "attest" / "ctgov-read-envelopes.jsonl"
API = "https://clinicaltrials.gov/api/v2/studies"
QUERY = "AREA[DesignAllocation]RANDOMIZED AND AREA[DesignInterventionModel]SINGLE_GROUP"
SEED = 20261026
MULTI_SAMPLE = 30
BUDGET = 4000
FROZEN_FILES = ("app/engine/ctgov_read.py",)
RANDOM_CUE = re.compile(r"\brandomi[sz]", re.I)
GROUP_CUE = re.compile(
    r"\b(two|three|four|both|either|groups?|arms?|placebo|versus|vs\.?|or|control|1:1|2:1|ratio)\b",
    re.I,
)
SINGLE_CUE = re.compile(
    r"\b(single[- ]arm|single group|one arm|one group|non[- ]?randomi[sz]ed|uncontrolled|"
    r"open[- ]label,? single|all (participants|patients|subjects) (will )?receive)\b",
    re.I,
)
PROMPT = (
    "You read one ClinicalTrials.gov record. Its design is coded Allocation = Randomized and "
    "Interventional Model = Single Group. By the registry's own definitions these cannot both be "
    "true: a single-group trial has one arm and no randomization.\n"
    "Decide which coded field the record's own text contradicts:\n"
    '- "model" if the text shows participants were randomly assigned to two or more groups or '
    "arms (then Single Group is wrong);\n"
    '- "allocation" if the text shows a single arm with no random assignment between groups '
    "(then Randomized is wrong);\n"
    '- "unclear" if the text does not settle it (for example randomization of order in one '
    "group, or no design statement).\n"
    'Return ONLY a JSON object: {"field": "model|allocation|unclear", "quote": "...", '
    '"reason": "one short sentence"}\n'
    "The quote is ONE contiguous passage copied character-for-character from the text that shows "
    "your answer, about this study (not background). Use an empty quote for unclear."
)


def _text(study: dict[str, Any]) -> tuple[str, int, list[str]]:
    s = study.get("protocolSection") or {}
    d = s.get("descriptionModule") or {}
    arms = (s.get("armsInterventionsModule") or {}).get("armGroups") or []
    parts = [d.get("briefSummary") or "", d.get("detailedDescription") or ""]
    parts += [f"Arm {a.get('label', '')}: {a.get('description', '')}" for a in arms]
    return "\n\n".join(p for p in parts if p.strip()), len(arms), [a.get("label", "") for a in arms]


def fetch() -> list[dict[str, Any]]:
    import httpx

    out, token = [], None
    while True:
        params = {"query.term": QUERY, "filter.advanced": "AREA[HasResults]true", "pageSize": "100"}
        if token:
            params["pageToken"] = token
        r = httpx.get(API, params=params, timeout=120)
        r.raise_for_status()
        j = r.json()
        for study in j.get("studies", []):
            text, n_arms, labels = _text(study)
            nct = study["protocolSection"]["identificationModule"]["nctId"]
            out.append({"nct": nct, "arms": n_arms, "arm_labels": labels, "text": text})
        token = j.get("nextPageToken")
        if not token:
            return out


def eligible(rec: dict[str, Any]) -> str | None:
    """Which slice a record belongs to, by code cues alone (no model)."""
    t = rec["text"]
    says_random = bool(RANDOM_CUE.search(t))
    says_single = bool(SINGLE_CUE.search(t))
    if rec["arms"] == 1 and (says_random or says_single):
        return "one_arm"
    if rec["arms"] >= 2 and says_random:
        return "multi_arm"
    return None


def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    records = fetch()
    slices: dict[str, list[str]] = {"one_arm": [], "multi_arm": []}
    for r in records:
        s = eligible(r)
        if s:
            slices[s].append(r["nct"])
    one = sorted(slices["one_arm"])
    multi = sorted(random.Random(SEED).sample(sorted(slices["multi_arm"]), MULTI_SAMPLE))
    keep = set(one) | set(multi)
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    RECORDS.write_text(
        json.dumps([r for r in records if r["nct"] in keep], indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "prompt_sha256_16": sha16(PROMPT),
        "records_sha256_16": sha16(RECORDS.read_text(encoding="utf-8")),
        "population": {
            "with_results": len(records),
            "one_arm_with_a_cue": len(slices["one_arm"]),
            "multi_arm_saying_randomized": len(slices["multi_arm"]),
        },
        "one_arm": one,
        "multi_arm": multi,
        "claim": "multi-arm: the text names the model field with a verified quote on at least 24 of 30, and the allocation field on at most 2",
        "kill": "multi-arm: fewer than 18 of 30 named the model field, or more than 4 named the allocation field",
        "reported_not_claimed": "one-arm records: verdicts as found (no automatic referee)",
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
    if sha16(PROMPT) != record["prompt_sha256_16"]:
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


def check(field: str, quote: str, text: str) -> dict[str, Any]:
    """The code check: the quote is in the text and carries the cue for the field it names."""
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


async def read_one(rec: dict[str, Any], item_id: str) -> dict[str, Any]:
    extra, max_tokens = thinking_args(BUDGET)
    text, receipt = await nightshift.chat(
        [
            {"role": "system", "content": PROMPT},
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
    }


async def run_ctgov_read() -> dict[str, Any]:
    record = frozen()
    records = {r["nct"]: r for r in json.loads(RECORDS.read_text(encoding="utf-8"))}
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    ENVELOPES.parent.mkdir(parents=True, exist_ok=True)
    for slice_name in ("multi_arm", "one_arm"):
        for nct in record[slice_name]:
            rec = records[nct]
            row: dict[str, Any] = {"nct": nct, "slice": slice_name, "arms": rec["arms"], "run": tag}
            with envelope_tap.capture() as calls:
                try:
                    row.update(await read_one(rec, f"ctgov-{tag}-{nct}-{uuid.uuid4().hex[:6]}"))
                except Exception as exc:  # a provider failure: logged, never re-run
                    row["provider_failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            for c in calls:
                with ENVELOPES.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"nct": nct, "run": tag, **c}, sort_keys=True) + "\n")
            rows.append(row)
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def named(rs: list[dict], field: str) -> int:
        return sum(r.get("field") == field and (r.get("check") or {}).get("verified") for r in rs)

    multi = [r for r in rows if r["slice"] == "multi_arm"]
    one = [r for r in rows if r["slice"] == "one_arm"]
    summary = {
        "run": tag,
        "records": len(rows),
        "failures": sum("provider_failure" in r for r in rows),
        "multi_arm": {
            "records": len(multi),
            "model_verified": named(multi, "model"),
            "allocation_verified": named(multi, "allocation"),
            "unclear_or_unverified": len(multi)
            - named(multi, "model")
            - named(multi, "allocation"),
        },
        "one_arm": {
            "records": len(one),
            "model_verified": named(one, "model"),
            "allocation_verified": named(one, "allocation"),
            "unclear_or_unverified": len(one) - named(one, "model") - named(one, "allocation"),
        },
    }
    summary["void"] = summary["failures"] > 8
    m = summary["multi_arm"]
    summary["claim_met"] = (
        not summary["void"] and m["model_verified"] >= 24 and m["allocation_verified"] <= 2
    )
    summary["kill"] = m["model_verified"] < 18 or m["allocation_verified"] > 4
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
