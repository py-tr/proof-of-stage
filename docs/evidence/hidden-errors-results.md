# Hidden errors in records that look consistent: results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/hidden-errors.md` + `hidden-cases.json` (commit 2973ac6, frozen before the first call; the run checked the code hashes at start). Logs: `logs/hidden-errors.jsonl` (one row per record), `logs/hidden-errors-runs.jsonl` (the summary), `logs/hidden-errors-2026-10-23.txt`, the rungs in `logs/markovian-chunks.jsonl` (run ids `hidden-…`). Run 2026-10-23 19:44 UTC.

## Validity

60 of 60 records run, one after another, through Nightshift with signed receipts (R1 Lightning, R2/R3 Super VL); 0 provider failures. **Not void.**

## Result

| Measure | Result |
|---|---|
| **Records whose closed value contradicts the registry** | **1 of 60** (TCGA-A2-A25D) |
| Contradicting fields | 0 N, 1 count; the count stays in the registry's N category (22 and 23 are both N3), so the cross-field rule cannot see it |
| Records fully settled (both fields closed) | 41 of 60; the other 19 have at least one field left to a person |
| Conflicts (two rungs accepting different values) | 0 |

Prediction (before the run): "1 to 4 of the 60 records contradict the registry on at least one field, mostly counts that stay in the same category." **Held** (1, a count in the same category).

## The hit, checked against the whole report

TCGA-A2-A25D: the registry records **22** positive nodes. The ladder's 4k rung (Super VL, Nightshift, signed) accepted 23 from the final diagnosis: "LYMPH NODES: TWENTY-THREE (23) LYMPH NODES POSITIVE FOR METASTATIC. CARCINOMA (SEE PARTS "B" AND "C")", with "AJCC PATHOLOGIC STAGE (7TH EDITION): pT2 N3a". Read against the full report (by Claude, the coding agent, before writing this file): part B, the highest axillary node, is "ONE (1) LYMPH NODE POSITIVE"; part C, the dissection, is "(22) OF TWENTY-THREE (23) LYMPH NODES POSITIVE". 1 + 22 = 23: the registry's 22 matches part C alone and leaves out the separately submitted node of part B. This is a guarded reading checked by an AI agent, not by a pathologist.

Also seen, post-hoc and outside this sample (it is why the study was run): TCGA-AR-A24O in the dial test's data, registry 7, report "Multiple (6 of 17) left axillary lymph nodes are involved … (AJCC pN2)", the only node statement in that 820-character report; both counts are N2.

## What it means, and what it does not

- Records the cross-field rule calls consistent can still contradict their report: here 1 in 60, a per-part count taken for the total. The 25 impossible records are not the whole story, but 1 of 60 is one record: no rate is claimed (a 95% interval for 1/60 runs from about 0.04% to 9%).
- The ladder found it without being asked to look for errors: R1 (Lightning) could not clear the count because the reading disagreed with the registry, so the 4k rung read it and the guard accepted the quoted total.
- Nothing was stored; the record is not in the review queue, because the queue comes from the cross-field rule. Catching this kind of error in production needs the ladder on every record, which the project scoped out.
