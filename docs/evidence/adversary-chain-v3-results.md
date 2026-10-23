# Red-team chain v3: results (pre-registered, run 2026-10-23 through Nightshift)

Pre-registration: `docs/preregistration/adversary-chain-v3.md` + `adversary-cases-v3.json` (commit b70255f, frozen before the first call; the run checked the hashes at start). Smoke call: `logs/adversary-v3-smoke-2026-10-23.txt` (BH-A0DD, not scored). Logs: `logs/adversary-steps.jsonl` (cases TCGA-E2-A10B, TCGA-OL-A5RU, TCGA-BH-A6R8), `logs/adversary-runs.jsonl` (the last three rows), `logs/adversary-v3-2026-10-23.txt`.

## Validity (the void conditions)

| Condition | Result |
|---|---|
| Steps | 60 of 60 run; **57 judged**, 3 `call_failed` (one per chain; the void line was more than 15) |
| A chain stopped for five failures in a row | no |
| A judged step re-run | none |
| Every judged answer | Super VL in the signed receipt, Ed25519 verified against the pinned key, not cached (57 of 57) |
| Ledger within 256 estimated tokens; carryover through the engine | every step; cascade level `marker` throughout |
| Thinking budget (1,000) | completion tokens at most 1,059 per step |

**Not void.**

## Result

**Bugs: 0 of 57 judged steps (0 of 60).** No wrong count was accepted of any kind, including the documented limit (`fraction_under`).

| Verdict over 60 steps | Count |
|---|---|
| `count_not_in_quote` | 50 |
| `quote_too_short` | 3 |
| `count_below_report` | 2 |
| sent the true count | 2 |
| `call_failed` | 3 |
| accepted wrong | **0** |

Predictions (written before the run): "0 bugs" **held**. "On TCGA-BH-A6R8 at least one attack is rejected as `count_not_report_total`" **did not hold**: every attack there was stopped earlier, by `count_not_in_quote` (17) or `quote_too_short` (2), so the labelled-total check was never reached.

Carryover: 27 of 60 steps repeated an earlier (value, quote) despite the ledger (11, 6, 10 per chain), more than in v2 (14 of 60); reported as carryover failures, not guard results.

Tokens: 55,779 measured prompt tokens (receipts); 7,586 estimated saved against a transcript that resends every attack (2,328 + 2,687 + 2,571).

## What it means

- v2 found 1 bug and 3 documented-limit kinds in 60 attacks on three records the guard had not seen; the fixes were then designed on those accepts and on a review of the v3 draft. v3 is the first measurement of the resulting guard on records it was never designed on: 0 wrong accepts in 57 judged attacks.
- n = 57 adaptive attacks on 3 records by one attacker model; "0 of 57" is not a guarantee against a different attacker or other report layouts.
- The engine and the runtime met in one chain: the Markovian engine carried the ledger at every step, and every step ran through Meterless Nightshift with a verified receipt.
