# The part-aware count on three sets (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/parts-bench.md` + `parts-bench.json` (frozen before the first call). Run 20261025T181620, log `logs/parts-bench.jsonl`, envelopes `docs/evidence/attest/parts-bench-envelopes.jsonl`. `app/reader/parts.py`: Super VL lists every specimen part with its own quote; code checks each quote with the shipped rules, drops the other breast using the GDC record's side, takes a labelled total if verified, else adds the parts. 83 records, 0 provider failures.

## Result

| Set | Result | Claim |
|---|---|---|
| A, designed on (census-2 hits; disclosed) | fallen fields fixed **8 of 11**; standing fields kept **8 of 12** | not met |
| B, blind labels (25 queue records) | count correct **12**, wrong **2**, open 4 (shipped deep read: 16 / 0 / 1) | not met |
| C, regression (40 multi-part records the shipped reader agreed on) | new disagreements with the registry **0 of 40** | met |

How each count was reached: no_verified_part 20, parts_sum 18, single_part 13, stated_total 32. A `parts_sum` is a value no single quote shows: the product would show the parts to a person.

Prediction (before the run): "Before the run, by the coding agent: A: 8-10 of 11 fallen fixed (the 5 per-part and 2 bilateral mostly fixed; the per-level and N-from-count cases may not be) and 9-11 of 12 standing kept (claim likely met, weak evidence since designed on); B: 14-16 correct, 0-2 wrong (claim uncertain; the list format may lose a labelled total on some reports); C: 1-4 new disagreements (claim uncertain: summing parts can double-count restatements); 0-3 provider failures."

## Set A field by field

| Case | Field | Registry → census reading | Review | New value | How | OK |
|---|---|---|---|---|---|---|
| TCGA-A2-A1G4 | NPOS | 2 → 1 | stands | 1 | stated_total | yes |
| TCGA-A2-A25B | NPOS | 2 → 1 | falls | 2 | parts_sum | yes |
| TCGA-AC-A3EH | NPOS | 12 → 3 | stands | 3 | stated_total | yes |
| TCGA-AN-A0XV | N | N2 → N1 | stands | open | no_verified_part | no |
| TCGA-AO-A03L | N | N2 → N1A | falls | N1 | parts_sum | no |
| TCGA-AO-A03L | NPOS | 4 → 3 | falls | 3 | parts_sum | no |
| TCGA-AO-A1KQ | NPOS | 2 → 1 | falls | 1 | stated_total | no |
| TCGA-AR-A254 | NPOS | 9 → 7 | falls | 9 | parts_sum | yes |
| TCGA-AR-A2LN | N | N0 → N1A | stands | N1 | parts_sum | yes |
| TCGA-AR-A2LN | NPOS | 0 → 1 | stands | 1 | parts_sum | yes |
| TCGA-AR-A5QM | N | N0 → N2 | falls | N0 | parts_sum | yes |
| TCGA-AR-A5QM | NPOS | 0 → 4 | falls | 0 | parts_sum | yes |
| TCGA-BH-A0B5 | NPOS | 5 → 6 | stands | 6 | stated_total | yes |
| TCGA-BH-A0B7 | NPOS | 1 → 3 | stands | 3 | stated_total | yes |
| TCGA-BH-A0BD | NPOS | 2 → 1 | unsure | 1 | single_part | - |
| TCGA-BH-A18H | N | N0 → N1A | falls | N0 | single_part | yes |
| TCGA-BH-A18H | NPOS | 0 → 2 | falls | 0 | single_part | yes |
| TCGA-E2-A108 | NPOS | 4 → 5 | stands | 5 | stated_total | yes |
| TCGA-E2-A154 | N | N0 → N1C | stands | N2 | parts_sum | no |
| TCGA-E2-A154 | NPOS | 0 → 2 | stands | 4 | parts_sum | no |
| TCGA-EW-A1IZ | NPOS | 5 → 4 | stands | 4 | stated_total | yes |
| TCGA-EW-A1P5 | NPOS | 3 → 1 | stands | open | no_verified_part | no |
| TCGA-GM-A4E0 | N | N3A → N2A | falls | N3 | parts_sum | yes |
| TCGA-GM-A4E0 | NPOS | 10 → 9 | falls | 10 | parts_sum | yes |

## What it means, and what it does not

- The finding: structure plus code fixes the traps it targets and costs accuracy elsewhere. On the designed-on set it fixed 8 of the 11 readings that fell, including both other-breast readings (TCGA-AR-A5QM, TCGA-BH-A18H: the GDC side dropped the other breast) and 3 of the 5 per-part sums (TCGA-A2-A25B, TCGA-AR-A254, TCGA-GM-A4E0), but it lost 4 standing readings: it added a restated total as a part (TCGA-E2-A154: 2 became 4) or left a field open. On the blind labels it was worse than the shipped deep read (12 correct, 2 wrong, 4 open against 16, 0, 1): one wrong was a single part taken alone (TCGA-AC-A2FK), one an added restatement (TCGA-AO-A03P). On 40 multi-part records the shipped reader agreed on, it caused 0 new disagreements.
- So the shipped reader stays; the part-aware read is a measured design note: list parts with quotes and add them in code where a report has separate specimens and no stated total, and never add a part that restates a total.
- Set A was designed on (the fix was written after reading these failures), so a pass there is weak evidence; sets B and C carry the claim.
- Not wired into the shipped chain; the shipped reader and its Limits line stand unless a later, separately pre-registered change says otherwise. One run, no re-run.
