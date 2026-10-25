# ClinicalTrials.gov read v2: widened cue vocabulary on 30 new records (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/ctgov-read-v2.md` + `ctgov-read-v2.json` (frozen before the first call). Run 20261025T202433, log `logs/ctgov-read-v2.jsonl`, envelopes `docs/evidence/attest/ctgov-read-v2-envelopes.jsonl`. Designed after v1's miss (`docs/evidence/ctgov-read-results.md`, which stands); only the quote check's cue vocabulary changed, measured on records v1 never saw.

## Result

| Measure | Result |
|---|---|
| Records | 30 (1 provider failures) |
| Field named by the reader | model 25, no parsable answer 3, unclear 1 |
| **Model field named with a verified quote** (bar 24) | **22 of 30** |
| Allocation field named with a verified quote (bar at most 2) | 0 |
| The same answers under v1's narrower check | 19 of 30 |
| Model answers the check turned away, by reason | quote_lacks_randomized_groups_cue 3 |
| **Claim** | **not met** |

Prediction (before the run): "Before the run, by the main session: on v1's records the widened check would have accepted 21 of 30 (14 + 7 of the 9 rejected), still under the bar of 24; on new records expect about 19-25 model fields verified, 0-1 allocation, 0-2 failures. Claim uncertain, leaning not met; kill unlikely."

## What it means, and what it does not

- The vocabulary was widened after reading v1's rejected quotes; the bar and everything else stayed as in v1, and v2 was measured once, on new records.
- Read by hand after the run: of the 3 model answers turned away, 2 are correct statements the cue list still misses ("comparative study of X to Y", "compared to patients receiving only") and 1 quotes only the arm descriptions (correctly rejected). With those 2 the reader would reach 24, the bar; the check as frozen gives 22, so the claim is not met.
- 3 answers had no parsable field and 1 call failed (a Nightshift 502); none was re-run.
- Across v1 and v2 the reader named the allocation field, the wrong one, on 0 of 60 multi-arm records.
- For multi-arm records the arm count alone already points at the model field; the quote adds documentary proof, not new information.
