# R1 timing, controlled: results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/r1-timing.md` + `r1-timing.json` (commit 6eace71, frozen before the first call; the run checked the code hashes at start). Logs: `logs/r1-timing.jsonl` (every read), `logs/r1-timing-runs.jsonl`, `logs/r1-timing-2026-10-23.txt`. Run 2026-10-23 21:43 UTC, one session.

## Validity

168 reads planned, 166 answered: 84 Lightning, 82 Super VL; 2 Super reads failed with a Nightshift 502 (trial 1, TCGA-GM-A2DD and TCGA-BH-A0DE), listed and not re-run. Every answer served by the model requested, signature verified against the pinned key (166 of 166). The void line was more than 28 failures. **Not void.**

## Result

| 28 records × 3 interleaved trials, thinking off, one guard version | Lightning | Super VL |
|---|---|---|
| Records settled (N and count both closed), trials 1 / 2 / 3 | **16 / 17 / 16** | 13 / 14 / 13 (trial 1 out of 26 reads: the 2 failed reads were in it) |
| Closings against the stored 4k referee | 95 agree, **0 disagree**, 9 unconfirmed | 82 agree, 0 disagree, 2 unconfirmed |
| Median seconds per read | 2.17 | **1.92** |
| Seconds per trial | 81.4 / 65.9 / 95.2 | 97.6 / 58.4 / 91.3 |
| Completion tokens per trial | 6,391 / 4,817 / 6,364 | 4,049 / 4,468 / 4,685 |

Kill lines:
- **Speed: hit.** Lightning's median seconds per read is not lower than Super's (2.17 against 1.92). As pre-registered, the README no longer says Lightning is faster at R1. The earlier 114 s against 436 s (`docs/evidence/lightning-r1-results.md`) came from runs hours apart; that it was load, not the model, is an inference from this controlled run (load was not measured).
- **Safety: not hit.** 0 of 104 Lightning closings contradicted by the referee; R1 stays Lightning.
- **Settling (reported):** Lightning settled more records than Super in every trial (16–17 against 13–14), confirming the earlier 18 against 15 under controlled conditions.

Prediction (before the run): "Lightning is faster per read in all three trials (median under half of Super's) and settles at least as many records as Super in each trial; 0 contradicted." **Half held:** it settled more in every trial with 0 contradicted, but it was not faster.

## What it means

- Lightning keeps R1 because it settles more fields safely, not because it is faster. It costs more completion tokens than Super with thinking off (about 5,900 against 4,400 per trial of 28 reads).
- 9 of Lightning's 104 closings and 2 of Super's 84 were unconfirmed (the referee's own read was rejected or abstained); none was contradicted.
- One session, one guard version, interleaved order: this is the controlled comparison the earlier run lacked. Seconds through Nightshift still vary with load from trial to trial (65.9 to 95.2 s for the same 28 Lightning reads).
