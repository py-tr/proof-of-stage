# Where the reasoning dial pays: results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/dial-sample.md` and `dial-cases.json` (commit 8844b04, frozen before the first call; the run checked the code hashes at start). Logs: `logs/dial-sample.jsonl` (one row per record), `logs/dial-runs.jsonl` (the summary), `logs/dial-2026-10-23.txt`, the rungs in `logs/markovian-chunks.jsonl` (run ids `dial-…`).

## Validity

30 of 30 records run, one after another, through Nightshift (Super VL pinned in the signed receipt). 2 provider failures (TCGA-E2-A15S: the ladder run errored; TCGA-D8-A1JJ: the control read failed with a Nightshift 502), reported and not scored; the void line was more than 10. **28 scored records. Not void.**

## Result

| Measure | Result |
|---|---|
| Records settled at R1 (the thinking-off read closed both N and the count) | **15 of 28 (54%)**; the other 13 went on to the 4k rung |
| Fields closed at R1 | 31 |
| The always-4k control on those 31 fields | **30 agree, 0 disagree, 1 unconfirmed** (TCGA-A2-A04X: the control also read 0 positive nodes, but its quote failed the guard, so it does not confirm) |
| Kill line: the control contradicts more than 10% of R1's closings | **not hit** (0 of 31) |
| Completion tokens, ladder vs always-4k (Nightshift usage) | **56,160 vs 93,419: 40% fewer** |
| Seconds, ladder vs always-4k | 2,372 vs 2,964: 20% less |

Prediction (written before the run): "at least half the scored records settle at R1, and the ladder uses fewer completion tokens than the always-4k control." Both held.

## What it means, and what it does not

- On records whose registry fields agree, the thinking-off read settles about half of them in seconds, and the deep read never contradicted a field it closed; spending the 4k budget only where the cheap read cannot settle saves 40% of completion tokens here.
- On the 25-case review queue the opposite holds, by construction: a contradiction case cannot agree with both registry fields, so every case goes on to the 4k rung and the ladder costs more than always-4k. The dial pays on the records that agree, which are most of the registry (853 of 1,097 are consistent).
- n = 28 from one draw (seed 20261023); "0 of 31 contradicted" is a sample, not a guarantee. Nightshift reports no reasoning tokens, so tokens here are completion tokens.
