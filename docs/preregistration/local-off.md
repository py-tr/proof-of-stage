# Pre-registration: the local read on the hard cases, thinking off (written 2026-10-26, frozen before the first call)

`python scripts/local_off_run.py run` refuses to run if `app/engine/local_off.py` or a module it reuses differs from the hashes in `local-off.json`, if the cases changed, if the prediction is not written, or if it has run once.

## Why (disclosed)

- **What the local lane can do on this release:**
  - after the Nightshift 2026-10-26 release, local Lightning reads whole reports with thinking off (`docs/evidence/local-whole-results.md`, claim met);
  - with thinking on, a local attempt does not finish (`docs/evidence/local-deep-results.md`, void).
- **A demonstration came first.** After the void, a demonstration (not pre-registered) read the first 5 of the 25 review-queue cases this way. It accepted 6 values, all matching both labellers, and rejected 4 (`logs/local-thinkoff-demo-2026-10-26.jsonl`). This test was designed after seeing it, so it reads only the other 20 queue cases.

## Design

- **Cases:** the deep-read bench's cases 6-25 (the first 5 were the demonstration).
- **Reader:** local Lightning through Nightshift's Jobs API with `"privacy": "local-only"`, thinking off. It uses the shipped system prompt on the whole report, and the guard checks each value's quote against the whole report.
- **Local check:** every read must pass the frozen local job checklist and be answered by `local-runtime/nemotron-3.5-lightning-30b-a3b`.
- **Scoring:** the deep-read bench's rules (correct accepts, wrong accepts, not accepted; N by its main category) against both frozen label sets (builder; independent second labeller).
- **Comparison, for context only:** cloud Lightning at a 4k budget made 3 wrong accepts against the builder and 2 against the second labeller on all 25. This arm is thinking off, so it is not like for like; the bar uses those counts as a ceiling.
- Nothing is stored.

## Claim, kill, void

- **Claim:** every read local and answered by local Lightning, and wrong accepts at most 3 (builder) and at most 2 (second labeller).
- **Kill:** any read not local or not local Lightning, or 5 or more wrong accepts against either labeller.
- **Void:** more than 6 of 20 provider failures. Never re-run.
- **Reported, not claimed:** correct accepts, not accepted, seconds per read. A value it does not accept goes to the cloud deep read in the shipped chain.

## Prediction

In the json, written before the run.
