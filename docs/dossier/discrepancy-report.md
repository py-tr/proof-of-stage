# Possible discrepancies in TCGA-BRCA clinical data (prepared, NOT sent)

> Draft for the NCI GDC help desk, to be sent by the project author after the hackathon judging, under their own name. Nothing here has been confirmed by GDC or by a pathologist.

Project TCGA-BRCA (GDC clinical data, 1,097 cases). Each record below has a recorded N stage and positive-node count that cannot both be true under the AJCC count ranges (paraphrased: N0 none, N1 1-3, N2 4-9, N3 10 or more), a sentence in the public pathology report that settles which field it contradicts (checked word for word by code), a signed re-read that reproduced it (2026-10-25), and a blind read by one lay reader that agrees. The 7 labelled records where the lay read differs from our reading (TCGA-A1-A0SN, TCGA-AC-A2FK, TCGA-AN-A0XN, TCGA-AN-A0XW, TCGA-BH-A0BS, TCGA-E2-A1LI, TCGA-E9-A3X8) are left out on purpose (two of them, TCGA-AN-A0XN and TCGA-AN-A0XW, are labelling mis-clicks the reader later confirmed; still left out).

## 14 records where the report contradicts one field

### TCGA-3C-AAAU: the N stage (N category)
- Registry: N NX; 4 positive of 13 examined (the count rule gives pN2a)
- Report: N N2A; 4 positive; N: "POSITIVE LYMPH NODES: TOTAL: 4 of 13" | NPOS: "POSITIVE LYMPH NODES: TOTAL: 4 of 13"
- Signed re-read receipts: rcpt_req_1d976kc1 rcpt_req_1d976kc1

### TCGA-A2-A0CV: the positive lymph node count
- Registry: N N1A; 4 positive of 18 examined (the count rule gives pN2a)
- Report: N N1A; 2 positive; N: "2/18) POSITIVE EXAMINED LYMPH NODES" | NPOS: "2/18) POSITIVE EXAMINED LYMPH NODES"
- Signed re-read receipts: rcpt_req_60s2249c rcpt_req_qzglnjj4

### TCGA-A7-A26E: the positive lymph node count
- Registry: N N1A; 0 positive of 16 examined (the count rule gives pN0)
- Report: N N1A; 1 positive; N: "As per parts A, C and E,. there are 16 1 mmnh nodes. one of which contains metastatic. carcinoma, l. Size of largest metastasis: 3 mm" | NPOS: "one of which contains metastatic. carcinoma, l"
- Signed re-read receipts: rcpt_req_i4gfhza7 rcpt_req_njrqb5c3

### TCGA-A7-A26H: the positive lymph node count
- Registry: N N1A; 0 positive of 5 examined (the count rule gives pN0)
- Report: N N1A; 1 positive; N: "Metastatic carcinoma is present in one lymph node" | NPOS: "Metastatic carcinoma is present in one lymph node"
- Signed re-read receipts: rcpt_req_gp07o70w rcpt_req_pm9ygs7c

### TCGA-AN-A0XO: the N stage (N category)
- Registry: N N2; 2 positive of 12 examined (the count rule gives pN1a)
- Report: N N1; - positive; N: "N Stage: 1"
- Signed re-read receipts: rcpt_req_fo7l5y7c

### TCGA-AN-A0XP: the N stage (N category)
- Registry: N N2; 1 positive of 19 examined (the count rule gives pN1a)
- Report: N N1; - positive; N: "N Stage: 1"
- Signed re-read receipts: rcpt_req_v3nz0s5o

### TCGA-AN-A0XS: the N stage (N category)
- Registry: N N2; 1 positive of 11 examined (the count rule gives pN1a)
- Report: N N1A; - positive; N: "N Stage: 1a"
- Signed re-read receipts: rcpt_req_hvoqrdwg

### TCGA-AN-A0XT: the N stage (N category)
- Registry: N N2; 1 positive of 17 examined (the count rule gives pN1a)
- Report: N N1A; - positive; N: "N Stage: 1a"
- Signed re-read receipts: rcpt_req_k5pjt7u6

### TCGA-AO-A1KP: the positive lymph node count
- Registry: N N1; 0 positive of 9 examined (the count rule gives pN0)
- Report: N N1A; 1 positive; N: "ONE LYMPH NODE POSITIVE FOR METASTATIC CARCINOMA (1/1) (SEE NOTE" | NPOS: "ONE LYMPH NODE POSITIVE FOR METASTATIC CARCINOMA (1/1"
- Signed re-read receipts: rcpt_req_bptyn2oy rcpt_req_ric23mor

### TCGA-AQ-A1H2: the positive lymph node count
- Registry: N N2A; 13 positive of 19 examined (the count rule gives pN3a)
- Report: N N2A; 7 positive; N: "Axillary lymph nodes: Total number with metastasis: 7. Total number examined: 10 (1 from part A, 9 from part B below" | NPOS: "Total number with metastasis: 7"
- Signed re-read receipts: rcpt_req_4ygun7f5 rcpt_req_4ygun7f5

### TCGA-BH-A0DD: the positive lymph node count
- Registry: N N1A; 0 positive of 22 examined (the count rule gives pN0)
- Report: N N1A; 1 positive; N: "LYMPH NODES POSITIVE: 1. LYMPH NODES EXAMINED: 23" | NPOS: "LYMPH NODES POSITIVE: 1"
- Signed re-read receipts: rcpt_req_a7j5f6e3 rcpt_req_eqdul0ad

### TCGA-E2-A1B4: the N stage (N category)
- Registry: N N2A; 3 positive of 4 examined (the count rule gives pN1a)
- Report: N N1MI; 3 positive; NPOS: "Lymph node status: Positive 3/4. Micrometastases" | N: "Micrometastases are identified in sentinel lymph nodes#1, #2 (AE 1/3 positive) and #4. The largest. tumor metastasis measures 2-mm"
- Signed re-read receipts: rcpt_req_r4lib2cn rcpt_req_abk6x7ye

### TCGA-E2-A572: the positive lymph node count
- Registry: N N2; 0 positive of 13 examined (the count rule gives pN0)
- Report: N N2A; 8 positive; N: "Lymph node status: Positive 8 / 13 Extranodal extension" | NPOS: "Lymph node status: Positive 8 / 13"
- Signed re-read receipts: rcpt_req_mgs6nxr6 rcpt_req_mgs6nxr6

### TCGA-EW-A424: the N stage (N category)
- Registry: N N1; 0 positive of 1 examined (the count rule gives pN0)
- Report: N N0; 0 positive; N: "Negative for carcinoma in one lymph node examined (0/1" | NPOS: "Negative for carcinoma in one lymph node examined (0/1"
- Signed re-read receipts: rcpt_req_elur1myn rcpt_req_elur1myn

## 4 records the report does not settle (listed for completeness)

- TCGA-A2-A0EW: registry N N3A; 26 positive of None examined; report N N2A; 4 positive
- TCGA-AO-A03P: registry N N1; 0 positive of 26 examined; report N N1MI; - positive
- TCGA-AR-A1AT: registry N N0; 1 positive of 3 examined; report N N0(I+); - positive
- TCGA-D8-A27L: registry N N2A; 2 positive of 16 examined; report N NX; - positive

## One record that passes every rule

### TCGA-A2-A25D: the positive lymph node count
- Registry: 22 positive nodes
- Report: final diagnosis: "TWENTY-THREE (23) LYMPH NODES POSITIVE FOR METASTATIC. CARCINOMA (SEE PARTS "B" AND "C")"; Part B 1 positive, Part C 22 of 23 positive
- Why: the registry records Part C's 22 and appears to miss Part B's 1; both 22 and 23 give the same N stage, so a stage rule cannot see it
- Source: docs/evidence/hidden-errors-results.md (lay read by the builder, 2026-10-24)


## More records that pass every rule (second census, 2026-10-25)

Each reading below was accepted by the code's quote check, and the record was reviewed: drafted by an AI assistant (Claude) from report excerpts, reviewed and confirmed by the builder (a lay reader, not a pathologist); disputed facts checked by code against the full report text and the GDC record. Only readings the review says stand are listed; 7 readings that fell and 1 left unsure are left out.

### TCGA-A2-A1G4
- positive lymph node count: registry 2, report reading 1; quote: "METASTATIC CARCINOMA TO 1 OF 15 AXILLARY LYMPH MODES"
- Review: count: the only positive count is '1 OF 15 AXILLARY'; the other node ('ONE LYMPH NODE … NO RESIDUAL NEOPLASM') is negative; registry 2

### TCGA-AC-A3EH
- positive lymph node count: registry 12, report reading 3; quote: "Total number of lymph nodes containing metastatic carcinoma: 3"
- Review: count stands: 'Total number of lymph nodes containing metastatic carcinoma: 3' vs registry 12 (12 is nodes received); the N part falls: the report prints 'pTNM stage: pT3 N2', neither the registry's N3 nor the reading's N1A

### TCGA-AN-A0XV
- N stage (N category): registry N2, report reading N1; quote: "N Stage: 1"
- Review: N: the report prints 'N Stage: 1'; registry N2

### TCGA-AR-A2LN
- N stage (N category): registry N0, report reading N1A; quote: "One (of1) axillary sentinel lymph node is. positive for metastatic carcinoma, the largest measuring 2.0 cm"
- positive lymph node count: registry 0, report reading 1; quote: "One (of1) axillary sentinel lymph node is. positive for metastatic carcinoma, the largest measuring 2.0 cm"
- Review: bilateral: the GDC record (N0, 0 positive) is the right breast; the report's right side gives 1 of 15 positive, pN1 (printed pN1, not N1a)

### TCGA-BH-A0B5
- positive lymph node count: registry 5, report reading 6; quote: "LYMPH NODES POSITIVE: 6"
- Review: count: 1/3 + 5/21 = 6, and the report states 'LYMPH NODES POSITIVE: 6'; registry 5

### TCGA-BH-A0B7
- positive lymph node count: registry 1, report reading 3; quote: "LYMPH NODES POSITIVE: 3"
- Review: count: 1/1 + 1/1 + 1/17 = 3, and the report states 'LYMPH NODES POSITIVE: 3'

### TCGA-E2-A108
- positive lymph node count: registry 4, report reading 5; quote: "Lymph node status: Positive 5 /27"
- Review: count: 'Lymph node status: Positive 5 /27' is in the report; registry 4

### TCGA-E2-A154
- N stage (N category): registry N0, report reading N1C; quote: "Pathological staging (pTN): pT 2 N 1c"
- positive lymph node count: registry 0, report reading 2; quote: "Lymph node status: Positive 2/15 Extranodal extension"
- Review: count: 'Positive 2/15' (1/12 axillary + 1/2 intramammary); N: the report prints 'pT 2 N 1c' (odd for an intramammary node, but printed); registry N0 / 0

### TCGA-EW-A1IZ
- positive lymph node count: registry 5, report reading 4; quote: "Number of lymph nodes with macrometastases: 4"
- Review: count and N: 'four out of nine' + '0/4' = 4 of 13, macrometastases 4, pN2

### TCGA-EW-A1P5
- positive lymph node count: registry 3, report reading 1; quote: "Number of lymph nodes with macrometastases (>0.2 cm): 1"
- Review: count: synoptic macrometastases 1, pN1a; only 2 nodes examined, so the registry's 3 cannot be true


Method and evidence: https://github.com/py-tr/proof-of-stage (README, docs/evidence/).
