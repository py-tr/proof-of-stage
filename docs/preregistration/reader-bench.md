# Pre-registration: which Nemotron should do the deep read? (written 2026-10-23, frozen before the first call and before the blind labels are frozen)

`python -m app.cli reader-bench run` refuses to run if `app/engine/reader_bench.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `reader-bench.json`. `reader-bench score` also needs the frozen labels (`ground-truth-labels.json` and its `.sha16`, the same files the M0 baseline uses).

## Question

The deep rung (R2) reads what the cheap rung could not settle, with a 4k thinking budget, and today it is Super VL because 4k matched unlimited thinking on Super (`docs/evidence/thinking-budget.md`). No measurement compares the Nemotron models in that seat on the cases it exists for: the review queue. Which model, under the unchanged guard, accepts the most values that a blind human reader agrees with, without accepting more that the reader contradicts?

## Design

- **Cases:** the 25 review-queue cases (`baseline-cases.json`), the full report text each.
- **Models**, each once per case, the three reads of a case side by side, all through Nightshift (pinned in the signed receipt, cloud, verified against the pinned key, no cache), the reader's prompt and guard unchanged:
  - **Lightning** (`nvidia/nemotron-3.5-lightning-30b-a3b`), 4k thinking budget;
  - **Super VL** (`nvidia/nemotron-3.5-super-vl-120b-a12b`), 4k thinking budget (today's R2);
  - **Ultra** (`nvidia/nemotron-3-ultra-550b-a55b`), thinking on **without a budget**: the hosted Ultra rejects a reasoning budget ("thinking_token_budget is not yet supported", probe 2026-10-23), so its arm is not budget-matched; its completion tokens are reported.
- The readings are logged and committed **unread**; nobody looks at them before the labels are frozen.
- **Ground truth:** the same blind labels as the M0 baseline (one lay reader; the count and the printed N category per case).

## Measures (fixed now)

- Per model and field (N by main category, the positive-node count): **correct accepts** (accepted and the label agrees), **wrong accepts** (accepted and the label disagrees), **not accepted** (rejected or abstained), over the cases where the label states a value.
- Completion tokens and seconds per model; provider failures.

## Decision rule (fixed now)

- The deep-read seat moves from Super to another model only if that model has **more correct accepts** than Super **and no more wrong accepts**; a tie on correct accepts keeps Super; among models that pass, the one with the most correct accepts (fewer completion tokens break a tie).
- **Void arm:** more than 8 of 25 provider failures; that model cannot take the seat. Failures are listed, never re-run.
- Nothing is re-tuned after scoring.

## Prediction (before the run)

Super and Ultra accept about the same number of correct values; Lightning accepts fewer; wrong accepts are 0 or 1 for every model (the guard). The seat stays with Super. A guess.
