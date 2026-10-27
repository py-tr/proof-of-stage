# A second cancer type: the impossible colorectal records, read once (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/colon-read.md` + `colon-read.json` (commit 051e580, frozen before the first call). Run 20261025T134109, log `logs/colon-read.jsonl`, summary `logs/colon-read-runs.jsonl`, envelopes `docs/evidence/attest/colon-read-envelopes.jsonl`. Population: 592 TCGA-COAD/READ cases with a recorded N and count (GDC API); 10 impossible under the paraphrased colon count rule (N1c with 0 nodes not counted); 8 with a report, all read once by Super VL through Nightshift with a colorectal version of the reader's prompt and the reader's own guard.

## Result (as pre-registered)

| Case | Registry | Verdict | Accepted reading |
|---|---|---|---|
| TCGA-A6-2671 | N2, 3 positive | **the report contradicts the stage field** | count 3: "Metastatic carcinoma in three of 27 lymph nodes (3/27" |
| TCGA-AF-2690 | N2, 3 positive | the report contradicts the stage field (see below) | count 3: "… three of twenty-four regional lymph nodes, pN2" |
| TCGA-AA-3672, TCGA-AA-A02E, TCGA-AD-6964, TCGA-CI-6621 | N1/4, N1/4, N2b/0, N1/0 | a person decides | reader declined, or the guard rejected the quote (too short; count not in quote) |
| TCGA-BM-6198, TCGA-EI-6511 | N1/0, N1/4 | not read | Nightshift 502 (provider failure; not void, not re-run) |

**Claim** (a field named on at least half of the records read): **not met**: 2 of 6. Prediction ("5–7 of 8 named"): did not hold.

## What a look at the two named records showed (after the run)

- **TCGA-A6-2671** is a clean finding: the report states 3 of 27 positive nodes, which is N1 under the count rule; the registry records N2.
- **TCGA-AF-2690 is not:** the accepted quote itself prints "pN2" next to "three of twenty-four". The pathologist staged it N2 (perhaps for a reason outside the count, such as tumour deposits); the guard accepted the reader's N1B from a quote that shows a different category. That is a gap in the guard for N (it checks that the quote supports a category, not that it does not print a conflicting one), found here and disclosed; this record is counted as named only by the pre-registered rule.

## What it means, and what it does not

- The pattern finds impossible colorectal records at about the breast rate (10 of 592, about 2%), but on these 8 the reading settled only one cleanly; most reports did not give the reader a quote the guard accepts. The colorectal reports are less uniform than the breast ones, and the breast-built prompt and guard were reused with minimal changes.
- No claim that the product transfers to colorectal cancer stands. Not tested: a prompt and guard tuned to colorectal reports (that would be a new, designed-after test).
