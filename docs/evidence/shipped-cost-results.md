# The shipped evidence chain's cost against always-4k (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/shipped-cost.md` + `shipped-cost.json` (frozen before the first call). Run 20261025T172328, log `logs/shipped-cost.jsonl`, summary `logs/shipped-cost-runs.jsonl`, envelopes `docs/evidence/attest/shipped-cost-envelopes.jsonl`. The dial test's procedure (`app/engine/dial.py`) unchanged, with today's rungs: first read Nemotron Lightning thinking off, then Super VL 4k on what stays open, against one Super VL 4k read of the same report, same session, through Nightshift.

## Result

| Measure | Result |
|---|---|
| Records | 30 (0 provider failures, void above 10): not void; 30 scored |
| Completion tokens: chain vs always-4k | **53,454 vs 107,438 (-50%)** |
| Records settled by the first read | 17 of 30 |
| First-read closings vs the 4k read | 33 agree, **0 contradicted**, 3 unconfirmed |
| Seconds: chain vs always-4k | 852.1 vs 1461.4 |
| **Claim** (tokens at most 60% of always-4k; at most 10% of closings contradicted) | **met** |

Prediction (before the run): "Before the run, by the coding agent: chain tokens about 45-55% below always-4k (the estimate was about -49%), claim met; Lightning settles about 15-19 of 30 at the first read; 0-1 first-read closings contradicted; 0-3 provider failures."

## What it means, and what it does not

- The chain as shipped, small model first and the large one only on what stays open, used 50% fewer completion tokens than always reading at a 4k budget on these 30 consistent records, measured, replacing the earlier estimate (about -49%).
- Tokens, not price: per-token prices differ by model size and are not measured here.
- These are consistent records, the easy set; on the 25 hard queue records the first read rarely settles a case (`docs/evidence/seat-cost-quality.md`). One run, n = 30, no re-run.
