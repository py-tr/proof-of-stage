"""Read one pathology report with Nemotron Super and verify every answer.

Super answers T and N directly, each with ONE verbatim quote and the reason it
applied, plus the number of positive regional nodes with its own quote. Code then
(1) parses the JSON, (2) normalises the category, (3) locates the quote in the report;
for the node count, (4) the number itself must appear inside the located span. A field
is ACCEPTED only when every check succeeds; otherwise it is REJECTED with a reason and
goes to the human review queue. The model never writes a value the report does not
visibly support.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from app import config
from app.providers import nightshift, nvidia
from app.reader.quotes import Span, is_too_short, locate

Provider = Literal["nvidia", "nightshift"]
Field = Literal["T", "N"]
FIELDS: tuple[Field, ...] = ("T", "N")
NODES_POSITIVE = "NPOS"  # field name of the positive-node count

METHOD = "nemotron_reader"
THINKING_BUDGET = 4000  # measured: same answers as unlimited thinking, bounded cost
THINKING_OFF = 0  # the fast rung: ~19 completion tokens per answer (measured)
REPORT_CHARS = 32000  # only 3 of 1,034 reports exceed 24,000 chars (max 26,162)

SYSTEM_PROMPT = (
    "You read one breast cancer pathology report and report the PATHOLOGIC T and N "
    "categories (AJCC), as the report supports them.\n"
    "Return ONLY a JSON object with these keys:\n"
    '{"T": "...", "T_quote": "...", "T_reason": "...", '
    '"N": "...", "N_quote": "...", "N_reason": "...", '
    '"N_positive": 0, "N_positive_quote": "..."}\n'
    "Rules:\n"
    "- T is one of TX, T0, Tis, T1mi, T1a, T1b, T1c, T1, T2, T3, T4a, T4b, T4c, T4d, T4; "
    "N is one of NX, N0, N0(i+), N1mi, N1a, N1b, N1c, N1, N2a, N2b, N2, N3a, N3b, N3c, N3.\n"
    "- T_quote / N_quote: ONE contiguous passage copied character-for-character from the "
    "report: the shortest passage that supports your category, at least a few words "
    "(not a bare code like 'pNx'). No ellipsis, no "
    "paraphrase, no joining of separate passages.\n"
    "- T_reason / N_reason: one short sentence on which rule you applied "
    "(e.g. largest invasive focus 2.4 cm -> T2; 2 of 14 axillary nodes positive -> N1a).\n"
    "- N_positive: the total number of positive regional lymph nodes as an integer; "
    "N_positive_quote: the passage that states it (it must contain that number). "
    "Use null with an empty quote if the report does not state a count.\n"
    '- If the report does not support a category, use "UNKNOWN" with an empty quote. '
    "Never guess."
)

_T_RE = re.compile(r"^T(?:X|0|IS|1MIC?|1[ABC]?|2|3|4[ABCD]?)$")
_N_RE = re.compile(r"^N(?:X|0(?:\((?:I|MOL)[+-]\))?|1MI|1[ABC]?|2[AB]?|3[ABC]?)$")
_NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()
_MAX_NODES = 99
REASON_CHARS = 250  # fits derived_stage.value
_NUMBER = r"(\d+|[a-z]+)"
# "2/14", "2 of 14", "two of fourteen", "2 out of 14": the first number is the positive count.
_FRACTION = re.compile(rf"(?<![\d.]){_NUMBER}\s*(?:/|\bof\b|\bout of\b)\s*{_NUMBER}", re.I)
# "no"/"none" mean zero only when they are about nodes or metastasis.
_ZERO = re.compile(r"\b(?:no|none)\b(?:\W+\w+){0,3}?\W+(?:nodes?|lymph|metasta\w*)", re.I)


@dataclass
class FieldResult:
    field: str
    status: Literal["accepted", "rejected", "abstained"]
    value: str | None = None
    quote: str | None = None
    span: Span | None = None
    reason: str = ""  # the model's reason when accepted, else the rejection code


@dataclass
class ReadResult:
    case_id: str
    model: str
    receipt_id: str | None
    provider: Provider
    fields: dict[str, FieldResult] = field(default_factory=dict)
    raw_text: str = ""
    budget: int = THINKING_BUDGET
    usage: dict[str, Any] = field(default_factory=dict)
    from_cache: bool | None = None
    signature: str = "absent"


def normalise_category(field_name: Field, value: Any) -> str | None:
    """'pT2' / 'ypN1a' / 'n0 (i+)' -> 'T2' / 'N1A' / 'N0(I+)'; None if not a valid category."""
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", "", value.strip().upper())
    text = re.sub(r"^(?:YP|P|C)", "", text)
    pattern = _T_RE if field_name == "T" else _N_RE
    return text if pattern.match(text) else None


def parse_answer(text: str) -> dict[str, Any] | None:
    """First JSON object in the model's text (tolerates code fences and prose around it)."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def judge_field(field_name: Field, answer: dict[str, Any] | None, report: str) -> FieldResult:
    if answer is None:
        return FieldResult(field_name, "rejected", reason="answer_not_json")
    raw_value = answer.get(field_name)
    quote = answer.get(f"{field_name}_quote")
    quote = quote if isinstance(quote, str) else None
    if isinstance(raw_value, str) and raw_value.strip().upper() == "UNKNOWN":
        return FieldResult(field_name, "abstained", quote=quote, reason="model_abstained")
    value = normalise_category(field_name, raw_value)
    if value is None:
        return FieldResult(field_name, "rejected", quote=quote, reason="invalid_category")
    if is_too_short(quote):
        return FieldResult(
            field_name, "rejected", value=value, quote=quote, reason="quote_too_short"
        )
    span = locate(quote, report)
    if span is None:
        return FieldResult(
            field_name, "rejected", value=value, quote=quote, reason="quote_not_in_report"
        )
    return FieldResult(
        field_name,
        "accepted",
        value=value,
        quote=span.text(report),
        span=span,
        reason=str(answer.get(f"{field_name}_reason") or "")[:REASON_CHARS],
    )


def parse_count(value: Any) -> int | None:
    """An integer node count 0..99 (accepts 3, 3.0 and "3"); None otherwise."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    return value if isinstance(value, int) and 0 <= value <= _MAX_NODES else None


def _as_number(token: str) -> int | None:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.index(token) if token in _NUMBER_WORDS else None


def count_in_span(count: int, span_text: str) -> bool:
    """The count is written inside the span as the positive number.

    If the span holds a fraction ("2/14", "two of fourteen"), the count must be its first
    number, so the tested count cannot pass as the positive count. Otherwise the count must
    appear as a whole number (not part of "2.4" or "14") or, up to twenty, as a word; zero
    may also be "no"/"none" followed closely by nodes/lymph/metastasis. Known limit: a bare
    number elsewhere in the span (a date, a size in mm) can still match.
    """
    numerators = []
    for match in _FRACTION.finditer(span_text):
        top, bottom = _as_number(match.group(1)), _as_number(match.group(2))
        if top is not None and bottom is not None:
            numerators.append(top)
    if numerators:
        return count in numerators
    if re.search(rf"(?<![\d.]){count}(?!\d|\.\d)", span_text):
        return True
    if count < len(_NUMBER_WORDS) and re.search(
        rf"\b{_NUMBER_WORDS[count]}\b", span_text, re.IGNORECASE
    ):
        return True
    return count == 0 and _ZERO.search(span_text) is not None


def judge_count(answer: dict[str, Any] | None, report: str) -> FieldResult:
    name = NODES_POSITIVE
    if answer is None:
        return FieldResult(name, "rejected", reason="answer_not_json")
    raw = answer.get("N_positive")
    quote = answer.get("N_positive_quote")
    quote = quote if isinstance(quote, str) else None
    if raw is None or (isinstance(raw, str) and raw.strip().upper() in ("", "UNKNOWN", "NULL")):
        return FieldResult(name, "abstained", quote=quote, reason="model_abstained")
    count = parse_count(raw)
    if count is None:
        return FieldResult(name, "rejected", quote=quote, reason="invalid_count")
    value = str(count)
    if is_too_short(quote):
        return FieldResult(name, "rejected", value=value, quote=quote, reason="quote_too_short")
    span = locate(quote, report)
    if span is None:
        return FieldResult(name, "rejected", value=value, quote=quote, reason="quote_not_in_report")
    if not count_in_span(count, span.text(report)):
        return FieldResult(
            name, "rejected", value=value, quote=span.text(report), reason="count_not_in_quote"
        )
    return FieldResult(name, "accepted", value=value, quote=span.text(report), span=span)


def thinking_args(budget: int) -> tuple[dict[str, Any], int]:
    """(extra request args, max_tokens) for a thinking budget; 0 turns thinking off."""
    if budget <= THINKING_OFF:
        return {"chat_template_kwargs": {"enable_thinking": False}}, 1500
    kwargs = {"enable_thinking": True, "reasoning_budget": budget}
    return {"chat_template_kwargs": kwargs}, budget + 3000


async def read_report(
    case_id: str,
    report: str,
    *,
    provider: Provider = "nvidia",
    budget: int = THINKING_BUDGET,
    run_id: str | None = None,
) -> ReadResult:
    """One read. Through Nightshift the model is pinned to Super VL (a substituted model is
    retried, then refused), the receipt signature must verify, and a cached answer is refused.
    `run_id` makes the item id unique per run (never reuse an item id across runs)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
    ]
    extra, max_tokens = thinking_args(budget)
    usage: dict[str, Any] = {}
    from_cache: bool | None = None
    signature = "absent"
    if provider == "nightshift":
        run = run_id or uuid.uuid4().hex[:8]
        text, receipt = await nightshift.chat(
            messages,
            config.NS_SUPER_VL,
            item_id=f"read-{case_id}-{run}-b{budget}",
            require_model=config.NS_SUPER_VL,
            retry_on_mismatch=True,
            require_signature=True,
            pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
            allow_cache=False,
            max_tokens=max_tokens,
            **extra,
        )
        model, receipt_id = receipt.winning_model or "", receipt.receipt_id
        usage, from_cache, signature = receipt.usage, receipt.from_cache, receipt.signature
    else:
        text, model = await nvidia.chat(messages, config.NV_SUPER, max_tokens=max_tokens, **extra)
        receipt_id = None
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id,
        model=model,
        receipt_id=receipt_id,
        provider=provider,
        raw_text=text,
        budget=budget,
        usage=usage,
        from_cache=from_cache,
        signature=signature,
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)
    result.fields[NODES_POSITIVE] = judge_count(answer, report)
    return result
