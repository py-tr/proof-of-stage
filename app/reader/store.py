"""Write reader results to Zetaris: accepted fields as extractions, the rest as review flags."""

from __future__ import annotations

from datetime import UTC, datetime

from app.reader.reader import METHOD, ReadResult
from app.usl.client import insert_extraction, insert_flag

REVIEW_RULE = "reader_review"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


async def store_result(result: ReadResult, created_at: str | None = None) -> dict[str, int]:
    """Append the result. Returns counts of extractions and review flags written."""
    stamp = created_at or _now()
    counts = {"extractions": 0, "review_flags": 0}
    for name, fr in result.fields.items():
        if fr.status == "accepted" and fr.span is not None:
            await insert_extraction(
                case_id=result.case_id,
                method=METHOD,
                field=name,
                value=fr.value,
                quote=fr.quote,
                quote_start=fr.span.start,
                quote_end=fr.span.end,
                model=result.model,
                receipt_id=result.receipt_id,
                created_at=stamp,
            )
            counts["extractions"] += 1
        else:
            await insert_flag(
                flag_id=f"{result.case_id}:{name}:{REVIEW_RULE}:{fr.reason}",
                case_id=result.case_id,
                rule_id=REVIEW_RULE,
                field=name,
                derived_value=fr.value,
                quote=(fr.quote or "")[:1000] or None,
                reason=fr.reason,
                severity="review",
                model=result.model,
                receipt_id=result.receipt_id,
                created_at=stamp,
            )
            counts["review_flags"] += 1
    return counts
