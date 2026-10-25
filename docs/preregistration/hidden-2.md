# Pre-registration: hidden errors, second census of 300 consistent records (written 2026-10-25, frozen before the first call)

`python scripts/hidden2_run.py` refuses to run if `app/engine/hidden2.py`, `hidden.py`, `rungs.py`, `run_case.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `hidden-2.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

The first hidden-errors test read 60 records the cross-field rule calls consistent and found 1 whose report contradicts the registry (TCGA-A2-A25D: 23 vs 22, confirmed by the builder's lay read); the 95% interval was 0.04–9%. This second census narrows it. Proposed by a council (council 11) after the first result; same question, same reader, new records.

## Design

- **Population** (same rule as the first test): stage_check records with `reason_class = consistent`, edition 6th or 7th, a recorded N other than NX, a recorded count, report text, never read by any committed run log: **528** (639 consistent, 618 with report text, 90 already read). **Sample: 300**, `random.Random(20261025)`, ids frozen in the json.
- **Reader:** `hidden.run_one` unchanged: the evidence steps through Nightshift (first read Lightning thinking off, which may only clear a field agreeing with the registry; deep read Super VL at a 4k budget; scan read where parsed), signed receipts; nothing stored. Every envelope kept (`docs/evidence/attest/hidden-2-envelopes.jsonl`).
- **Hit:** a record with a closed field whose value differs from the registry (N by main category, count as an integer), listed with the registry value, the report value, the step and the accepted quote.

## Measures, claim, void

- **Primary:** records with a hit, of the scored records; split by field.
- **After the run (not pre-registered as a measure):** the builder reads each hit's report as a lay reader and says whether it stands; only standing hits are called contradictions. If at least 240 records are scored, the 95% Wilson interval over the 360 records of both censuses is stated for standing hits; never called "the registry's error rate".
- **Void:** more than 100 provider failures. Never re-run.

## Prediction

In the json, written before the run.
