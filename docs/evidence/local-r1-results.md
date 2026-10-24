# Local Nemotron as the first read (on this PC): results (pre-registered, run 2026-10-24)

Pre-registration: `docs/preregistration/local-r1.md` + `local-r1.json` (commit 1169ba9, frozen before the first call). Run 20261024T160819, log `logs/local-r1.jsonl`, summary `logs/local-r1-runs.jsonl`. Nightshift 1.2.3 Jobs API, "privacy": "local-only", lane `nemotron-3-5-lightning-3-2`.

## Result

| Measure | Local Lightning (this PC) | Bar |
|---|---|---|
| Settled (both open fields closed by R1), of 28 | **13** | ≥ 15: **not met** |
| Closings contradicted by the dial run's 4k Super read | **0** of 28 | 0: met |
| Unconfirmed closings (referee had no accepted value) | 5 of 28 | report-only |
| Records whose local job failed ("local job errored") | **4** | void only above 9 |
| Attempts that ran: local-only checklist (privacy, lanes, lane, resolved model, honored, egress, finish) | **all passed**; every answer from `local-runtime/nemotron-3.5-lightning-30b-a3b` | — |
| Retries of an empty answer | 0 | report-only |
| Wall clock, 28 records | 321 s (about 11 s each, including 2 s polling) | report-only |

**Claim** ("on the dial records, a local Nemotron did the first read on this PC without the report leaving it"): **not met**: 13 settled is under the floor, and the 4 failed records also fail the "no record failed" condition. Prediction ("about 12 to 16 settled; 0 contradicted; every attempt local; reaching 15 a coin flip"): held.

Honesty row, not a bar: cloud Lightning settled 18 of 28 in its test and 16, 17, 16 in the timing trials, with 5 unconfirmed of 38 closings.

## The four failures (report-only, inference)

The 4 failed records are exactly the 4 longest reports in the set: 8,116, 8,670, 10,523 and 14,193 characters. Every settled record was 8,046 characters or shorter (the 11 unsettled-but-answered records were 483 to 3,077). The job record says only "errored", so the cause is not logged; a context window on the local lane smaller than the longest reports is the likely reading, not a measured one. Without those 4, local Lightning settled 13 of the 24 it could read.

**Diagnosis after the run (one unscored call, 2026-10-24):** the longest failed report (TCGA-E2-A14U, 10,523 characters), sent again as the same local-only job, came back `errored` with "no attempt produced a candidate: no slot was dispatched" and "generated 0 of a planned 1 attempts": the job never reached the model. That fits Nightshift refusing a prompt larger than the local lane's context window before dispatch (its engine drops lanes that cannot hold the prompt). So the four failures are the lane's context setting, not the model's reading; the published result stands as it is.

## What it means, and what it does not

- The privacy mechanism works: every local attempt that ran stayed on the local lane by Nightshift's own job record, and none of its closings was contradicted.
- As a replacement for the cloud first rung on these records, it falls short of the pre-registered bar; cloud Lightning keeps R1. The local lane is not added to the ladder.
- 0 contradicted is what the closing rule produces whenever a reader declines to close; it is not evidence of reading quality on its own.
- Not tested: a local lane with a larger context window, a different quantisation, or chunking long reports. No re-run.
