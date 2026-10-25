# Pre-registration: the deep read on this PC (written 2026-10-26, frozen before the first call)

`python scripts/local_deep_run.py run` refuses to run if `app/engine/local_deep.py` or a module it reuses (`local_whole.py`, `local_r1.py`, `reader_bench.py`, `reader.py`, `quotes.py`) differs from the hashes in `local-deep.json`, if the bench cases changed, if the prediction is not written, or if it has run once.

## Why (disclosed)

- **The deep-read bench** (`docs/evidence/reader-bench-results.md`, which stands) read the 25 review-queue reports at a 4k thinking budget through Nightshift. Results against the builder's labels and the independent second labeller:
  - cloud Lightning: 24 correct / 3 wrong, and 25 / 2;
  - Super VL: 32 / 3, and 33 / 2;
  - Ultra: 32 / 4, and 33 / 3.
- **The Nightshift 2026-10-26 release changed what the local lane can do.** After a restart, the local Lightning lane on this 16 GB GPU holds ~13,000-token prompts and honours a thinking budget: about 28 s at 256 against 71 s at 2,000 on the same question (`logs/probe-nightshift-update-2026-10-26.txt`).
- **The question is what moving the deep read onto this PC costs.** Designed tonight, after those probes. This is a measurement of the local lane, not a new seat: Super keeps the deep read unless a later decision says otherwise.

## Design

- **Cases:** the bench's 25 frozen cases.
- **Unchanged from the bench:** the report text (the first 32,000 characters, as in the bench), the system prompt, the 4k thinking budget, the guard (each value's quote checked against the full report), and the scoring rules (correct accepts, wrong accepts, not accepted; N by its main category).
- **Reader:** local Lightning through Nightshift's Jobs API, `"privacy": "local-only"`, thinking on.
- **Every read must pass the frozen local job checklist** (lanes resolved exactly the local Lightning lane, local model, model and egress honoured, not truncated) **and be answered by `local-runtime/nemotron-3.5-lightning-30b-a3b`.**
- **Scored against both frozen label sets**, whose hashes are recorded in the json.
- **Gate:** one ~13,000-token local job first. If it is refused or not answered by local Lightning, the run is void.
- Nothing is stored.

## Claim, kill, void

- **Claim:** every read local and answered by local Lightning, and against both labellers, local Lightning's wrong accepts are no more than cloud Lightning's (3 builder, 2 second).
- **Kill:** any read not local or not local Lightning, or 5 or more wrong accepts against either labeller.
- **Void:** the gate fails, or more than 8 of 25 provider failures. Never re-run.
- **Reported, not claimed:** correct accepts, not accepted, seconds per read. Correct accepts are expected below Super's: that gap is what a bigger local machine would be needed to close, and it stays an untested inference.

## Prediction

In the json, written before the run.

## Addendum (2026-10-26, before any call of this test)

This test reuses the gate and the model check from `app/engine/local_whole.py`. That module was fixed after its own first run crashed on a scoring bug (see `local-whole.md`, addendum), so this pre-registration is re-frozen with the new hash. This test's code, cases, bar, kill, void and prediction are unchanged, and it has made no call.
