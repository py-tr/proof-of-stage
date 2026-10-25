# Pre-registration: ClinicalTrials.gov read v2, widened cue vocabulary on new records (written 2026-10-25, frozen before the first call)

`python scripts/ctgov_read_v2_run.py run` refuses to run if `app/engine/ctgov_read_v2.py`, `app/engine/ctgov_read.py`, the prompt or the frozen records file (`docs/evidence/ctgov/records-v2.json`) differ from the hashes in `ctgov-read-v2.json`, if the prediction is not written, or if it has run once.

## Why (disclosed: designed after v1's miss)

v1 (`docs/preregistration/ctgov-read.md`, result in `docs/evidence/ctgov-read-results.md`) stands as published. Its reader named the allocation field on none of the 30 multi-arm records. But the code check accepted only 14 model quotes against a bar of 24, so the kill fired. Reading the rejected quotes showed that the check's cue vocabulary was too narrow:
- it required "randomiz-/randomis-" and turned away "randomly assigned";
- it needed a word for two or more groups from a short list and turned away "1 of 3 routes", "one of", "the control group" and "controlled".

v2 changes **only the cue vocabulary** of the code check:
- the randomization cue also accepts "randomly";
- the groups cue also accepts numbers, "one of", "control/controlled/controls" and "comparator".

On v1's 9 rejected model quotes, the widened check accepts 7. It still rejects "assigned by day" and a quote that only names an arm. Those 9 quotes are where the vocabulary was widened, so v2 is measured only on **30 new records**.

## Design

- **Records:** fetched again from the ClinicalTrials.gov API v2 at freeze time, using v1's query and eligibility rule. 30 multi-arm records are drawn (seed 20261027) from the pool minus every v1 record, both slices. They are frozen in `docs/evidence/ctgov/records-v2.json`.
- **Unchanged from v1:** the reader (Nemotron Super VL through Nightshift, pinned, signed, no cache, 4k thinking budget), the prompt, and the quote location and length rules.
- **Referee:** the structured arm count, as in v1.
- **Logged:** each row also logs v1's check, so the effect of the vocabulary change alone can be read off.
- Nothing is stored. Every envelope is kept.
- There is no one-arm slice: v1 used every eligible one-arm record.

## Claim, kill, void (v1's bar, unchanged)

- **Claim:** the reader names the model field with a verified quote on at least 24 of 30 new multi-arm records, and the allocation field on at most 2.
- **Kill:** fewer than 18 of 30 name the model field, or more than 4 name the allocation field.
- **Void:** more than 8 provider failures. Never re-run.
- **Honest limit (as in v1):** for multi-arm records the arm count alone already points at the model field. The quote adds documentary proof, not new information.

## Prediction

In the json, written before the run.
