# Hidden errors, second census: results (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/hidden-2.md` + `hidden-2.json` (commit 2cb8c97, frozen before the first call). Log `logs/hidden-2.jsonl`, summary `logs/hidden-2-runs.jsonl`, envelopes `docs/evidence/attest/hidden-2-envelopes.jsonl` (every signature checkable on `/receipts`). Lay reads `docs/evidence/hidden-2-lay-reads.json`.

## Validity

300 of 300 records run; 2 provider failures (void above 100): **not void**. 298 scored.

## Result

| Measure | Result |
|---|---|
| Records with a closed value that differs from the registry (a hit) | **18 of 298** |
| Fields | 8 N, 17 count |
| Records fully settled (both fields closed) | 208 of 298 |
| The read of each hit (provenance below) | stands 10, falls 7, unsure 1, not yet read 0 |

Prediction (before the run): "Before the run, by the coding agent: 1-6 records with a hit among ~295 scored (the first census found 1 of 60); most hits on the count field within the same N category; 0-5 provider failures; at least half the hits stand after a lay read."

Against the prediction: hits outside 1-6 (18: did not hold); provider failures 2 (held against 0-5); standing hits 10 of 18 (held against at least half).

**How each hit was read:** drafted by an AI assistant (Claude) from report excerpts, reviewed and confirmed by the builder (a lay reader, not a pathologist); disputed facts checked by code against the full report text and the GDC record. A hit is called a contradiction only when this read stands.

**Why the readings that fall, fall:** 5 took one part's node count for the total (a separately submitted sentinel node left out); 2 read the other breast in a bilateral case. Both are reader limits, now listed in Limits.

## Both censuses together

Standing contradictions: 11 of 358 consistent records read (1 of 60 in the first census, TCGA-A2-A25D; 10 of 298 here). 95% Wilson interval **1.7% to 5.4%**. This is the share of records the cross-field rule calls consistent whose report, read by this reader and one lay person, gives a different value; it is not the registry's error rate (one reader, one lay check, no pathologist; unsure hits are not counted; the first census's read was the builder's own, this census's was AI-drafted and builder-confirmed).

## Every hit, with its quote and the lay read

- **TCGA-A2-A1G4** (count): registry 2, reading 1 (step R2), quote “METASTATIC CARCINOMA TO 1 OF 15 AXILLARY LYMPH MODES”. Read (whole record): **stands**: count: the only positive count is '1 OF 15 AXILLARY'; the other node ('ONE LYMPH NODE … NO RESIDUAL NEOPLASM') is negative; registry 2
- **TCGA-A2-A25B** (count): registry 2, reading 1 (step R2), quote “METASTATIC BREAST CARCINOMA. IS IDENTIFIED IN 1 OF 6 LYMPH NODES EXAMINED”. Read (whole record): **falls**: per-part count: Part A sentinel 'ONE OF TWO' plus Part C '1 OF 6' = 2, the registry's value; the reading took Part C only
- **TCGA-AC-A3EH** (N category): registry N3, reading N1A (step R2), quote “Total number of lymph nodes containing metastatic carcinoma: 3”. Read (whole record): **stands**: count stands: 'Total number of lymph nodes containing metastatic carcinoma: 3' vs registry 12 (12 is nodes received); the N part falls: the report prints 'pTNM stage: pT3 N2', neither the registry's N3 nor the reading's N1A
- **TCGA-AC-A3EH** (count): registry 12, reading 3 (step R2), quote “Total number of lymph nodes containing metastatic carcinoma: 3”. Read (whole record): **stands**: count stands: 'Total number of lymph nodes containing metastatic carcinoma: 3' vs registry 12 (12 is nodes received); the N part falls: the report prints 'pTNM stage: pT3 N2', neither the registry's N3 nor the reading's N1A
- **TCGA-AN-A0XV** (N category): registry N2, reading N1 (step R2), quote “N Stage: 1”. Read (whole record): **stands**: N: the report prints 'N Stage: 1'; registry N2
- **TCGA-AO-A03L** (N category): registry N2, reading N1A (step R2), quote “LEVEL. I: 3/9; LEVEL II: 0/7”. Read (whole record): **falls**: per-part count: Part 1 sentinel positive plus Part 2 'LEVEL I: 3/9' = 4, which fits the registry's N2
- **TCGA-AO-A03L** (count): registry 4, reading 3 (step R2), quote “LEVEL. I: 3/9; LEVEL II: 0/7”. Read (whole record): **falls**: per-part count: Part 1 sentinel positive plus Part 2 'LEVEL I: 3/9' = 4, which fits the registry's N2
- **TCGA-AO-A1KQ** (count): registry 2, reading 1 (step R2), quote “METASTATIC CARCINONA IN ONE OF EIGHT LYMPH NODES (1/8”. Read (whole record): **falls**: per-part count: Part 1 sentinel (1/1) plus Part 2 (1/8) = 2, the registry's value
- **TCGA-AR-A254** (count): registry 9, reading 7 (step R2), quote “Multiple (7 of 28) left axillary lymph nodes are positive for metastatic carcinoma”. Read (whole record): **falls**: per-part count: sentinels '2 of 2' plus dissection '7 of 28' = 9, the registry's value
- **TCGA-AR-A2LN** (N category): registry N0, reading N1A (step R2), quote “One (of1) axillary sentinel lymph node is. positive for metastatic carcinoma, the largest measuring 2.0 cm”. Read (whole record): **stands**: bilateral: the GDC record (N0, 0 positive) is the right breast; the report's right side gives 1 of 15 positive, pN1 (printed pN1, not N1a)
- **TCGA-AR-A2LN** (count): registry 0, reading 1 (step R2), quote “One (of1) axillary sentinel lymph node is. positive for metastatic carcinoma, the largest measuring 2.0 cm”. Read (whole record): **stands**: bilateral: the GDC record (N0, 0 positive) is the right breast; the report's right side gives 1 of 15 positive, pN1 (printed pN1, not N1a)
- **TCGA-AR-A5QM** (N category): registry N0, reading N2 (step R2), quote “Multiple (4 of 25) right axillary lymph nodes are. positive for metastatic breast carcinoma [AJCC pN2”. Read (whole record): **falls**: bilateral, wrong breast: the GDC N0/0 record is the left breast, which matches the report's left side (pN0(i+)); the reading took the right side
- **TCGA-AR-A5QM** (count): registry 0, reading 4 (step R2), quote “Multiple (4 of 25) right axillary lymph nodes are. positive for metastatic breast carcinoma [AJCC pN2”. Read (whole record): **falls**: bilateral, wrong breast: the GDC N0/0 record is the left breast, which matches the report's left side (pN0(i+)); the reading took the right side
- **TCGA-BH-A0B5** (count): registry 5, reading 6 (step R2), quote “LYMPH NODES POSITIVE: 6”. Read (whole record): **stands**: count: 1/3 + 5/21 = 6, and the report states 'LYMPH NODES POSITIVE: 6'; registry 5
- **TCGA-BH-A0B7** (count): registry 1, reading 3 (step R2), quote “LYMPH NODES POSITIVE: 3”. Read (whole record): **stands**: count: 1/1 + 1/1 + 1/17 = 3, and the report states 'LYMPH NODES POSITIVE: 3'
- **TCGA-BH-A0BD** (count): registry 2, reading 1 (step R2), quote “AXILLARY SENTINEL LYMPH NODE #1 WITH FOCAL METASTATIC ADENOCARCINOMA (1/1”. Read (whole record): **unsure**: only sentinel #1 (1/1) mentions nodes; no other part or total; registry 2
- **TCGA-BH-A18H** (N category): registry N0, reading N1A (step R2), quote “METASTATIC CARCINOMA INVOLVES TWO OF TWENTY-FOUR LYMPH NODES (2/24”. Read (whole record): **falls**: bilateral, wrong breast: the GDC N0/0 record is the right breast, which matches the report's right side (0 positive, pN0); the left breast has its own record (N1a)
- **TCGA-BH-A18H** (count): registry 0, reading 2 (step R2), quote “METASTATIC CARCINOMA INVOLVES TWO OF TWENTY-FOUR LYMPH NODES (2/24”. Read (whole record): **falls**: bilateral, wrong breast: the GDC N0/0 record is the right breast, which matches the report's right side (0 positive, pN0); the left breast has its own record (N1a)
- **TCGA-E2-A108** (count): registry 4, reading 5 (step R2), quote “Lymph node status: Positive 5 /27”. Read (whole record): **stands**: count: 'Lymph node status: Positive 5 /27' is in the report; registry 4
- **TCGA-E2-A154** (N category): registry N0, reading N1C (step R2), quote “Pathological staging (pTN): pT 2 N 1c”. Read (whole record): **stands**: count: 'Positive 2/15' (1/12 axillary + 1/2 intramammary); N: the report prints 'pT 2 N 1c' (odd for an intramammary node, but printed); registry N0 / 0
- **TCGA-E2-A154** (count): registry 0, reading 2 (step R2), quote “Lymph node status: Positive 2/15 Extranodal extension”. Read (whole record): **stands**: count: 'Positive 2/15' (1/12 axillary + 1/2 intramammary); N: the report prints 'pT 2 N 1c' (odd for an intramammary node, but printed); registry N0 / 0
- **TCGA-EW-A1IZ** (count): registry 5, reading 4 (step R2), quote “Number of lymph nodes with macrometastases: 4”. Read (whole record): **stands**: count and N: 'four out of nine' + '0/4' = 4 of 13, macrometastases 4, pN2
- **TCGA-EW-A1P5** (count): registry 3, reading 1 (step R2), quote “Number of lymph nodes with macrometastases (>0.2 cm): 1”. Read (whole record): **stands**: count: synoptic macrometastases 1, pN1a; only 2 nodes examined, so the registry's 3 cannot be true
- **TCGA-GM-A4E0** (N category): registry N3A, reading N2A (step R2), quote “METASTATIC CARCINOMA IN NINE OF TWENTY-ONE LYMPH NODES”. Read (whole record): **falls**: per-part count: sentinel A one positive plus Part C 'NINE OF TWENTY-ONE' = 10, N3a, the registry's values
- **TCGA-GM-A4E0** (count): registry 10, reading 9 (step R2), quote “METASTATIC CARCINOMA IN NINE OF TWENTY-ONE LYMPH NODES”. Read (whole record): **falls**: per-part count: sentinel A one positive plus Part C 'NINE OF TWENTY-ONE' = 10, N3a, the registry's values

## What it means, and what it does not

- A hit is the reader's value against the registry's; it is called a contradiction only when the lay read stands. Hits that fall are the reader's errors and are counted against it, not the registry.
- Nothing was stored and no record was changed; these records are not in the review queue, because the queue comes from the cross-field rule.
- One reader, one lay person, no pathologist. No re-run.
