# Pre-registration: ClinicalTrials.gov records coded both Randomized and Single Group (written 2026-10-25, frozen before the first call)

`python scripts/ctgov_read_run.py run` refuses to run if `app/engine/ctgov_read.py`, its prompt or the frozen records file (`docs/evidence/ctgov/records.json`) differ from the hashes in `ctgov-read.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

Four earlier tries on other data missed because the source text was scanned or OCR, the documents' own numbers were wrong, or the cases were too few. Council 17's dataset scout found a source without those problems:
- **Typed text:** ClinicalTrials.gov records, typed by the sponsors, public domain.
- **A rule from the registry itself:** its Protocol Registration Data Element Definitions say "Single Group: Clinical trials with a single arm", Allocation "N/A (not applicable): For a single-arm trial", and "Randomized: Participants are assigned to intervention groups by chance". So Allocation = Randomized together with Interventional Model = Single Group cannot be true as written.
- **Enough cases:** 8,261 records are coded that way; 893 have posted results.

Designed after the four misses and after the scout's zero-model-call counts. This is a test of "clean typed text plus a rule from the registry's own definitions", chosen to fit what stopped the earlier tries, and disclosed as such.

## Design

- **Records:** fetched from the ClinicalTrials.gov API v2 at freeze time (records with results, coded Randomized and Single Group) and frozen in `docs/evidence/ctgov/records.json`. Each record keeps its text (brief summary, detailed description, arm group descriptions) and its structured arm count.
  - **Multi-arm slice:** 30 records drawn (seed 20261026) from those with two or more arms whose text mentions randomization.
  - **One-arm slice:** every record with exactly one arm whose text mentions randomization or a single-arm design.
- **Reader:** Nemotron Super VL through Nightshift, pinned, signed, no cache, 4k thinking budget. It names the field the text contradicts ("model", "allocation" or "unclear") with one verbatim quote.
- **Code check:** the quote is in the text and carries the cue for its verdict. "Model" needs a randomization cue plus a cue of two or more groups. "Allocation" needs a single-arm cue.
- **Referee for the multi-arm slice:** the structured arm count. Two or more arms means the model field is the wrong one. This is a field independent of the two that contradict.
- **The one-arm slice has no automatic referee** and is reported as found.
- Nothing is stored. Every envelope is kept.

## Claim, kill, void

- **Claim (multi-arm):** the reader names the model field with a verified quote on at least 24 of 30, and the allocation field on at most 2.
- **Kill:** fewer than 18 of 30 name the model field, or more than 4 name the allocation field.
- **Void:** more than 8 provider failures. Never re-run.
- **Honest limit:** for multi-arm records the arm count alone already points at the model field. The quote adds documentary proof, not new information. Only the one-arm slice is decided by the text alone.

## Prediction

In the json, written before the run.
