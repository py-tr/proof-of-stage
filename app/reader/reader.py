"""Read one pathology report with Nemotron Super and verify every answer.

Super answers T and N directly, each with ONE verbatim quote and the reason it
applied. Code then (1) parses the JSON, (2) normalises the category, (3) locates the
quote in the report. A field is ACCEPTED only when all three succeed; otherwise it is
REJECTED with a reason and goes to the human review queue. The model never writes a
value the report does not visibly support.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app import config
from app.providers import nightshift, nvidia
from app.reader.quotes import Span, is_too_short, locate

Provider = Literal["nvidia", "nightshift"]
Field = Literal["T", "N"]
FIELDS: tuple[Field, ...] = ("T", "N")

METHOD = "nemotron_reader"
THINKING_BUDGET = 4000  # measured: same answers as unlimited thinking, bounded cost

SYSTEM_PROMPT = (
    "You read one breast cancer pathology report and report the PATHOLOGIC T and N "
    "categories (AJCC), as the report supports them.\n"
    "Return ONLY a JSON object with these keys:\n"
    '{"T": "...", "T_quote": "...", "T_reason": "...", '
    '"N": "...", "N_quote": "...", "N_reason": "..."}\n'
    "Rules:\n"
    "- T is one of TX, T0, Tis, T1mi, T1a, T1b, T1c, T1, T2, T3, T4a, T4b, T4c, T4d, T4; "
    "N is one of NX, N0, N0(i+), N1mi, N1a, N1b, N1c, N1, N2a, N2b, N2, N3a, N3b, N3c, N3.\n"
    "- T_quote / N_quote: ONE contiguous passage copied character-for-character from the "
    "report: the shortest passage that supports your category, at least a few words "
    "(not a bare code like 'pNx'). No ellipsis, no "
    "paraphrase, no joining of separate passages.\n"
    "- T_reason / N_reason: one short sentence on which rule you applied "
    "(e.g. largest invasive focus 2.4 cm -> T2; 2 of 14 axillary nodes positive -> N1a).\n"
    '- If the report does not support a category, use "UNKNOWN" with an empty quote. '
    "Never guess."
)

_T_RE = re.compile(r"^T(?:X|0|IS|1MIC?|1[ABC]?|2|3|4[ABCD]?)$")
_N_RE = re.compile(r"^N(?:X|0(?:\((?:I|MOL)[+-]\))?|1MI|1[ABC]?|2[AB]?|3[ABC]?)$")


@dataclass
class FieldResult:
    field: Field
    status: Literal["accepted", "rejected", "abstained"]
    value: str | None = None
    quote: str | None = None
    span: Span | None = None
    reason: str = ""


@dataclass
class ReadResult:
    case_id: str
    model: str
    receipt_id: str | None
    provider: Provider
    fields: dict[str, FieldResult] = field(default_factory=dict)
    raw_text: str = ""


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
        reason=str(answer.get(f"{field_name}_reason") or "")[:300],
    )


async def read_report(case_id: str, report: str, *, provider: Provider = "nvidia") -> ReadResult:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Pathology report:\n\n" + report[:24000]},
    ]
    thinking = {
        "chat_template_kwargs": {"enable_thinking": True, "reasoning_budget": THINKING_BUDGET}
    }
    if provider == "nightshift":
        text, receipt = await nightshift.chat(
            messages,
            config.NS_SUPER_VL,
            item_id=f"read-{case_id}",
            max_tokens=THINKING_BUDGET + 3000,
            **thinking,
        )
        model, receipt_id = receipt.winning_model or "", receipt.receipt_id
    else:
        text, model = await nvidia.chat(
            messages, config.NV_SUPER, max_tokens=THINKING_BUDGET + 3000, **thinking
        )
        receipt_id = None
    answer = parse_answer(text)
    result = ReadResult(
        case_id=case_id, model=model, receipt_id=receipt_id, provider=provider, raw_text=text
    )
    for name in FIELDS:
        result.fields[name] = judge_field(name, answer, report)
    return result
