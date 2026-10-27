# Which Nemotron should do the deep read? Results (pre-registered, scored 2026-10-24)

Pre-registration: `docs/preregistration/reader-bench.md` + `reader-bench.json` (commit 0ff703f, frozen before the first call and before the labels), with its dated addendum (the second-reader measure, committed 9562012 before the labels). Run log committed unread (fc30eaa): 74 of 75 reads answered (Super 1 Nightshift 502, TCGA-AR-A1AT), every answer signed by the pinned key. Labels frozen 16a2071. Scores: `logs/label-scores.json`.

## Result: accepted values against the blind labels (N by main category; the count as an integer)

| Model at the deep read | Correct accepts | Wrong accepts | N: correct / wrong / not accepted (of 21) | Count: correct / wrong / not accepted (of 17) | Completion tokens |
|---|---|---|---|---|---|
| Lightning (4k budget) | 24 | 3 | 13 / 3 / 5 | 11 / 0 / 6 | 101,184 |
| **Super VL (4k budget, today's R2)** | **32** | **3** | 16 / 3 / 2 | 16 / 0 / 1 | 77,212 |
| Ultra (thinking on, no budget: the hosted Ultra rejects one) | 32 | 4 | 16 / 4 / 1 | 16 / 0 / 1 | 47,654 |

Decision rule (fixed before the run): the seat moves only to a model with more correct accepts than Super and no more wrong ones. **Super keeps the deep read.** Prediction ("Super and Ultra about the same correct; Lightning fewer; the seat stays with Super") **held**, except one clause: see the correction below.

Every wrong accept is an N category (no wrong counts for any model); Ultra reached the same correct count with fewer tokens but one more wrong N.

## Addendum: the reads as an independent second reader of the stored values

| Model | Disagreements with the stored value | Right (the label agrees with the disagreement) | Wrong | Missed (the label disputes the stored value, the model did not) |
|---|---|---|---|---|
| Lightning | 0 | 0 | 0 | 4 |
| Super VL | 1 (TCGA-A1-A0SN, N2 -> N1) | 1 | 0 | 3 |
| Ultra | 0 | 0 | 0 | 4 |

Blind second readings almost never disagree with the stored values (which came from Super's own guarded reads); where the labels dispute a stored value (4 fields), only one blind read disagreed, and it was right.

## Correction 2026-10-24: the prediction did not fully hold

The pre-registered prediction also said "wrong accepts are 0 or 1 for every model (the guard)". The result is 3, 3 and 4 wrong accepts (Lightning, Super, Ultra), so that clause **did not hold**, and the prediction as a whole did not hold. The parts about correct accepts and the seat did. The numbers above are unchanged.

## Sensitivity: three labels the labeller later confirmed as mis-clicks (disclosed 2026-10-24); frozen scores stand

After scoring, the labeller (the builder) confirmed that three labels were mis-clicks: TCGA-AN-A0XO's N was meant as pN1 (the label note says "fits N1"; pN2 was entered), and TCGA-AN-A0XN and TCGA-AN-A0XW were meant to name the N category, as their notes say (node count was entered). The pre-registration forbids relabelling, so the frozen labels and the scores above stand. Recomputed from the committed log with the same scoring code and those three labels corrected in memory only (the labels file is unchanged):

| Model at the deep read | Correct / wrong accepts (frozen) | Correct / wrong accepts (corrected labels) |
|---|---|---|
| Lightning | 24 / 3 | 25 / 2 |
| Super VL | 32 / 3 | 33 / 2 |
| Ultra | 32 / 4 | 33 / 3 |

The seat stays with Super either way. As second readers of the stored values, the models' misses go from 4 / 3 / 4 to 3 / 2 / 3 (Lightning / Super / Ultra); disagreements and right / wrong are unchanged.
