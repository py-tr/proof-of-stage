"""Boolean data-quality checks for stage_check, shared with offline tests."""

from __future__ import annotations

from typing import Any

REASON_CONTRADICTION = "n_count_contradiction"
REASON_MISSING_DERIVABLE = "n_missing_derivable"
REASON_AMBIGUOUS_MICROMET = "n_ambiguous_micromet"
REASON_COUNT_MISSING = "count_missing"
REASON_CONSISTENT = "consistent"

_MICROMET = frozenset({"N1MI", "N0(I+)", "N0(MOL+)"})
_EDITIONS_N_FROM_COUNT = frozenset({"6", "7"})


def _text(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _edition(row: dict[str, Any]) -> str | None:
    return _text(row, "edition_code") or _text(row, "edition")


def recorded_n_token(row: dict[str, Any]) -> str:
    raw = _text(row, "recorded_n")
    if raw is None:
        return ""
    return raw.upper().replace(" ", "")


def is_micromet_or_itc(row: dict[str, Any]) -> bool:
    return recorded_n_token(row) in _MICROMET


def has_positive_count(row: dict[str, Any]) -> bool:
    return _text(row, "lymph_nodes_positive") is not None


def nodes_consistent_valid(row: dict[str, Any]) -> bool:
    """True unless a 6th/7th-edition count contradicts the recorded N category."""
    edition = _edition(row)
    recorded_main = _text(row, "recorded_n_main")
    derived_main = _text(row, "derived_n_main")
    invalid = (
        edition in _EDITIONS_N_FROM_COUNT
        and has_positive_count(row)
        and recorded_main is not None
        and recorded_main != "NX"
        and not is_micromet_or_itc(row)
        and derived_main is not None
        and recorded_main != derived_main
    )
    return not invalid


def stage_derivable_but_missing_valid(row: dict[str, Any]) -> bool:
    """True unless a 6th/7th-edition count could fill a missing/NX recorded N."""
    edition = _edition(row)
    recorded_main = _text(row, "recorded_n_main")
    invalid = (
        edition in _EDITIONS_N_FROM_COUNT
        and has_positive_count(row)
        and (recorded_main is None or recorded_main == "NX")
    )
    return not invalid


def reason_class(row: dict[str, Any]) -> str:
    edition = _edition(row)
    recorded_main = _text(row, "recorded_n_main")
    derived_main = _text(row, "derived_n_main")
    if not has_positive_count(row):
        return REASON_COUNT_MISSING
    if edition in _EDITIONS_N_FROM_COUNT and (recorded_main is None or recorded_main == "NX"):
        return REASON_MISSING_DERIVABLE
    if edition in _EDITIONS_N_FROM_COUNT and is_micromet_or_itc(row):
        return REASON_AMBIGUOUS_MICROMET
    if (
        edition in _EDITIONS_N_FROM_COUNT
        and recorded_main is not None
        and recorded_main != "NX"
        and derived_main is not None
        and recorded_main != derived_main
    ):
        return REASON_CONTRADICTION
    return REASON_CONSISTENT


FAULT_NODE_COUNT = "node_count"
FAULT_PATHOLOGIC_N = "pathologic_n"
FAULT_REVIEW = "review"
_FAULT_REASONS = frozenset({REASON_CONTRADICTION, REASON_MISSING_DERIVABLE})


def _number(text: str | None) -> float | None:
    try:
        return float(text) if text is not None else None
    except ValueError:
        return None


def fault_field(row: dict[str, Any]) -> str | None:
    """Which registry field the report contradicts (mirror of stage_check.fault_field).

    node_count: the report agrees with the recorded N and its verified count differs from
    the registry's positive-node count, so the count field is wrong.
    pathologic_n: the report agrees with the N the count implies, so the recorded N is wrong
    (or missing). review: no verified report N, or the report's own count contradicts it.
    None: the case has no node-count contradiction or derivable missing N.
    """
    reason = _text(row, "reason_class") or reason_class(row)
    if reason not in _FAULT_REASONS:
        return None
    report_main = _text(row, "report_n_main")
    if report_main is None:
        return FAULT_REVIEW
    report_count = _number(_text(row, "report_nodes_positive"))
    gdc_count = _number(_text(row, "lymph_nodes_positive"))
    if gdc_count is None:
        return FAULT_REVIEW
    # Accusing the count needs evidence about the count itself: the recorded N was
    # abstracted from this same report, so N agreement alone is not enough.
    if (
        reason == REASON_CONTRADICTION
        and report_main == _text(row, "recorded_n_main")
        and report_count is not None
        and report_count != gdc_count
    ):
        return FAULT_NODE_COUNT
    if report_main == _text(row, "derived_n_main") and (
        report_count is None or report_count == gdc_count
    ):
        return FAULT_PATHOLOGIC_N
    return FAULT_REVIEW


def fault_named_valid(row: dict[str, Any]) -> bool:
    """Invalid when the report names a faulty registry field."""
    return fault_field(row) not in (FAULT_NODE_COUNT, FAULT_PATHOLOGIC_N)


def fault_unresolved_valid(row: dict[str, Any]) -> bool:
    """Invalid when a contradiction still needs a human (no settling evidence)."""
    return fault_field(row) != FAULT_REVIEW


def nodes_within_tested_valid(row: dict[str, Any]) -> bool:
    """The basic source-level rule: positive nodes cannot exceed the nodes examined."""
    positive = _number(_text(row, "lymph_nodes_positive"))
    tested = _number(_text(row, "lymph_nodes_tested"))
    return positive is None or tested is None or positive <= tested
