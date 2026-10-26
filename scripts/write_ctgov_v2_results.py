"""Write docs/evidence/ctgov-read-v2-results.md from the v2 run's own summary row and per-record log."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
OUT = ROOT / "docs" / "evidence" / "ctgov-read-v2-results.md"


def main() -> None:
    runs = [
        json.loads(x) for x in (LOGS / "ctgov-read-v2-runs.jsonl").read_text("utf-8").splitlines()
    ]
    s = runs[-1]
    rows = [
        r
        for r in map(json.loads, (LOGS / "ctgov-read-v2.jsonl").read_text("utf-8").splitlines())
        if r.get("run") == s["run"]
    ]
    pre = json.loads((ROOT / "docs" / "preregistration" / "ctgov-read-v2.json").read_text("utf-8"))
    fields = Counter(
        r.get("field") or "no parsable answer" for r in rows if "provider_failure" not in r
    )
    rejected = Counter(
        (r.get("check") or {}).get("reason")
        for r in rows
        if r.get("field") == "model" and not (r.get("check") or {}).get("verified")
    )
    lines = [
        "# ClinicalTrials.gov read v2: widened cue vocabulary on 30 new records (pre-registered, run 2026-10-25)",
        "",
        f"Pre-registration: `docs/preregistration/ctgov-read-v2.md` + `ctgov-read-v2.json` (frozen before the first call). Run {s['run']}, log `logs/ctgov-read-v2.jsonl`, envelopes `docs/evidence/attest/ctgov-read-v2-envelopes.jsonl`. Designed after v1's miss (`docs/evidence/ctgov-read-results.md`, which stands); only the quote check's cue vocabulary changed, measured on records v1 never saw.",
        "",
        "## Result",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Records | {s['records']} ({s['failures']} provider failure{'s' if s['failures'] != 1 else ''}) |",
        f"| Field named by the reader | {', '.join(f'{k} {v}' for k, v in sorted(fields.items()))} |",
        f"| **Model field named with a verified quote** (bar 24) | **{s['model_verified']} of {s['records']}** |",
        f"| Allocation field named with a verified quote (bar at most 2) | {s['allocation_verified']} |",
        f"| The same answers under v1's narrower check | {s['model_verified_under_v1_check']} of {s['records']} |",
        f"| Model answers the check turned away, by reason | {', '.join(f'{k} {v}' for k, v in rejected.items()) or 'none'} |",
        f"| **Claim** | **{'met' if s['claim_met'] else 'not met'}**{'; kill fired' if s['kill'] else ''}{'; void' if s['void'] else ''} |",
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        "## What it means, and what it does not",
        "",
        "- The vocabulary was widened after reading v1's rejected quotes; the bar and everything else stayed as in v1, and v2 was measured once, on new records.",
        '- **Disclosure (found by a council review after the run):** the frozen code changed more than the pre-registration lists. Besides "randomly", numbers, "one of", control and comparator, it also added "each" and "five" to the groups cue, widened the single-arm cue ("single cohort", "one cohort", "be treated"), and narrowed the randomization cue so that "randomizes" no longer matches. One of the 22 (NCT02030002, "randomized for each patient") passes only because of "each": under the disclosed vocabulary the count is **21 of 30**. No allocation answer and no rejected answer was affected. The verdict (not met) is the same either way.',
        '- The groups half of the cue check is weak: "or" and any number count as a groups word, so in practice "verified" means a sentence found verbatim in the record that mentions randomization.',
        "- The arm labels and descriptions are part of the text the reader sees, so on these records the quote documents the answer rather than discovering it.",
        '- Read by hand after the run: of the 3 model answers turned away, 2 are correct statements the cue list still misses ("comparative study of X to Y", "compared to patients receiving only") and 1 quotes only the arm descriptions (correctly rejected). The claim is not met.',
        "- 3 answers had no parsable field and 1 call failed (a Nightshift 502); none was re-run. The envelopes keep only each answer's hash and length, so the cause of the unparsable answers cannot be recovered; across both runs 3 of the 9 coincide with the 4k thinking budget being used up.",
        "- Across v1 and v2 the reader named the allocation field, the wrong one, on 0 of 59 answered multi-arm records (60 drawn, one 502); it named the model field on 49.",
        "- For multi-arm records the arm count alone already points at the model field; the quote adds documentary proof, not new information.",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ok", OUT.name)


if __name__ == "__main__":
    main()
