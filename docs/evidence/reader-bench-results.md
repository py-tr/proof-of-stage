# Which Nemotron should do the deep read? Results (pre-registered, scored 2026-10-24)

Pre-registration: `docs/preregistration/reader-bench.md` + `reader-bench.json` (commit 1f9b63f, frozen before the first call and before the labels), with its dated addendum (the second-reader measure, committed 92e0d51 before the labels). Run log committed unread (4645685): 74 of 75 reads answered (Super 1 Nightshift 502, TCGA-AR-A1AT), every answer signed by the pinned key. Labels frozen bcb11ae. Scores: `logs/label-scores.json`.

## Result: accepted values against the blind labels (N by main category; the count as an integer)

| Model at the deep read | Correct accepts | Wrong accepts | N: correct / wrong / not accepted (of 21) | Count: correct / wrong / not accepted (of 17) | Completion tokens |
|---|---|---|---|---|---|
| Lightning (4k budget) | 24 | 3 | 13 / 3 / 5 | 11 / 0 / 6 | 101,184 |
| **Super VL (4k budget, today's R2)** | **32** | **3** | 16 / 3 / 2 | 16 / 0 / 1 | 77,212 |
| Ultra (thinking on, no budget: the hosted Ultra rejects one) | 32 | 4 | 16 / 4 / 1 | 16 / 0 / 1 | 47,654 |

Decision rule (fixed before the run): the seat moves only to a model with more correct accepts than Super and no more wrong ones. **Super keeps the deep read.** Prediction ("Super and Ultra about the same correct; Lightning fewer; the seat stays with Super") **held**.

Every wrong accept is an N category (no wrong counts for any model); Ultra reached the same correct count with fewer tokens but one more wrong N.

## Addendum: the reads as an independent second reader of the stored values

| Model | Disagreements with the stored value | Right (the label agrees with the disagreement) | Wrong | Missed (the label disputes the stored value, the model did not) |
|---|---|---|---|---|
| Lightning | 0 | 0 | 0 | 4 |
| Super VL | 1 (TCGA-A1-A0SN, N2 -> N1) | 1 | 0 | 3 |
| Ultra | 0 | 0 | 0 | 4 |

Blind second readings almost never disagree with the stored values (which came from Super's own guarded reads); where the labels dispute a stored value (4 fields), only one blind read disagreed, and it was right.
