# Ultra as a second reader that can only object: results (pre-registered, scored 2026-10-24)

Pre-registration: `docs/preregistration/ultra-critic.md` + `ultra-critic.json` (commit 92e0d51, frozen before the first call and before the labels). Run log committed unread (24ecfe6): run 20261024T123625, 46 calls (41 stored values + 5 planted controls). Labels frozen bcb11ae. Scores: `logs/label-scores.json` (`ultra_critic`).

## Validity

41 of 46 calls answered, every answer Ultra (`nvidia/nemotron-3-ultra-550b-a55b`) signed by the pinned key; 0 unusable. **5 calls were refused by our own receipt check** (`context_sources = ['messages', 'hmem:1 records']`). The cause was a bug in the critic, not the provider: each call's item id was built from case + field + run, so a planted control and the real row with the same case and field shared one Nightshift scope, and H-MEM recalled the earlier answer within it (`docs/evidence/nightshift-limits.md` §8, corrected). 2 of the 5 were real values (under the void line of 8: **not void**), 3 were planted controls.

## Result

| Measure | Result |
|---|---|
| Real values, by class | 35 agree · **3 contradictions verified** by the guard · 1 contradiction unverified · 2 refused (above) |
| The 3 verified objections against the blind labels | **3 right, 0 wrong**, 1 missed (a value the label disputes that Ultra upheld) |
| The objections | TCGA-A1-A0SN N (stored N2A, Ultra N1), TCGA-AC-A2FK N (stored N1A, Ultra NX), TCGA-E2-A1LI N (stored N0, Ultra N1) |
| Planted controls | 2 of 5 detected, both objecting with the real value; 3 of 5 refused by the receipt check, so not testable |
| **Ship line** (plants ≥ 4/5 and objections ≤ 8 and right > wrong and wrong ≤ 1) | **not met** (plants 2/5) |

As pre-registered: **"Ultra as a second reader: measured, not on the critical path."** No re-run, no prompt change, no relabelling.

Prediction (before the run): "at most 3 verified objections on real values; plants at least 4 of 5": the first half **held** (3), the second **did not** (2 of 5, because 3 controls were refused by our own scope bug, not missed).

## What it means, and what it does not

- On the real values, every objection Ultra could back with a verified quote was one the blind human reader also made, and the 3 objections fall on 3 of the 7 cases where the product's verdict differs from the label (`docs/evidence/baseline-m0-results.md`): as a refer-only second reader it would have sent 3 of the product's 7 disagreements to a person, with no false alarm in this run.
- The positive control could not be judged: our scope bug got 3 of its 5 rows refused. The fix is one line (a unique item id per call); a separately pre-registered v2 with only that change is the honest way to test whether the critic can ship.
- n = 41 values, one run, one lay labeller: an encouraging measurement, not a shipped feature.

## v2: one Nightshift scope per call (pre-registered, run 2026-10-24 13:34 UTC)

Pre-registration: `docs/preregistration/ultra-critic-v2.md` + `ultra-critic-v2.json` (commit 63a6cdd, frozen before the first call; designed after the labels were scored, disclosed; v1 byte-identical except one item id per call). Log: `logs/ultra-critic-v2.jsonl`, summary `logs/ultra-critic-v2-runs.jsonl`, score `logs/ultra-critic-v2-score.json` (scored with v1's `critic.score` against the frozen labels).

| Measure | v2 |
|---|---|
| Calls | 46 of 46 answered, 46 unique scopes, **0 provider failures, 0 memory refusals**; every answer Ultra, signed by the pinned key |
| Real values, by class | 38 agree · **3 contradictions verified** |
| Verified objections against the labels | **3 right, 0 wrong**, 1 missed |
| The objections | the same 3 as v1: TCGA-A1-A0SN N (N2A -> N1), TCGA-AC-A2FK N (N1A -> NX), TCGA-E2-A1LI N (N0 -> N1) |
| Planted controls | **4 of 5 detected**, all 4 objecting with the real value |
| **Ship line** (plants ≥ 4/5 and objections ≤ 8 and right > wrong and wrong ≤ 1) | **met: the critic ships** as a read-only "a second reader objects" line on the case page and a `/how` card; it never writes to the layer and never accepts or changes a value |

Prediction ("0 memory refusals; plants at least 4 of 5; objections close to v1's 3 on the same cases"): **held**. v2 is a confirmation run designed after the labels were known; its prompt, guard, plants and ship line are v1's, so nothing in it could be tuned toward the labels.
