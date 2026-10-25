# Second labeller: the scorer, written before any second label exists (2026-10-25)

`docs/preregistration/second-labeller.md` says the second labels are scored "by the frozen scoring rules unchanged". The existing `app/engine/labels.py` only reads the first labeller's file, so the scorer for the second is a new module, written and committed before any second label exists:

- `app/engine/second_labeller.py` (sha16 `d25e2b460ccbf923` at this commit) and `scripts/second_labeller.py` (`freeze <labels.json>`, then `score`).
- It calls the frozen `baseline.score` and `reader_bench.score` unchanged. The product's verdict, Super alone (thinking off and 4k) and the rule alone are the per-case answers already recorded when the first labels were scored (`logs/label-scores.json`), so scoring is offline and calls no model.
- Check before any second label: scoring the first labels against themselves reproduces the published numbers exactly (product 18 of 25, Super alone 17, rule 7, thinking off 9; deep-read bench Super 32 correct / 3 wrong).
- Added measure, as pre-registered: Cohen's kappa between the two labellers over the three outcomes.
