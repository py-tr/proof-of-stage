# Pre-registration: Nemotron 3.5 Bolt at the first read (written 2026-10-25, frozen before the first call)

`python scripts/bolt_r1_run.py run` refuses to run if `app/engine/bolt_r1.py`, `rungs.py`, `run_case.py`, `dial.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `bolt-r1.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

NVIDIA's guidance routes execution down to the smallest model that does the job. Lightning holds the first read: it settled 17 of 30 of these records today, with 0 of 36 closings contradicted. Bolt (E4B) is the edge-sized Nemotron. Councils 15 and 17 asked whether it can take the first read one size down. Two probes, not claims, confirmed the endpoint and the JSON format (TCGA-E2-A572: N2 closed, the count left open). Designed after the shipped-cost run; disclosed.

## Design

- The shipped evidence chain's first read only (`rungs.climb(..., abort_after=1)`), with its closing rule unchanged: the first read may close only a field that agrees with the registry. Bolt takes Lightning's place, thinking off, NVIDIA direct.
- Nightshift has no Bolt lane, so even a pass cannot ship under decision 0004. A pass reads as "an edge candidate, measured".
- **Records:** the dial test's 30 frozen records, the ones the shipped-cost run read today.
- **Referee:** that run's logged always-4k Super VL read per record. No new referee calls.
- **Comparator:** that run's Lightning first read (17 settled, 36 closings, 0 contradicted).
- Nothing is stored.

## Claim, kill, void

- **Claim:** Bolt settles at least 14 of 30 records at the first read, with 0 closings contradicted by the 4k read.
- **Kill:** fewer than 12 settled, or any closing contradicted. The "Not used" row then gets the measured numbers.
- **Void:** more than 5 provider failures. Never re-run.

## Prediction

In the json, written before the run.
