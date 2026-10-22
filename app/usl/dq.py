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
