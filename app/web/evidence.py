"""Pure logic behind the case page: rule lines, guard re-checks, the challenge, the headline.

Nothing here calls a model or Zetaris, so the same code runs in SAMPLE_MODE.
"""

from __future__ import annotations

import re
from typing import Any

from app.reader.reader import NODES_POSITIVE, judge_count, judge_field
from app.usl.dq import (
    FAULT_NODE_COUNT,
    FAULT_PATHOLOGIC_N,
    FAULT_REVIEW,
    fault_field,
)
from app.usl.rules import staging_rule_rows

_EXCLUDED_OUTPUTS = {"UNRESOLVED", "flag", "suffix/prefix", "not staged"}
_MAIN_N = re.compile(r"N[0-9X]")  # same as the USL's regexp_extract
_BARE_N = re.compile(r"^N[0-3]$")


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def count_rules(
    count: Any, tested: Any, edition: str | None, site: str | None = "breast"
) -> list[dict[str, str]]:
    """The paraphrased N rules a positive-node count selects (mirror of 054_activate_derived_stage).

    tested missing or zero selects the not-examined rules (BN1/CN1), as the USL does.
    Pass tested=True when the source states a count, so nodes were examined.
    """
    positive = _number(count)
    examined = 1.0 if tested is True else _number(tested)
    site = site or "breast"
    if positive is None or not edition:
        return []
    matched = []
    for rule in staging_rule_rows():
        if rule["site"] != site or rule["element"] != "N":
            continue
        if edition not in rule["edition"].split(","):
            continue
        if examined is None or examined == 0:
            if rule["rule_id"] in ("BN1", "CN1"):
                matched.append(rule)
            continue
        low, high = _number(rule["min_value"]), _number(rule["max_value"])
        if low is None or rule["output"] in _EXCLUDED_OUTPUTS or not rule["output"]:
            continue
        if positive >= low and (high is None or positive <= high):
            matched.append(rule)
    return sorted(matched, key=lambda rule: rule["output"])


def main_n(value: str | None) -> str | None:
    """'pN2a' / 'N2A' -> 'N2'; None when there is no N category."""
    match = _MAIN_N.search((value or "").upper())
    return match.group(0) if match else None


def _category(value: str | None) -> str:
    text = re.sub(r"\s+", "", (value or "").upper())
    return re.sub(r"^(?:YP|P|C)", "", text)


def n_range(category: str | None, edition: str | None, site: str | None = "breast") -> str | None:
    """Plain words for a count-defined N category: 'N1a' -> '1-3 positive nodes'.

    Only for categories a count rule defines exactly (N0, N1a, N2a, N3a) or a bare
    N0-N3; N1b, N1c, N2b, N3b, N3c depend on where the nodes are, so no range is given.
    """
    target = _category(category)
    if target == "NX":
        return "nodes not assessed"
    if not target or not edition:
        return None
    for rule in staging_rule_rows():
        if rule["site"] != (site or "breast") or rule["element"] != "N" or not rule["min_value"]:
            continue
        if edition not in rule["edition"].split(","):
            continue
        output = _category(rule["output"])
        if output != target and not (_BARE_N.match(target) and main_n(output) == target):
            continue
        low, high = rule["min_value"], rule["max_value"]
        if high == low:
            return f"{low} positive nodes"
        return f"{low}-{high} positive nodes" if high else f"{low} or more positive nodes"
    return None


def _count(value: Any) -> str:
    number = _number(value)
    return "missing" if number is None else f"{number:g}"


def headline(check: dict[str, Any]) -> str:
    """The case in plain words, leading with the field the evidence names (never a model's text)."""
    edition = check.get("edition_code")
    site = check.get("site_key")
    recorded = check.get("recorded_n") or "missing"
    recorded_words = n_range(recorded, edition, site)
    count = _count(check.get("lymph_nodes_positive"))
    derived = check.get("derived_n")
    tested = _number(check.get("lymph_nodes_tested"))
    report_n = check.get("report_n")
    report_count = _number(check.get("report_nodes_positive"))
    fault = check.get("fault_field")
    reason = check.get("reason_class")
    rec = f"Recorded N is {recorded}" + (
        f", which means {recorded_words}" if recorded_words else ""
    )
    if derived and main_n(derived) == "NX" and not tested:
        reg = (
            f"The registry count is {count}, but its tested count is missing, "
            f"so the rule gives {derived}"
        )
    else:
        reg = f"The registry count is {count}" + (f", which would be {derived}" if derived else "")
    rep = f"The report says {report_n}" + (
        f" and counts {report_count:g}" if report_count is not None else ""
    )
    if fault == FAULT_NODE_COUNT:
        return f"The evidence names the count field. {rec}. {reg}. {rep}."
    if fault == FAULT_PATHOLOGIC_N:
        lead = (
            "The evidence says the N field should be filled in."
            if reason == "n_missing_derivable"
            else "The evidence names the N field."
        )
        return f"{lead} {rec}. {reg}. {rep}."
    if fault == FAULT_REVIEW and check.get("read") is False:
        return (
            f"Not read yet. {rec}. {reg}. They cannot both be true; "
            "Nemotron has not read this report yet."
        )
    if fault == FAULT_REVIEW:
        settle = (
            f" {rep}, which does not settle it." if report_n else " No verified reading settles it."
        )
        return f"Needs a person. {rec}. {reg}.{settle}"
    if reason == "n_count_contradiction":
        return f"{rec}. {reg}. They cannot both be true. No model answer in this mode."
    if reason == "n_missing_derivable":
        return f"{rec}. {reg}. No model answer in this mode."
    return f"{rec}. {reg}. They agree."


def why_chain(check: dict[str, Any], accepted: list[dict[str, Any]]) -> list[str]:
    """The case as five short steps: rule, the report's words, the code check, the field, a person.

    Built only from layer values and the stored, re-checked quote (never a model's prose); an
    empty list when the registry fields agree."""
    fault = check.get("fault_field")
    if not fault and check.get("reason_class") not in (
        "n_count_contradiction",
        "n_missing_derivable",
    ):
        return []
    recorded = check.get("recorded_n") or "missing"
    count = _count(check.get("lymph_nodes_positive"))
    derived = check.get("derived_n")
    rule = f"Rule: the registry says {recorded} with {count} positive nodes" + (
        f"; {count} would be {derived}, so both cannot be true" if derived else ""
    )
    quoted = next(
        (a for a in accepted if a.get("quote") and a.get("field") in (NODES_POSITIVE, "N")), None
    )
    if quoted is None:
        return [rule, "No checked quote from the report yet", "A person decides"]
    words = f'The report says: "{quoted["quote"].strip()}"'
    checked = "Code check: these exact words are in the report"
    if fault == FAULT_NODE_COUNT:
        field = "So the report contradicts the count field"
    elif fault == FAULT_PATHOLOGIC_N:
        field = "So the report contradicts the stage field (N)"
    else:
        field = "The report does not settle which field is wrong"
    return [rule, words, checked, field, "A person decides; the record is never edited"]


# The guard's checks in the order it runs them: (rejection reason, what passing means).
COUNT_CHECKS = (
    ("invalid_count", "a whole number from 0 to 99"),
    ("quote_too_short", "a quote long enough to prove something"),
    ("quote_not_in_report", "the quote is word for word in the report"),
    ("count_not_in_quote", "the number is the positive count inside that quote"),
    ("count_below_report", "not below a node fraction the report states"),
    ("count_not_report_total", "equal to the total the report states, if it states one"),
)
FIELD_CHECKS = (
    ("invalid_category", "a valid category"),
    ("quote_too_short", "a quote long enough to prove something"),
    ("quote_not_in_report", "the quote is word for word in the report"),
    ("quote_does_not_support", "the quote shows that category (a stage, node count or size)"),
)


def recheck(field: str, value: Any, quote: str | None, report: str) -> list[dict[str, Any]]:
    """Re-run the guard on a stored value: every check it passed, then the one it failed."""
    if field == NODES_POSITIVE:
        result = judge_count({"N_positive": value, "N_positive_quote": quote}, report)
        steps = COUNT_CHECKS
    else:
        result = judge_field(field, {field: value, f"{field}_quote": quote}, report)  # type: ignore[arg-type]
        steps = FIELD_CHECKS
    checks = []
    for reason, label in steps:
        failed = result.status != "accepted" and result.reason == reason
        checks.append({"check": label, "ok": not failed})
        if failed:
            break
    checks.append({"check": "accepted", "ok": result.status == "accepted"})
    return checks


def challenge(
    check: dict[str, Any],
    report: str,
    field: str,
    value: Any,
    quote: str,
    known: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the real guards on a reader answer typed by a person ('try to fool it').

    Returns the guard verdict and, if accepted, the fault the USL would compute with it.
    `known` carries the person's earlier accepted N / count in this session, so a count
    and an N typed one after the other combine as the reader's two answers would.
    """
    if field == NODES_POSITIVE:
        result = judge_count({"N_positive": value, "N_positive_quote": quote}, report)
    elif field in ("T", "N"):
        result = judge_field(field, {field: value, f"{field}_quote": quote}, report)  # type: ignore[arg-type]
    else:
        raise ValueError("field must be T, N or NPOS")
    verdict: dict[str, Any] = {
        "field": field,
        "status": result.status,
        "value": result.value,
        "reason": result.reason,
        "span": [result.span.start, result.span.end] if result.span else None,
    }
    if result.status == "accepted" and field in ("N", NODES_POSITIVE):
        what_if = dict(check)
        for key in ("report_n_main", "report_nodes_positive"):
            if known and known.get(key) not in (None, ""):
                what_if[key] = known[key]
        if field == "N":
            what_if["report_n_main"] = main_n(result.value)
        else:
            what_if["report_nodes_positive"] = result.value
        verdict["fault_field_if_accepted"] = fault_field(what_if)
        verdict["used"] = {
            "report_n_main": what_if.get("report_n_main"),
            "report_nodes_positive": what_if.get("report_nodes_positive"),
        }
    return verdict
