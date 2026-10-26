# The deep read on this PC: void (pre-registered, run 2026-10-26)

Pre-registration: `docs/preregistration/local-deep.md` + `local-deep.json` (frozen before the first call). Run 20261025T235715, log `logs/local-deep.jsonl`, run record `logs/local-deep-runs.jsonl`.

## Result: void

- **The gate passed:** a ~66,000-character local job, thinking off, was answered by local Lightning.
- **Every deep read errored:** 17 of 17 attempted reads (thinking on) failed. The run was stopped by hand once the pre-registered void condition (more than 8 of 25 provider failures) was already met; the remaining 8 reads could not change the outcome. No accuracy was measured.

## Why (from Nightshift's own job events, read after the run)

- Each failed job made two attempts. Each attempt ended after about 80-90 seconds with `local-runtime/nemotron-3.5-lightning-30b-a3b_empty_response`: no answer was produced.
- A follow-up demonstration (not pre-registered, `logs/local-think-demo-2026-10-26.jsonl`) gave three of the shortest queue reports (489 characters) thinking on and a 15,318-token output cap: all three failed the same way after about 72 seconds per attempt. So the output cap is not the cause: this Nightshift release appears to end a local attempt after roughly 70-90 seconds, and a thinking read of a real report does not finish within that. Thinking-off reads finish in seconds, which is why the local first read works. The local job records live in Nightshift's runtime folder, not in this repository.
- **Correction to the pre-registration's "why":** it says the local lane "honours a thinking budget (about 28 s at 256 against 71 s at 2,000)". That inference was wrong. Those two probes also had different output caps (3,256 and 5,000 tokens), which explain the timing. Whether the local lane enforces a numeric budget is untested; either way, a thinking read of a real report does not finish within this release's local attempt time.
- Super VL keeps the deep read in the cloud. A local deep read stays untested.
- One more check (2026-10-26 ~03:50, logged in `logs/probe-nightshift-update-2026-10-26.txt`): Nightshift's Preferences say a thinking budget is sent to Lightning only if one is set there ("budget not verified"). With it set to 1,024, two local thinking reads (489 and 4,840 characters) still failed the same way, so that setting does not make a local thinking read finish on this build. The setting was put back afterwards.
