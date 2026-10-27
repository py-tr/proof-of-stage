# IRS Form 990-EZ paper returns at read level: results (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/irs-read.md` + `irs-read.json` (commit 4ad3516, re-frozen before any call in da3f42c: the line label became a requirement). Run 20261025T134720, log `logs/irs-read.jsonl`, summary `logs/irs-read-runs.jsonl`, envelopes `docs/evidence/attest/irs-read-envelopes.jsonl`. Population: 2016 SOI extract, 990-EZ paper returns whose line 9 − 17 ≠ 18 by $2 or more (1,523 after dedup; e-filed ~0); 16 drawn (seed 20261025); 11 returns found in Candid's public archive (5 not in the archive); page-1 text layer read by Super VL through Nightshift (signed); the code check requires the quote verbatim in the text, the line's label in the quote and the amount in the quote.

## Result (as pre-registered)

| Measure | Result |
|---|---|
| Returns read cleanly (lines 9, 17, 18 all accepted) | **2 of 16** (5 had no document) |
| Verdicts | "the return itself does not add up" 1, "record matches return" 1, "not read" 14 |
| "The record contradicts the return on one field" | 0 |
| Provider failures | 0 |
| **Claim** (≥ 8 read cleanly and ≥ 3 contradicts) | **not met** |

Prediction ("6–9 of 11 read cleanly; claim about one in three"): did not hold.

## Why (from the log)

The text layer is the archive's OCR of scanned paper returns, not typed text: amounts come with split digits and dropped decimal points, so on most returns the reader returned no quotable amount or an amount the code check could not find intact in its quote (reasons in the log: no_amount, amount_unparseable, amount_not_in_quote). The design-time example (EIN 352517049, a keying error the return names) was a clean page; the drawn sample mostly was not.

## What it means

The cross-field rule finds impossible paper-return records at scale (1,523 in one year; ~0 e-filed), but on these OCR text layers the quote-checked reading does not work as built. No claim stands for this domain. Not tested: Parse or Super VL on the page image of these typed returns. No re-run.
