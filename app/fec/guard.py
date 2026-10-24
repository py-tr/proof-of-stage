"""The FEC rule and the guard for its document values.

The record: four fields of a committee's report summary as the FEC database holds them (OpenFEC
/reports/house-senate/): cash on hand at the beginning of the period, total receipts, total
disbursements, cash on hand at close. The rule: beginning + receipts - disbursements = close
(the form's own lines 23 + 24 - 26 = 27). A record that breaks it cannot be true as written.

The document: the filed report itself (a scanned PDF for paper filers), whose detailed summary
page prints those four lines. A value read from the document is accepted only if its verbatim
quote is found in the document text, the amount is written inside the quote, and the quote
carries the line's own label or number (so a total from another line cannot stand in for it).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.reader.quotes import is_too_short, locate

FIELDS = ("beginning", "receipts", "disbursements", "close")
RECORD_COLUMNS = {
    "beginning": "cash_on_hand_beginning_period",
    "receipts": "total_receipts_period",
    "disbursements": "total_disbursements_period",
    "close": "cash_on_hand_end_period",
}
# Each field's label on the form's detailed summary page (Form 3, lines 23, 24, 26, 27).
LABELS = {
    "beginning": re.compile(r"\b23\b|cash\s+on\s+hand\s+at\s+(?:the\s+)?beginning", re.I),
    "receipts": re.compile(r"\b24\b|total\s+receipts", re.I),
    "disbursements": re.compile(r"\b26\b|total\s+disbursements", re.I),
    "close": re.compile(r"\b27\b|cash\s+on\s+hand\s+at\s+(?:the\s+)?close", re.I),
}
SUBSTANTIVE = Decimal("1.00")  # gaps under a dollar are reported apart (cents keyed away)
_AMOUNT = re.compile(r"\(?-?\$?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?|\(?-?\$?\s*\d+(?:\.\d{2})?\)?")


def money(value: Any) -> Decimal | None:
    """'20,535.35', '$1,000', '(250.00)' (negative), 1234.5 -> Decimal; None if not an amount."""
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return -amount if negative else amount


def identity_gap(record: dict[str, Any]) -> Decimal | None:
    """beginning + receipts - disbursements - close, from the record's columns; None if missing."""
    values = [money(record.get(RECORD_COLUMNS[f])) for f in FIELDS]
    if any(v is None for v in values):
        return None
    beginning, receipts, disbursements, close = values
    return (beginning + receipts - disbursements - close).quantize(Decimal("0.01"))


def classify(gap: Decimal | None) -> str:
    if gap is None:
        return "incomplete"
    if gap == 0:
        return "consistent"
    return "impossible" if abs(gap) >= SUBSTANTIVE else "cents_only"


def amounts_in(text: str) -> list[Decimal]:
    out = []
    for match in _AMOUNT.finditer(text):
        amount = money(match.group(0))
        if amount is not None:
            out.append(amount)
    return out


@dataclass
class Check:
    field: str
    status: str  # accepted / rejected
    value: Decimal | None = None
    quote: str | None = None
    reason: str = ""


def check_value(field: str, value: Any, quote: Any, document: str) -> Check:
    """Accept a document value only if its quote is in the document, holds the amount, and
    carries the field's own line label or number."""
    amount = money(value)
    if amount is None:
        return Check(field, "rejected", reason="not_an_amount")
    if not isinstance(quote, str) or is_too_short(quote):
        return Check(field, "rejected", amount, None, "quote_too_short")
    span = locate(quote, document)
    if span is None:
        return Check(field, "rejected", amount, quote, "quote_not_in_document")
    text = span.text(document)
    if amount not in amounts_in(text):
        return Check(field, "rejected", amount, text, "amount_not_in_quote")
    if not LABELS[field].search(text):
        return Check(field, "rejected", amount, text, "label_not_in_quote")
    return Check(field, "accepted", amount, text, "")


def verdict(record: dict[str, Any], doc: dict[str, Check]) -> str:
    """Which record field the document contradicts.

    One field differs and the document's own lines add up: that field. The document's lines do
    not add up, or more than one field differs, or a field could not be read: a person decides.
    """
    if any(doc.get(f) is None or doc[f].status != "accepted" for f in FIELDS):
        return "review"
    values = {f: doc[f].value for f in FIELDS}
    doc_gap = values["beginning"] + values["receipts"] - values["disbursements"] - values["close"]
    if doc_gap != 0:
        return "review"  # the filing itself does not add up
    differ = [f for f in FIELDS if money(record.get(RECORD_COLUMNS[f])) != values[f]]
    return differ[0] if len(differ) == 1 else "review"
