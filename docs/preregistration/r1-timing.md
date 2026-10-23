# Pre-registration: R1 timing, controlled (written 2026-10-23, frozen before the first call)

`python -m app.cli r1-timing` refuses to run if `app/engine/timing.py`, `lightning.py`, `rungs.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `r1-timing.json`.

## Why

The pre-registered Lightning R1 result (`docs/evidence/lightning-r1-results.md`: 18 of 28 settled vs Super's 15, 114 s vs 436 s) compared two runs made hours apart, under different guard versions, on a load-sensitive endpoint, so its timing was explicitly not a controlled comparison. This run controls both.

## Design

- **Records:** the same 28 dial-test records (ids frozen in `r1-timing.json`, the same list as `lightning-cases.json`).
- **Reads:** for each of **3 trials**, every record is read twice back to back, once by Lightning (`nvidia/nemotron-3.5-lightning-30b-a3b`) and once by Super VL (`nvidia/nemotron-3.5-super-vl-120b-a12b`), both through Nightshift, each pinned in its signed receipt, cloud, not cached, thinking off, the reader's prompt and the current guard (one code version for every read). Order: Lightning first on trials 1 and 3, Super first on trial 2. 168 reads in one session.
- **R1's closing rule** on every read (a field closes only if it agrees with the registry and the reading is self-consistent under the count rule). **Referee:** the dial run's stored always-4k Super read (agree / disagree / unconfirmed).

## Measures (fixed now)

- Per model: records settled in each trial (reported as the three values, not averaged into one), median seconds per read, seconds and completion tokens per trial, closings against the referee.

## Kill lines (what changes in the README)

- **Speed:** if Lightning's median seconds per read is not lower than Super's, the README stops saying Lightning is faster at R1.
- **Safety:** if the referee contradicts more than 10% of Lightning's closings, R1 goes back to Super.
- **Settling:** reported as measured; the R1 seat was decided by the earlier pre-registered run and is not re-decided here unless the safety line is hit.
- **Void:** more than 28 failed reads (a sixth). Failed reads are listed, never re-run.

## Prediction (before the run)

Lightning is faster per read in all three trials (median under half of Super's) and settles at least as many records as Super in each trial; 0 contradicted. A guess.
