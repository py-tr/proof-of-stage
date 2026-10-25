# Pre-registration: the shipped evidence chain's cost against always-4k (written 2026-10-25, frozen before the first call)

`python scripts/shipped_cost_run.py run` refuses to run if `app/engine/shipped_cost.py`, `dial.py`, `rungs.py`, `run_case.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `shipped-cost.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

The dial test (2026-10-23) measured the evidence chain with Super VL at the first read: 40% fewer completion tokens than always reading at a 4k budget, with 0 of 31 first-read closings contradicted. Lightning took the first-read seat afterwards, so the token saving of the chain as shipped was only an estimate (about −49%, `docs/evidence/seat-cost-quality.md`). Two council-13/14 judges flagged this. This test replaces the estimate with a measurement. It was designed after the judges' review and is disclosed as such.

## Design

- **Records:** the dial test's 30 frozen records (`dial-cases.json`): consistent records, 6th/7th edition, report text available.
- **Procedure:** the dial test's own `run_one` and `summarise` (`app/engine/dial.py`), imported unchanged, with today's rungs. For each record:
  - the evidence chain as shipped: first read Nemotron Lightning with thinking off, which may close only a field that agrees with the registry; then the deep read, Super VL at a 4k budget, on what stays open;
  - then a control: one Super VL 4k read of the same report.

  Both run through Nightshift, signed and interleaved per record, in one session. Nothing is stored. Every envelope is kept.
- **Measures:**
  - completion tokens of the chain against the control (Nightshift's own usage);
  - records settled by the first read;
  - first-read closings that agree with, contradict, or are unconfirmed by the control;
  - seconds.

## Claim, void

- **Claim:** the chain's completion tokens are at most 60% of always-4k, and the first-read closings the control contradicts are at most 10%.
- **Void:** more than 10 provider failures. Never re-run.

## Prediction

In the json, written before the run.
