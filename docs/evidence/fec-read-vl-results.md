# FEC v2: Super VL reads the handwritten cash summary, the FEC database as second reader: results (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/fec-read-vl.md` + `fec-read-vl.json` (commit 7d406dd, frozen before the first call; designed after FEC v1 and a 3-page spike, disclosed). Run 20261025T124853, log `logs/fec-read-vl.jsonl`, summary `logs/fec-read-vl-runs.jsonl`. 24 fresh 2018 Senate paper filings; Nemotron Parse found the summary page; Super VL (NVIDIA direct) read lines 23–27 from the page image; each of lines 23, 24, 26, 27 compared with the value the FEC typed into its database from the same paper.

## Result (as pre-registered)

| Measure | Result |
|---|---|
| Filings read (page found and amounts in the answer) | **22 of 24** (0 provider failures) |
| Lines where Super VL and the database agree to the cent | **33 of 88** (37.5%) |
| Filings where all four lines agree | 0 |
| Filings with exactly one disagreement (to a person) | 5 |
| **Claim line** (≥ 16 read and ≥ 80% agreement) | **not met** |

Prediction ("18–22 read; ~80–90% agreement; claim likely met"): the reading count held, the agreement did not. The 3-page spike (two pages at 5 of 5) overestimated it.

## What the disagreements are (exploratory, classified after the run; not part of the claim)

| Kind | Lines |
|---|---|
| Exact agreement | 33 |
| The database has whole dollars where the form (as read) has cents, e.g. $2,279.00 vs $2,279.95 (the database's known cents-only class, `fec-rule-results.md`) | 15 |
| Super VL missed a handwritten decimal point (e.g. "22702" for $227.02) | 4 |
| Other: mostly extra or missing digits, consistent with Super VL reading box ticks or a "$" as digits ("910,351.04" vs $10,351.04, "882,123" vs $5,821), some possibly database errors | 34 |
| Unread | 2 |

## What it means, and what it does not

- On these boxed, mostly handwritten forms, Super VL's digit reading is not reliable enough to settle amounts on its own, and neither is the database (it truncates cents). The two-reader rule did what the product's rule does on the cancer registry: no amount was accepted unless both readers agreed, so the misreads were held back, not trusted.
- No claim about FEC at read level stands: v1 (text rules) and v2 (Super VL) both missed their pre-registered bars. The rule-level result (`fec-rule-results.md`) and v1's four looked-at pages (each filing's own arithmetic is wrong) are what this domain shows.
- Not tested: crops of single boxes, a higher resolution, two independent VL reads, typed (e-filed) forms. No re-run.
