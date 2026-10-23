"""Read one pathology report with Nemotron Super and verify every answer.

Super answers T and N directly, each with ONE verbatim quote and the reason it
applied, plus the number of positive regional nodes with its own quote. Code then
(1) parses the JSON, (2) normalises the category, (3) locates the quote in the report;
for the node count, (4) the number itself must appear inside the located span and (5) it
may not be below any node fraction the report states (one specimen's count is not the
total). A field
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
# A fraction is about lymph nodes when the word "node(s)" is written this close to it
# (not "lymph": "lymphovascular" and "lymphoplasmacytic" sit beside grade scores like 8/9).
_NODE_WORD = re.compile(r"\bnodes?\b", re.I)
_NODE_WINDOW = 60
# "Eight of eight sentinel lymph nodes, free of metastatic carcinoma" counts examined nodes,
# not positive ones: a negative word this soon after a fraction drops it from the floor.
_NEGATIVE_AFTER = re.compile(
    r"\b(?:free|negative|benign|without|no\s+(?:evidence|tumou?r|metasta|carcinoma))", re.I
)
_NEGATIVE_WINDOW = 50
# Grades and scores ("Grade 2/3", "Nottingham score 8/9") are not node fractions.
_SCORE_BEFORE = re.compile(
    r"\b(?:grade|score|nottingham|tubules?|tubule formation|mitos[ei]s|mitotic|nuclear|"
    r"pleomorphism|her-?2|allred)[^\w;.]*(?:\w+[^\w;.]+){0,2}$",
    re.I,
)
_SCORE_WINDOW = 30
# "no"/"none" mean zero only when they are about nodes or metastasis ("lymph" alone is
# not enough: "No lymphovascular invasion" says nothing about nodes).
_ZERO = re.compile(
    r"\b(?:no|none)\b(?:\W+\w+){0,3}?\W+(?:nodes?\b|lymph\s+nodes?\b|metasta\w*)", re.I
)
_ZERO_NEGATIVE = re.compile(r"\b(?:negative|free of|benign)\b", re.I)
# Without a fraction, the count is the number written nearest a positive-node cue.
_TOKEN = re.compile(r"(?<![\w.])(\d+|[a-z]+)(\.\d+)?(?!\w)", re.I)
_POSITIVE_CUE = re.compile(
    r"\b(?:positive|metasta\w*|macrometasta\w*|micrometasta\w*|involv\w*|carcinoma|"
    r"tumou?r\s+(?:deposits?|cells))",
    re.I,
)
_NEGATED_CUE = re.compile(
    r"\b(?:no|not|free of|negative for|without|absence of)\b[^.;:]{0,25}$", re.I
)
# Not a node count: a measurement or duration after it, or "examined"/"size" just before.
_UNIT_AFTER = re.compile(
    r"^\s*(?:mm|cm|%|percent|months?|years?|yrs?|weeks?|days?|hours?|hrs?|x\b|-\s*\d|to\s+\d)",
    re.I,
)
_NOT_POSITIVE_BEFORE = re.compile(
    r"\b(?:examined|tested|total\s+(?:lymph\s+)?nodes?|received|retrieved|size|grade|score|"
    r"block|slide|measur\w*|age|cassettes?)\W{0,3}$",
    re.I,
)
# "NUCLEAR GRADE: COMPONENT: 3": a grade a few words back, in the same sentence.
_GRADE_BEFORE = re.compile(
    r"\b(?:grade|sbr|bloom|richardson|elston|nottingham)\b[^.;]{0,25}$", re.I
)
# "two contiguous sections", "3 blocks", "two cores": the number counts something else.
_OTHER_NOUN_AFTER = re.compile(
    r"^\W{0,2}(?:\w+\W+){0,2}?(?:sections?|slides?|blocks?|cores?|fragments?|pieces?|foci|"
    r"focus|levels?|cassettes?|specimens?|parts?|quadrants?|margins?|samples?|stains?|views?|"
    r"images?|cm|mm)\b",
    re.I,
)
# "3. Excisional biopsy margins": a list index, not a count (but "POSITIVE: 1." counts).
_INDEX_BEFORE = re.compile(r"(?:^|[.;]\s*|\s-\s*)$")
_INDEX_AFTER = re.compile(r"^\.\s+[A-Za-z]")
_CONTEXT = 30  # report characters read on each side of a quote for units and labels
_VALUE = r"(\d+|[a-z]+)"
# A total the report states with a label ("Number of positive lymph nodes: 4", "Total number
# with metastasis: 7", "POSITIVE LYMPH NODES: TOTAL: 4 of 13", "LYMPH NODES POSITIVE: 1").
# Macrometastasis counts are not totals (micrometastases are positive nodes too).
_TOTAL_LABEL = re.compile(
    r"(?:number of (?:positive|involved) (?:lymph )?nodes?"
    r"|number of (?:lymph )?nodes? (?:positive|involved|with (?:metasta\w*|carcinoma))"
    r"|total (?:number )?(?:of )?(?:positive (?:lymph )?nodes?|(?:lymph )?nodes? positive"
    r"|(?:number )?with metasta\w*)"
    r"|positive (?:lymph )?nodes?\W{0,3}total"
    rf"|\blymph nodes? positive)\W{{0,4}}{_VALUE}\b",
    re.I,
)


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
    if not supports_category(field_name, value, span.text(report), report, span.start):
        return FieldResult(
            field_name,
            "rejected",
            value=value,
            quote=span.text(report),
            reason="quote_does_not_support",
        )
    return FieldResult(
        field_name,
        "accepted",
        value=value,
        quote=span.text(report),
        span=span,
        reason=str(answer.get(f"{field_name}_reason") or "")[:REASON_CHARS],
    )


# A stage token in the quote: "pN1a", "N1A", "pT2N1aMX" (T2 and N1A), "ypN0(i+)".
_STAGE_TOKEN = {
    "T": re.compile(r"(?<![A-Za-z])(?:y?p|c)?T\s?(IS|X|[0-4])(?:\s?(MI|[A-D]))?(?![0-9])", re.I),
    "N": re.compile(r"(?<![A-Za-z])(?:y?p|c)?N\s?(X|[0-3])(?:\s?(MI|[A-C]))?(?![0-9])", re.I),
}
# "N Stage: 1a", "pN: 1A", "T category: T2", "Primary tumor (pT): 2".
_STAGE_LABEL = {
    "T": re.compile(
        r"\b(?:y?p)?T\s*(?:stage|category|\(p?T\))?\s*[:=]\s*(?:y?p?T)?\s*(IS|X|[0-4])", re.I
    ),
    "N": re.compile(
        r"\b(?:y?p)?N\s*(?:stage|category|\(p?N\))?\s*[:=]\s*(?:y?p?N)?\s*(X|[0-3])", re.I
    ),
}
# "2.4 cm", "4.1 x 3.5 x 1.5 cm" (the largest dimension counts), "18 mm".
_DIMENSION = r"\d+(?:\.\d+)?"
_SIZE = re.compile(
    rf"(?<![\w.])((?:{_DIMENSION}\s*(?:x|×|by)\s*)*{_DIMENSION})\s*-?\s*(cm|mm)\b", re.I
)  # also "1.2-CM"
# Categories a count or size cannot show, with the words that can.
_NEGATED_BEFORE = re.compile(
    r"\b(?:no|not|negative for|free of|without|absence of|absent)\b[^.;]{0,30}$", re.I
)
_NEGATED_AFTER = re.compile(
    r"^[^.;]{0,25}\b(?:not (?:identified|present|involved|seen)|none|absent|negative)\b", re.I
)
# Categories a count or size cannot show, with the words that can. Each match must not be
# negated, and must be about the right element (see `_category_words_show`).
_CATEGORY_WORDS = {
    "N1MI": re.compile(r"micro-?\s?metasta\w*", re.I),
    "N0(I+)": re.compile(r"isolated\s+tumou?r\s+cells?|\bITCs?\b|\(i\+\)", re.I),
    "NX": re.compile(
        r"cannot be assessed|not assessed|without axillary|no axillary"
        r"|no (?:lymph )?nodes? (?:were )?(?:submitted|received|identified|sampled)"
        r"|examined\W{0,3}0\b|\b0\s+(?:lymph\s+)?nodes?\s+examined",
        re.I,
    ),
    "TX": re.compile(r"cannot be assessed|not assessed", re.I),
    "TIS": re.compile(r"\bin[- ]situ\b", re.I),
    "T4": re.compile(
        r"(?:invad\w*|involv\w*|infiltrat\w*|extend\w*|extension|ulcerat\w*)[^.;]{0,30}"
        r"\b(?:skin|dermis|epidermis|chest wall)\b"
        r"|\b(?:skin|dermis|epidermis|chest wall)\b[^.;]{0,20}"
        r"(?:invad\w*|involv\w*|infiltrat\w*|ulcerat\w*)"
        r"|satellite (?:skin )?nodules?|inflammatory (?:breast )?carcinoma|peau d",
        re.I,
    ),
}
# A word about these categories is deliberately one of the negating or assessing kind
# itself ("cannot be assessed", "no axillary"), so the general negation check skips them.
_SELF_NEGATING = frozenset({"NX", "TX"})
# "cannot be assessed" belongs to the element named just before it.
_ELEMENT_NODES = re.compile(r"\bp?N\b|regional|lymph|nodes?|axilla", re.I)
_ELEMENT_OTHER = {
    "NX": re.compile(r"\bp?[MT]\b|distant|primary tumou?r|\(p[MT]\)", re.I),
    "TX": re.compile(r"\bp?[MN]\b|distant|lymph|nodes?|\(p[MN]\)", re.I),
}
_ELEMENT_TUMOUR = re.compile(r"\bp?T\b|primary tumou?r", re.I)
_INVASIVE = re.compile(r"\binvasive|infiltrat\w*|micro-?invas", re.I)
# A size shows T only after a tumour cue, with nothing between that names something else.
_TUMOUR_CUE = re.compile(
    r"\b(?:invasive|carcinoma|tumou?r|mass|focus|foci|lesion|neoplasm|largest)\b", re.I
)
_NOT_TUMOUR = re.compile(
    r"\b(?:lymph|nodes?|margins?|specimen|away|distance|from|ellipse|nipple|skin|biopsy|"
    r"cavity|clip|fat|tissue)\b",
    re.I,
)
_SIZE_WINDOW = 60


def _main(category: str) -> str:
    """'N1A' -> 'N1', 'T1MI' -> 'T1', 'N0(I+)' -> 'N0', 'TIS' -> 'TIS'."""
    match = re.match(r"([TN](?:IS|X|\d))", category.upper())
    return match.group(1) if match else category.upper()


def _n_from_count(count: int) -> str:
    return "N0" if count == 0 else "N1" if count <= 3 else "N2" if count <= 9 else "N3"


def _t_from_size(cm: float) -> str:
    return "T1" if cm <= 2.0 else "T2" if cm <= 5.0 else "T3"


def _category_words_show(key: str, span_text: str, before: str, after: str) -> bool:
    """A category word in the quote, not negated, about the right element."""
    words = _CATEGORY_WORDS[key]
    context = before + span_text
    for match in words.finditer(span_text):
        lead = context[: len(before) + match.start()][-40:]
        trail = span_text[match.end() :] + after
        if key not in _SELF_NEGATING and (
            _NEGATED_BEFORE.search(lead) or _NEGATED_AFTER.search(trail)
        ):
            continue
        if key in _ELEMENT_OTHER and match.group(0).lower().endswith("assessed"):
            near = lead[-30:] + match.group(0)
            element = _ELEMENT_NODES if key == "NX" else _ELEMENT_TUMOUR
            if _ELEMENT_OTHER[key].search(near) or not element.search(near):
                continue
        if key == "TIS" and _INVASIVE.search(span_text):
            continue
        return True
    return False


def _tumour_sizes(span_text: str, before: str) -> list[float]:
    """Sizes in cm that follow a tumour cue in the quote (or just before it)."""
    context = before + span_text
    sizes = []
    for match in _SIZE.finditer(span_text):
        at = len(before) + match.start()
        window = context[max(0, at - _SIZE_WINDOW) : at]
        cues = list(_TUMOUR_CUE.finditer(window))
        if not cues or _NOT_TUMOUR.search(window[cues[-1].end() :]):
            continue
        largest = max(float(d) for d in re.findall(_DIMENSION, match.group(1)))
        sizes.append(largest / (10 if match.group(2).lower() == "mm" else 1))
    return sizes


def supports_category(
    field_name: str, value: str, span_text: str, report: str | None = None, start: int = 0
) -> bool:
    """The located quote shows the category, not just that it exists in the report.

    Accepted when the quote holds a stage token or label with the same main category
    ("pN1a" or "N Stage: 1a" for N1A); for N, a node count that passes the whole count
    guard (the context around the quote, the report's fraction floor and labelled total)
    and implies it (2 positive nodes -> N1); for T, a tumour size in its range, after a
    tumour cue (the largest invasive focus 2.4 cm -> T2; not a node, margin or specimen
    size); for the categories a number cannot show, their words, not negated and about the
    right element (micrometastasis -> N1mi, isolated tumour cells -> N0(i+), nodes "cannot
    be assessed" -> NX, skin or chest-wall invasion -> T4, in situ without invasion -> Tis).
    Precision is checked on the main category (N1 vs N1A). `report` and `start` give the
    report around the quote; without them only the quote is read.
    """
    end = start + len(span_text)
    before = report[max(0, start - _CONTEXT) : start] if report else ""
    after = report[end : end + _CONTEXT] if report else ""
    want = _main(value)
    upper = value.upper()
    for key in _CATEGORY_WORDS:
        if (upper == key or want == key) and _category_words_show(key, span_text, before, after):
            return True
    found = {
        _main(f"{field_name}{m.group(1)}") for m in _STAGE_TOKEN[field_name].finditer(span_text)
    }
    found |= {
        _main(f"{field_name}{m.group(1)}") for m in _STAGE_LABEL[field_name].finditer(span_text)
    }
    if want in found:
        return True
    if field_name == "N":
        floor = report_floor(report) if report else None
        totals = report_totals(report) if report else set()
        return any(
            _n_from_count(count) == want
            for count in range(_MAX_NODES + 1)
            if count_path(count, span_text, before, after) is not None
            and (floor is None or count >= floor)
            and (not totals or count in totals)
        )
    return any(_t_from_size(cm) == want for cm in _tumour_sizes(span_text, before))


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

    If the span holds a fraction ("2/14", "two of fourteen"), the count must be the first
    number of a positive one: a fraction of negative nodes ("eight of eight ..., free of
    metastatic carcinoma") states zero positives, and a score ("Nottingham 8/9") is ignored.
    Otherwise the count must be the number (digits, or a word up to twenty) written nearest a
    positive cue that is not negated ("positive", "metastatic", "involving", "carcinoma"):
    "two lymph nodes, one of which contains metastatic carcinoma" states 1, not 2. A number
    with a unit after it (mm, %, months) or "examined"/"size" just before it never counts.
    Zero may also be "no"/"none" closely followed by nodes or metastasis, or a negative word
    in a span about nodes. Known limits: a count above every stated fraction, and a
    per-specimen count when no fraction states the total (the report floor catches the rest).
    """
    return count_path(count, span_text) is not None


def count_path(count: int, span_text: str, before: str = "", after: str = "") -> str | None:
    """Which rule of `count_in_span` finds the count in the span: "fraction",
    "negative_fraction", "zero_phrase" or "cued"; None when no rule does. `before` and
    `after` are the report text around the quote: a unit or a grade just outside it
    ("PRESENT, 4" + " MM") still disqualifies a number."""
    positive, negative = [], False
    full_after = span_text + after  # the report continues past the quote ("AE 1/3" NEGATIVE)
    for match in _FRACTION.finditer(span_text):
        top, bottom = _as_number(match.group(1)), _as_number(match.group(2))
        if top is None or bottom is None or top > bottom:
            continue
        lead = (before + span_text)[: len(before) + match.start()][-_SCORE_WINDOW:]
        if _SCORE_BEFORE.search(lead):
            continue
        trail = full_after[match.end() : match.end() + _NEGATIVE_WINDOW]
        if _NEGATIVE_AFTER.search(re.split(r"[.;]", trail)[0]):
            negative = True
        else:
            positive.append(top)
    if positive:
        return "fraction" if count in positive else None
    if negative:
        return "negative_fraction" if count == 0 else None
    if count == 0 and (
        _ZERO.search(span_text)
        or (_ZERO_NEGATIVE.search(span_text) and _NODE_WORD.search(span_text))
    ):
        return "zero_phrase"
    return "cued" if count in _cued_counts(span_text, before, after) else None


def _cued_counts(span_text: str, before_text: str = "", after_text: str = "") -> set[int]:
    """For each positive cue that is not negated, the value of the nearest number."""
    full, offset = before_text + span_text + after_text, len(before_text)
    numbers = []
    for match in _TOKEN.finditer(span_text):
        value = None if match.group(2) else _as_number(match.group(1))
        if value is None:
            continue
        start, end = offset + match.start(), offset + match.end()
        after = full[end : end + 12]
        before = full[max(0, start - 30) : start]
        if (
            _UNIT_AFTER.search(after)
            or _NOT_POSITIVE_BEFORE.search(before)
            or _GRADE_BEFORE.search(before)
            or _OTHER_NOUN_AFTER.search(full[end : end + 40])
            or (_INDEX_AFTER.search(after) and _INDEX_BEFORE.search(before))
        ):
            continue
        numbers.append((match.start(), match.end(), value))
    cued = set()
    for cue in _POSITIVE_CUE.finditer(span_text):
        if _NEGATED_CUE.search(span_text[max(0, cue.start() - 40) : cue.start()]):
            continue

        def gap(number: tuple[int, int, int], cue: re.Match[str] = cue) -> int:
            start, end, _ = number
            return cue.start() - end if end <= cue.start() else start - cue.end()

        if numbers:
            cued.add(min(numbers, key=gap)[2])
    return cued


def report_floor(report: str) -> int | None:
    """The fewest positive nodes the report's own node fractions allow; None if it states none.

    Every node fraction ("2/18 lymph nodes", "one of two nodes") counts positive nodes in all
    or part of the dissection, so the total is at least its first number. A quote about one
    specimen ("ONE (1) SENTINEL LYMPH NODE: POSITIVE" in a 2/18 report) then cannot pass as
    the total. Only a floor: a positive node stated without a fraction ("one of which
    contains carcinoma") can make the true total higher than every fraction.
    """
    tops = []
    for match in _FRACTION.finditer(report):
        top, bottom = _as_number(match.group(1)), _as_number(match.group(2))
        if top is None or bottom is None or not 0 <= top <= bottom <= _MAX_NODES:
            continue
        window = report[max(0, match.start() - _NODE_WINDOW) : match.end() + _NODE_WINDOW]
        after = report[match.end() : match.end() + _NEGATIVE_WINDOW]
        before = report[max(0, match.start() - _SCORE_WINDOW) : match.start()]
        if (
            _NODE_WORD.search(window)
            and not _NEGATIVE_AFTER.search(after)
            and not _SCORE_BEFORE.search(before)
        ):
            tops.append(top)
    return max(tops) if tops else None


def report_totals(report: str) -> set[int]:
    """Every positive-node total the report states with a label; empty if it states none."""
    totals = set()
    for match in _TOTAL_LABEL.finditer(report):
        value = _as_number(match.group(1))
        if value is not None and value <= _MAX_NODES:
            totals.add(value)
    return totals


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
    before = report[max(0, span.start - _CONTEXT) : span.start]
    after = report[span.end : span.end + _CONTEXT]
    if count_path(count, span.text(report), before, after) is None:
        return FieldResult(
            name, "rejected", value=value, quote=span.text(report), reason="count_not_in_quote"
        )
    floor = report_floor(report)
    if floor is not None and count < floor:
        return FieldResult(
            name, "rejected", value=value, quote=span.text(report), reason="count_below_report"
        )
    totals = report_totals(report)
    if totals and count not in totals:
        return FieldResult(
            name, "rejected", value=value, quote=span.text(report), reason="count_not_report_total"
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
    model: str | None = None,
) -> ReadResult:
    """One read. Through Nightshift the model (Super VL unless `model` names another cloud
    Nemotron) is pinned in the receipt (a substituted model is retried, then refused), the
    receipt signature must verify, and a cached answer is refused.
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
        pinned = model or config.NS_SUPER_VL
        text, receipt = await nightshift.chat(
            messages,
            pinned,
            item_id=f"read-{case_id}-{run}-b{budget}",
            require_model=pinned,
            require_kind="cloud",
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
        text, model, usage = await nvidia.chat_with_usage(
            messages, model or config.NV_SUPER, max_tokens=max_tokens, **extra
        )
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
