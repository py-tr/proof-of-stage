# ClinicalTrials.gov: records coded both Randomized and Single Group (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/ctgov-read.md` + `ctgov-read.json` (frozen before the first call). Run 20261025T194808, log `logs/ctgov-read.jsonl`, summary `logs/ctgov-read-runs.jsonl`, envelopes `docs/evidence/attest/ctgov-read-envelopes.jsonl`. Population at freeze: 893 records with results coded Allocation = Randomized and Interventional Model = Single Group, which the registry's own definitions say cannot both be true. Nemotron Super VL through Nightshift (signed) named the field the record's own text contradicts, with one verbatim quote; code checked the quote is in the text and carries the cue for its verdict.

## Result

| Slice | Records | Model field named, verified | Allocation field named, verified | Unclear or not verified |
|---|---|---|---|---|
| Multi-arm (referee: the structured arm count says the model field is wrong) | 30 | **14** | **0** | 16 |
| One-arm (no automatic referee; reported as found) | 26 | 6 | 4 | 16 |

0 provider failures. **Claim** (multi-arm: model field on at least 24 of 30, allocation on at most 2): **not met**; **kill fired** (fewer than 18).

Prediction (before the run): "Before the run, by the coding agent: multi-arm: 24-29 of 30 name the model field with a verified quote (claim likely met; misses from background mentions or crossover wording), 0-2 allocation; one-arm slice: mostly 'model' or 'unclear' (randomization of order or dose cohorts in one group), few 'allocation'; 0-3 provider failures."

## Why most misses happened (read after the run, not pre-registered)

- On the multi-arm slice the reader never named the wrong field: every verified answer agrees with the record's arm count (0 of 30 wrong).
- 9 multi-arm answers named the right field but failed our own cue check, which required "randomiz-" and a two-groups word in the same quote. About 5 of them were correct statements the frozen vocabulary did not cover ("randomly assigned … or to the control group", "randomized to 1 of 3 routes", "one of 2 treatment regimens", "randomized and concurrent controlled"); the check correctly refused 2 (assignment by day of presentation, a cluster design, is not randomization; an arm list without a randomization statement). A wider cue list, written after the run, is not a claim and the result stands as frozen.
- 6 answers were "unclear" or empty, and 1 model answer's quote was not in the text (NCT01093417: two arm descriptions stitched together).
- One-arm slice: 4 records verified as single-arm studies coded Randomized, so the allocation field is the one the text contradicts (NCT00570141, NCT00773383, NCT01106248, NCT01663714); 6 used within-person randomization (split-face, one eye vs the other, test sites), a design the two coded fields do not describe well.

## What it means, and what it does not

- On clean typed text the reading did not produce a wrong field (0 of 30 against the arm count), but our quote check as written accepted too few correct answers to meet the bar; the miss is split between the check's vocabulary and the reader's own unclear or empty answers (a post-hoc re-score with no cue words, quote located and field agreeing with the arm count, gives 23 of 30, still under the bar; not a claim). The arm list is part of the text the reader sees, so the quote documents the answer rather than discovering it. 893 such records have results; the registry's own count is 8,261.
- Correction (after an AI-assisted review): within-person designs (NCT01053000, NCT01848288, NCT02251561) are counted as correct model answers in the multi-arm slice, although the one-arm note above says the two coded fields describe that design poorly.
- One run, no re-run; the multi-arm verdicts are referred to the arm count, not to a person.

## Found after the run, confirmed by the builder (2026-10-25, not pre-registered)

An AI-assisted review of the one-arm slice pointed to 2 records listed with one arm where the reader named the model field with a verified quote describing two groups. The builder (a lay reader) read both records and confirmed that each text describes two or more groups, so the record's Single Group field is the one its own text contradicts. These are the only records in this test where the quote carries information the structured fields lack.

| Record | Arms listed | Verified quote |
|---|---|---|
| NCT00073008 | 1 ("lapatinib") | "Randomized, open-label, parallel group, 2-stage study to evaluate and compare 2 dose schedules (1500 mg once daily and 500 mg twice daily) of oral lapatinib." |
| NCT00391469 | 1 ("control treatment", no description) | "In this study we will randomize 1,200 cardiac arrest patients … to hypothermia … or to standard of care following ROSC." |

Reported as found: the one-arm slice had no automatic referee and these two were picked out after the run, so they are examples, not a rate.
