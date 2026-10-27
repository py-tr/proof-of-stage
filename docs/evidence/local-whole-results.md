# The local first read on whole reports (pre-registered, run 2026-10-26)

Pre-registration: `docs/preregistration/local-whole.md` + `local-whole.json` (frozen before the first call). Run 20261025T234252, log `logs/local-whole.jsonl`. After the Nightshift 2026-10-26 release the local Lightning lane holds long prompts, so this repeats the local-mode test with no cut, on 20 new census-2 records (6 longer than 7,000 characters).

## Result

| Measure | Result |
|---|---|
| Gate (~13,000-token local job) | passed: local-runtime/nemotron-3.5-lightning-30b-a3b, 12.4 s |
| Records | 20 (0 failures) |
| First reads local by the frozen checklist and answered by local Lightning | **20 of 20** |
| Reports sent whole | **20 of 20** (longest 13,003 characters) |
| Local first-read closings vs the census's cloud closings | 10 agree, **0 disagree**, 3 unconfirmed |
| Records settled by the local first read (report only) | 6 of 20 |
| **Claim** | **met** |

Prediction (before the run): "Before the run, by the coding agent: gate passes (local Lightning answers ~13k tokens); 20 of 20 first reads local by the checklist and answered by local Lightning; 20 of 20 reports sent whole (6 longer than 7,000 characters); 0 disagreements with the census's cloud closings; the local first read settles about 8-12 of 20 (report only); 0-2 failures. Claim likely met. Precondition: the Bolt lane is removed, or every read fails the frozen lane check."

## What it means, and what it does not

- Only the first read is local; what it does not settle goes to the cloud deep read as shipped.
- A first attempt crashed after 7 of 20 records on a bug in our scoring code (a record with no census closing); no result was computed, its 7 rows are kept in `logs/local-whole-crashed.jsonl` (7 of 7 local and whole, 0 disagreements), and the fix is disclosed in the pre-registration's addendum.
- The local first read settled fewer records than predicted (6 against 8-12): the settled count is report only.
- The window grew after the sponsor's release and a lane restart; we did not change any setting (`logs/probe-nightshift-update-2026-10-26.txt`).
- The referee is the census's cloud chain on the same records, not a fresh paired run. One run, no re-run.
- The Bolt lane was removed before the run; with it on, local jobs resolved two lanes and the frozen checklist failed.
- Lengths are in characters; token counts in the probes were estimates (characters / 5).
- What "local" rests on: Nightshift's own job record (privacy, lanes, model, egress). Local reads carry no Ed25519 signature, and the local checklist does not check context sources.
- Correction to the pre-registration's wording: it cites rising GPU memory in the probe log; that sample was observed in the session and saved afterwards to `logs/probe-gpu-sample-2026-10-26.txt`, not tied to a job id.
