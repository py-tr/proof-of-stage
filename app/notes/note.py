"""A short case note for the reviewer, written by Nemotron Super through Meterless Nightshift.

Code first lists the case's facts, each with an id: what the registry records, what the count
rule derives, which field the semantic layer names (stage_check.fault_field) and every accepted
report quote. Super may only restate them: 1-4 sentences, each citing the fact ids it uses.
Code then checks every sentence: each cited id exists, and every number and stage category in
the sentence appears in the facts it cites. A note that fails any check is not shown.

The call goes through Nightshift with Super VL pinned, the receipt's Ed25519 signature
verified and cached answers refused; the receipt is kept with the note.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import config
from app.providers import nightshift, nvidia
from app.providers.receipts import key_fingerprint
from app.reader.reader import NODES_POSITIVE, parse_answer
from app.web.evidence import n_range

ROOT = Path(__file__).resolve().parents[2]
NOTES_LOG = ROOT / "logs" / "case-notes.jsonl"
# Ultra notes (NVIDIA direct, no receipt) go to their own log; the page reads only NOTES_LOG.
ULTRA_LOG = ROOT / "logs" / "case-notes-ultra.jsonl"
MAX_SENTENCES = 4
MAX_WORDS = 35  # per sentence
# Thinking stays on for the note. Measured 2026-10-23 through Nightshift 1.2.3: with thinking
# off, 25 of 25 notes answered (median 4.4 s) but only 4 passed the guard (fact ids in the
# text, words not in the facts); with thinking on, 12 of 20 passed at run time.
NOTE_EXTRA: dict[str, Any] = {}
MAX_TOKENS = 4000

SYSTEM_PROMPT = (
    "You write a short case note for a cancer-registry reviewer. Use ONLY the numbered facts "
    "given; add nothing else. Answer in under 100 words of JSON, no explanation:\n"
    '{"sentences": [{"text": "...", "cites": ["F1", "Q1"]}]}\n'
    f"Rules: 1 to {MAX_SENTENCES} sentences, each under {MAX_WORDS} words; every sentence "
    'cites the ids of the facts it uses (in "cites" only, never in the text); every number '
    "and stage category you write must appear in a fact that sentence cites; say which "
    "field the semantic layer names and why, then that a person decides. Never recommend "
    "a value the facts do not state, and never say anyone reviewed, confirmed or judged "
    "anything the facts do not say."
)

FAULT_WORDS = {
    "node_count": "the positive-node count field",
    "pathologic_n": "the N category field",
    "review": "neither field (a person must decide)",
}
_CITE = re.compile(r"^[FQ]\d{1,2}$")
_ID_IN_TEXT = re.compile(r"\b[FQ]\d{1,2}\b")
# Words that claim an action or a judgment; a sentence may use one only if a fact it cites
# does ("A reviewer verified the report" passed the number check, but no reviewer did).
_CLAIM = re.compile(
    r"\b(?:review(?:er|ed)s?|confirm\w*|recommend\w*|should|must|correct\w*|wrong|"
    r"incorrect|error\w*|mistak\w*|likely|probabl\w*|clearly|definitely|proves?|"
    r"approved|decided)\b",
    re.I,
)
# a whole or decimal number; a full stop after it ends the sentence ("POSITIVE: 1. NODES")
_NUMBER = re.compile(r"(?<!\w)(?<!\d\.)\d+(?:\.\d+)?(?!\w|\.\d)")
_CATEGORY = re.compile(r"\b(?:y?p)?([TN](?:X|IS|\d[A-D]?|\dMI))\b", re.I)
_NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty"
).split()
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.I)
_WORD = re.compile(r"[a-z]+")
# Besides the words of the facts it cites, a sentence may only use these: grammar and the
# connecting words honest notes used (logs/case-notes.jsonl). Anything else ("surgery",
# "pathologist", "slip", "amended") is a fact the note made up.
_VOCABULARY = frozenset(
    """a an the and or but so because while whereas also then than that this these those it
    its is are was were be been being has have had of to for with on in at by as from per
    after before both each neither nor not no s which what
    person decides decide final verifies verified verify verifying verification reading reads
    read shows show gives give meaning means mean defined consistent disagree disagrees agree
    agrees contradict contradicts contradiction converts convert turns implies node nodes
    count counts category categories field fields record records recorded report registry
    value values separately against based considering facts element data identify
    review map maps mapped derive derives derived
    do does did where when how using uses used apply applies applied drive drives driven
    identifies identified pathology whether nodal""".split()
)


def _count(value: Any) -> str | None:
    try:
        return f"{float(value):g}" if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_facts(found: dict[str, Any]) -> dict[str, str]:
    """Numbered facts from the USL case record; quotes only from accepted reader values."""
    check = found["check"]
    edition, site = check.get("edition_code"), check.get("site_key")
    facts: dict[str, str] = {}
    recorded = check.get("recorded_n")
    meaning = n_range(recorded, edition, site) if recorded else None
    facts["F1"] = f"The registry records N category {recorded or 'missing'}" + (
        f", which means {meaning}" if meaning else ""
    )
    count, tested = (
        _count(check.get("lymph_nodes_positive")),
        _count(check.get("lymph_nodes_tested")),
    )
    facts["F2"] = f"The registry records {count or 'no'} positive nodes" + (
        f" of {tested} examined" if tested else ""
    )
    if check.get("derived_n"):
        facts["F3"] = f"The count rule turns the registry count into {check['derived_n']}"
    fault = check.get("fault_field")
    if fault:
        facts["F4"] = f"The semantic layer names {FAULT_WORDS.get(fault, fault)}"
    rows = [
        row
        for row in found.get("accepted") or []
        # the audit is N against the node count, so T quotes stay out of the note
        if row.get("field") in ("N", NODES_POSITIVE)
        and row.get("quote")
        and all(c.get("ok") for c in row.get("checks", []))
    ]
    for i, row in enumerate(rows, start=1):
        what = (
            "positive-node count" if row["field"] == NODES_POSITIVE else f"{row['field']} category"
        )
        facts[f"Q{i}"] = (
            f'The report states "{row["quote"]}", read and verified as {what} {row["value"]}'
        )
    return facts


def _tokens(text: str) -> set[str]:
    numbers = {f"{float(n):g}" for n in _NUMBER.findall(text)}
    numbers |= {str(_NUMBER_WORDS.index(w.lower())) for w in _NUMBER_WORD.findall(text)}
    categories = {c.upper() for c in _CATEGORY.findall(text)}
    return numbers | {f"cat:{c}" for c in categories}


def check_note(answer: dict[str, Any] | None, facts: dict[str, str]) -> tuple[list[dict], str]:
    """(sentences, "") when every sentence passes; ([], reason) for the first failure."""
    if answer is None or not isinstance(answer.get("sentences"), list):
        return [], "answer_not_json"
    sentences = answer["sentences"]
    if not 1 <= len(sentences) <= MAX_SENTENCES:
        return [], "sentence_count"
    out = []
    for n, sentence in enumerate(sentences, start=1):
        text = sentence.get("text") if isinstance(sentence, dict) else None
        cites = sentence.get("cites") if isinstance(sentence, dict) else None
        if not isinstance(text, str) or not text.strip() or not isinstance(cites, list):
            return [], f"sentence_{n}_malformed"
        if _ID_IN_TEXT.search(text):
            return [], f"sentence_{n}_fact_id_in_text"
        if len(text.split()) > MAX_WORDS:
            return [], f"sentence_{n}_too_long"
        if not cites or not all(isinstance(c, str) and _CITE.match(c) for c in cites):
            return [], f"sentence_{n}_no_citation"
        unknown = [c for c in cites if c not in facts]
        if unknown:
            return [], f"sentence_{n}_cites_unknown_{unknown[0]}"
        cited = " ".join(facts[c] for c in cites)
        extra = sorted(_tokens(text) - _tokens(cited))
        if extra:
            return [], f"sentence_{n}_states_{extra[0].removeprefix('cat:')}_not_in_cited_facts"
        unknown_words = sorted(
            set(_WORD.findall(text.lower()))
            - set(_WORD.findall(cited.lower()))
            - _VOCABULARY
            - set(_NUMBER_WORDS)
        )
        if unknown_words:
            return [], f"sentence_{n}_word_{unknown_words[0]}_not_in_cited_facts"
        cited_claims = {w.lower() for w in _CLAIM.findall(cited)}
        claims = sorted({w.lower() for w in _CLAIM.findall(text)} - cited_claims)
        if claims:
            return [], f"sentence_{n}_claims_{claims[0]}_not_in_cited_facts"
        out.append({"text": text.strip(), "cites": cites})
    return out, ""


async def write_note(
    found: dict[str, Any], *, chat: Any = None, writer: str = "super"
) -> dict[str, Any]:
    """One note for one case; the result is logged and returned, never stored as evidence.

    writer "ultra": Nemotron Ultra on NVIDIA direct (no Nightshift lane for it), same facts,
    prompt and guard, logged to ULTRA_LOG."""
    case_id = found["check"]["case_id"]
    facts = build_facts(found)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Case {case_id}. Facts:\n"
            + "\n".join(f"{key}: {value}" for key, value in facts.items()),
        },
    ]
    started = time.monotonic()
    if writer == "ultra":
        return await _ultra_note(case_id, facts, messages, started, chat)
    text, receipt = await (chat or nightshift.chat)(
        messages,
        config.NS_SUPER_VL,
        item_id=f"note-{case_id}-{uuid.uuid4().hex[:8]}",
        require_model=config.NS_SUPER_VL,
        retry_on_mismatch=True,
        require_signature=True,
        pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
        allow_cache=False,
        max_tokens=MAX_TOKENS,
        **NOTE_EXTRA,
    )
    seconds = round(time.monotonic() - started, 2)
    sentences, reason = check_note(parse_answer(text), facts)
    result = {
        "case_id": case_id,
        "status": "accepted" if sentences else "rejected",
        "reason": reason,
        "sentences": sentences,
        "facts": facts,
        "provider": "nightshift",
        "receipt": {
            "receipt_id": receipt.receipt_id,
            "model": receipt.winning_model,
            "kind": receipt.winning_kind,
            "egress": receipt.egress_destination,
            "context_sources": receipt.context_sources,
            "signature": receipt.signature,
            "signer": key_fingerprint(receipt.signer_key),
            "from_cache": receipt.from_cache,
            "latency_ms": receipt.latency_ms,
            "usage": receipt.usage,
        },
        "seconds": seconds,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _append(result, text)
    return result


async def _ultra_note(
    case_id: str, facts: dict[str, str], messages: list[dict], started: float, chat: Any
) -> dict[str, Any]:
    text, served, usage = await (chat or nvidia.chat_with_usage)(
        messages, config.NV_ULTRA, max_tokens=MAX_TOKENS
    )
    sentences, reason = check_note(parse_answer(text), facts)
    result = {
        "case_id": case_id,
        "writer": "ultra",
        "status": "accepted" if sentences else "rejected",
        "reason": reason,
        "sentences": sentences,
        "facts": facts,
        "provider": "nvidia direct",
        "model": served,
        "usage": usage,
        "seconds": round(time.monotonic() - started, 2),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _append(result, text, ULTRA_LOG)
    return result


def _append(result: dict[str, Any], raw_text: str, path: Path | None = None) -> None:
    path = path or NOTES_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({**result, "raw_text": raw_text}, ensure_ascii=False) + "\n")


def latest_note(case_id: str) -> dict[str, Any] | None:
    """The newest logged note for a case that passes the CURRENT guard (re-judged from the
    model's raw answer); if none passes, the newest one, shown as rejected with its reason.
    The page never hides a signed answer, and never shows a failing one as passing."""
    if not NOTES_LOG.exists():
        return None
    passing = newest = None
    for line in NOTES_LOG.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("case_id") != case_id or "raw_text" not in row:
            continue
        sentences, reason = check_note(parse_answer(row["raw_text"]), row.get("facts") or {})
        judged = {
            **{k: v for k, v in row.items() if k != "raw_text"},
            "status": "accepted" if not reason else "rejected",
            "reason": reason,
            "sentences": sentences,
            "logged_status": row.get("status"),
        }
        newest = judged
        if not reason:
            passing = judged
    return passing or newest
