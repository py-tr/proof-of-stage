# Local first read with an on-PC focus step: results (pre-registered, run 2026-10-24)

Pre-registration: `docs/preregistration/local-focus.md` + `local-focus.json` (commit 92eb29c, frozen before the first call; designed after the local R1 test's diagnosis, on its 4 failed records, disclosed). Run 20261024T163042, log `logs/local-focus.jsonl`, summary `logs/local-focus-runs.jsonl`. 60 records of the hidden-errors set, none read locally before.

## Result

| Measure | Local Lightning + focus step (this PC) | Bar |
|---|---|---|
| Settled (both open fields closed by R1), of 60 | **28** | ≥ 33: **not met** |
| Records whose local job failed | **0** (the local R1 test had 4, all long reports) | 0: met |
| Long reports (> 7,000 characters) cut by the focus step | **6 of 6 reached the model, 4 settled**, the longest 24,092 characters cut to 3,721 | report-only |
| Closings vs the cloud ladder (Lightning R1, Super R2) | **55 agree, 0 disagree**, 2 unconfirmed | 0 disagree: met |
| Every attempt local (frozen checklist) | **yes**, 60 of 60 | met |
| Wall clock | 526 s (about 9 s per record) | report-only |

**Claim** ("a local Nemotron did the first read on this PC, long reports included through an on-PC focus step, without the report leaving it"): **not met**, on the settled count alone (28 under 33). Prediction ("settled about 28 to 36; 0 disagreements; every attempt local; at least 4 of 6 focused reach the model, 2 or more settle; reaching 33 uncertain"): held, at its low end.

Honesty row, not a bar: cloud Lightning settled 34 of these 60 at R1. 25 records settled in both, 3 only locally, 9 only in the cloud.

## What it means, and what it does not

- The window problem is solved: every report reached the local model, long ones through the focus step, and none of the 57 local closings disagreed with the cloud ladder. Every quote was checked against the full report, so the excerpt never added an acceptance the full report does not support.
- The remaining gap is reading, not the window: the guard rejected about a third of the local reads' N and count answers (N 21 of 60, count 22 of 60), mostly quotes that do not support the value or are too short, so those records escalate. On this PC the local lane would settle fewer records than cloud Lightning and send more to Super.
- So cloud Lightning keeps R1. A local first read is a working privacy option at a measured cost (28 vs 34 settled on these records), not the default.
- Not tested: a GPU with room for the 16,384-token window, a different quantisation, or a larger local model. No re-run.
