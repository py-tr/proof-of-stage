# The local first read as a product mode (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/local-mode.md` + `local-mode.json` (frozen before the first call). Run 20261025T200828, log `logs/local-mode.jsonl`. `python -m app.cli run --case <id> --local`: the shipped evidence chain with its first read on this PC (local Nemotron Lightning, Nightshift Jobs API, "privacy": "local-only", the on-PC focus step; the quote check on the full report); what stays open goes to the cloud deep read as shipped.

## Result

| Measure | Result |
|---|---|
| Records | 20 (0 failures) |
| First reads local by the job checklist | **20 of 20** |
| Local first-read closings vs the census's cloud closings | 21 agree, **0 disagree**, 0 unconfirmed |
| Records settled by the local first read (report only) | 10 of 20 |
| **Claim** (every first read local, 0 disagreements) | **met** |

Prediction (before the run): "Before the run, by the coding agent: 20 of 20 first reads local by the checklist; 0 disagreements with the census's cloud closings (as in the focus test, 0 of 57); the local first read settles about 7-11 of 20 (report only); 0-2 failures. Claim likely met."

## What it means, and what it does not

- Only the first read stays on the PC; a record it does not settle still goes to the cloud deep read with the full report. Fully local reading would need a larger local window (for example a DGX Spark): an inference, not tested.
- The referee is the census's cloud chain on the same records, not a fresh cloud read. One run, no re-run.
