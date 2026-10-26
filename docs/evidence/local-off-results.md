# The local read on the hard cases, thinking off (pre-registered, run 2026-10-26)

Pre-registration: `docs/preregistration/local-off.md` + `local-off.json` (frozen before the first call; designed after a 5-case demonstration, so it reads only the other 20 queue cases). Log `logs/local-off.jsonl`, run record `logs/local-off-runs.jsonl`.

## Result: claim not met, kill fired

| Measure | Result |
|---|---|
| Reads | 20 (0 provider failures), median 12.3 s |
| Passed every check of the frozen local checklist and answered by local Lightning | **19 of 20** |
| Against the builder's labels: correct / wrong accepts | **12 / 2** (bar: at most 3 wrong) |
| Against the independent second labeller | **13 / 1** (bar: at most 2 wrong) |
| **Claim** | **not met; kill fired** |

The kill fired on one read, TCGA-AO-A1KP (6,861 characters), which ran out of output tokens after 85 seconds. Its answer was cut off and nothing from it was accepted. The read was local (lane, model and egress checks passed), but the frozen checklist includes "not truncated", and the pre-registration counts any checklist failure as a kill. The wrong-accept counts were within the bar against both labellers.

Prediction (before the run): about 15-25 correct and 0-2 wrong accepts against each labeller; claim likely met. Correct accepts came in below the prediction (12 and 13).

## What it means, and what it does not

- Thinking off, local Lightning accepted 14 of the values it was scored on against the builder's labels, 2 of them wrong; most values (15 against the builder) were not accepted and would go on to the cloud deep read in the shipped chain.
- No cloud arm read these cases thinking off, so there is no like-for-like comparison. Cloud Lightning at a 4k budget made 3 and 2 wrong accepts on all 25.
- The 5-case demonstration before it (6 accepted, all right) is not part of this test.
- One run, no re-run.
