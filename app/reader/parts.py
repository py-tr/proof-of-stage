"""Part-aware node count: Nemotron Super lists each specimen part with its own quote; code adds.

Built for the reader's two measured traps (census 2, `docs/evidence/hidden-2-results.md`): a
separately submitted sentinel node left out of the total (5 of the 7 readings that fell), and the
other breast read in a bilateral case (2). Super VL (4k thinking, through Nightshift, pinned,
signed, no cache) returns every specimen part that reports lymph nodes: its side, its role, its
positive count and ONE verbatim quote. It never returns a total of its own. Code then:
- checks each part's quote with the shipped quote rules (`locate`, `count_path`, unchanged);
- drops a part whose side is the other breast, when the registry record's side is known (GDC
  `diagnoses.laterality`, frozen per case in the test's pre-registration);
- takes a total the report states with a label (role "total", on the record's side) when one is
  verified; otherwise one verified part is the count; otherwise the verified parts are added.
A sum is not a value any single quote shows, so under the product's rule (one quote must show the
value) it is "parts_sum": the parts and their quotes are shown and a person decides. Nothing here
is wired into the shipped evidence chain.
"""

from __future__ import annotations

from typing import Any

from app import config
from app.providers import nightshift
from app.reader.quotes import is_too_short, locate
from app.reader.reader import (
    _CONTEXT,
    REPORT_CHARS,
    THINKING_BUDGET,
    _n_from_count,
    count_path,
    parse_answer,
    parse_count,
    report_floor,
    thinking_args,
)

PROMPT = (
    "You read one breast-cancer pathology report and list every specimen part that reports "
    "regional lymph nodes. Do not add anything up.\n"
    'Return ONLY a JSON object: {"parts": [{"label": "...", "side": "left|right|unspecified", '
    '"role": "sentinel|dissection|level|intramammary|total|other", "positive": 0, '
    '"quote": "..."}]}\n'
    "Rules:\n"
    "- One entry per specimen part or per stated count: sentinel node biopsies, axillary "
    "dissections, nodes counted per level, intramammary nodes, and a total the report states for "
    'one breast (role "total"). Include parts with 0 positive nodes.\n'
    '- side: the breast that part belongs to, if the report says; otherwise "unspecified".\n'
    "- positive: that part's number of positive lymph nodes, as an integer.\n"
    "- quote: ONE contiguous passage copied character-for-character from the report that states "
    "that part's positive count (it must contain the number, as digits or a word, or a phrase "
    "such as 'no metastatic carcinoma'). No ellipsis, no paraphrase, no joining.\n"
    "- Never compute or return a total yourself; a total belongs in the list only if the report "
    "writes it."
)
ADDED_ROLES = ("sentinel", "dissection", "level", "intramammary", "other")


def check_part(part: dict[str, Any], report: str) -> dict[str, Any]:
    """One part: its quote must be in the report and show its positive count."""
    out = {
        "label": str(part.get("label") or "")[:80],
        "side": str(part.get("side") or "unspecified").lower(),
        "role": str(part.get("role") or "other").lower(),
        "positive": parse_count(part.get("positive")),
        "quote": part.get("quote") if isinstance(part.get("quote"), str) else None,
    }
    if out["positive"] is None:
        return {**out, "verified": False, "reason": "invalid_count"}
    if is_too_short(out["quote"]):
        return {**out, "verified": False, "reason": "quote_too_short"}
    span = locate(out["quote"], report)
    if span is None:
        return {**out, "verified": False, "reason": "quote_not_in_report"}
    before = report[max(0, span.start - _CONTEXT) : span.start]
    after = report[span.end : span.end + _CONTEXT]
    if count_path(out["positive"], span.text(report), before, after) is None:
        return {**out, "verified": False, "reason": "count_not_in_quote"}
    return {**out, "quote": span.text(report), "verified": True, "reason": ""}


def resolve(parts: list[dict[str, Any]], report: str, side: str | None) -> dict[str, Any]:
    """The count from the verified parts on the record's side, and how it was reached."""
    side = (side or "").lower() or None
    checked = [check_part(p, report) for p in parts if isinstance(p, dict)]
    usable = [
        p
        for p in checked
        if p["verified"] and not (side and p["side"] in ("left", "right") and p["side"] != side)
    ]
    dropped_other_side = sum(
        p["verified"] and bool(side) and p["side"] in ("left", "right") and p["side"] != side
        for p in checked
    )
    totals = {p["positive"] for p in usable if p["role"] == "total"}
    added = [p for p in usable if p["role"] in ADDED_ROLES]
    if len(totals) == 1:
        count, how = totals.pop(), "stated_total"
    elif len(totals) > 1:
        count, how = None, "totals_disagree"
    elif len(added) == 1:
        count, how = added[0]["positive"], "single_part"
    elif added:
        count, how = sum(p["positive"] for p in added), "parts_sum"
    else:
        count, how = None, "no_verified_part"
    two_sided = len({p["side"] for p in checked if p["side"] in ("left", "right")}) > 1
    if two_sided and not side and count is not None:
        count, how = None, "two_sides_no_record_side"
    floor = report_floor(report)
    below_floor = count is not None and floor is not None and count < floor and how != "parts_sum"
    return {
        "count": count,
        "how": how,
        "n_by_rule": _n_from_count(count) if count is not None else None,
        "accepted_one_quote": how in ("stated_total", "single_part") and not below_floor,
        "below_floor": below_floor,
        "dropped_other_side": dropped_other_side,
        "parts": checked,
    }


async def read_parts(case_id: str, report: str, side: str | None, item_id: str) -> dict[str, Any]:
    extra, max_tokens = thinking_args(THINKING_BUDGET)
    text, receipt = await nightshift.chat(
        [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
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
    parts = answer.get("parts") if isinstance(answer.get("parts"), list) else []
    return {
        "case": case_id,
        "receipt_id": receipt.receipt_id,
        "signature": receipt.signature,
        "tokens": (receipt.usage or {}).get("completion_tokens") or 0,
        **resolve(parts, report, side),
    }
