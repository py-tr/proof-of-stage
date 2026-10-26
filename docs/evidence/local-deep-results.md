# The deep read on this PC: void (pre-registered, run 2026-10-26)

Pre-registration: `docs/preregistration/local-deep.md` + `local-deep.json` (frozen before the first call). Run 20261025T235715, log `logs/local-deep.jsonl`, run record `logs/local-deep-runs.jsonl`.

## Result: void

- **The gate passed:** a ~66,000-character local job, thinking off, was answered by local Lightning.
- **Every deep read errored:** 17 of 17 attempted reads (thinking on) failed. The run was stopped by hand once the pre-registered void condition (more than 8 of 25 provider failures) was already met; the remaining 8 reads could not change the outcome. No accuracy was measured.

## Why (from Nightshift's own job events, read after the run)

- Each failed job made two attempts. Each attempt ended after about 80-90 seconds with `local-runtime/nemotron-3.5-lightning-30b-a3b_empty_response`: the model was still thinking when it reached the output cap, so no answer was produced. The local job records live in Nightshift's runtime folder, not in this repository.
- **Correction to the pre-registration's "why":** it says the local lane "honours a thinking budget (about 28 s at 256 against 71 s at 2,000)". That inference was wrong. Those two probes also had different output caps (3,256 and 5,000 tokens), which explain the timing. The local lane appears to accept thinking on or off but not a numeric budget, so a 4k-budget deep read like the cloud bench's cannot be run on it.
- Super VL keeps the deep read in the cloud. A local deep read stays untested.
