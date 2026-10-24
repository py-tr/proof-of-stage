# The product vs Nemotron alone vs the rule alone, against blind labels (pre-registered, scored 2026-10-24)

Pre-registration: `docs/preregistration/baseline-m0.md` + `baseline-cases.json` (commit e48e295, frozen before the M0 run); the M0 log was committed unread (a542e8c) before the labels existed. Labels: `docs/preregistration/ground-truth-labels.json` (frozen bcb11ae, sha16 caef98991d916a90; how they were made: the dated note in baseline-m0.md). Scores: `logs/label-scores.json` (`python -m app.cli labels score`).

## Result (agreement with the blind label: which registry field the report contradicts, or "a person decides")

| Method | All 25 cases | Without the 3 disclosed cases |
|---|---|---|
| **A0, the product** (the guarded ladder; `stage_check.fault_field`) | **18 / 25** | **16 / 22** |
| M0, Super VL alone, 4k thinking, no guard | 17 / 25 | 15 / 22 |
| M0, Super VL alone, thinking off | 9 / 25 | 8 / 22 |
| B0, the count rule alone (always "the N category is wrong") | 7 / 25 | 7 / 22 |

M0 answered every case in both arms (0 provider failures, 0 unusable); its quote was in the report for 25 of 25 at 4k and 24 of 25 with thinking off.

Kill line: "the guard buys provenance, not accuracy" is stated if M0-4k agrees with the labels on at least as many cases as A0: **not met** (17 < 18). Prediction (before the run): "A0 > M0-4k > M0-off, B0 lowest": **held**.

## What it means, and what it does not

- On accuracy the product and Super-with-thinking are within **one case** of 25; that gap is not meaningful at this size. Thinking matters a lot (17 against 9), and the rule alone is far behind (7). What the product adds beyond Super alone is not measured accuracy here: every accepted value carries a quote the guard located and checked, a signed receipt, and an append-only record a person can audit.
- The labeller is one lay reader (the builder), not a pathologist, and the decision standard used is close to `fault_field`'s own logic (disclosed before scoring), which favours agreement with the product.
- Where the product and the label differ (7 cases): TCGA-A1-A0SN, AC-A2FK, BH-A0BS, E2-A1LI, E9-A3X8 (the label says a person decides; the product named a field) and AN-A0XN, AN-A0XW (the label says the count field; the product says the N field). The per-case table for all four methods is in `logs/label-scores.json` (`baseline_all.per_case`). No label was changed after scoring.
