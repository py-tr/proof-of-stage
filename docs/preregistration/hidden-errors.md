# Pre-registration: hidden errors in records that look consistent (written 2026-10-23, frozen before the first call)

`python -m app.cli hidden` refuses to run if `app/engine/hidden.py`, `rungs.py`, `run_case.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `hidden-cases.json`.

## Question

The cross-field rule flags a record only when its N category and node count cannot both be true. A count that is wrong but stays in the same category (7 recorded, 6 in the report: both N2), or an N and a count that are wrong together, pass it. How often does a record that the rule calls consistent still contradict its own pathology report?

## Why now (disclosed)

The question came from a post-hoc look at the dial test's data (2026-10-23 evening): on 1 of its 28 scored consistent records (TCGA-AR-A24O) both the ladder and the independent 4k read accepted "Multiple (6 of 17) left axillary lymph nodes are involved … (AJCC pN2)" against a recorded count of 7. That record is not in this sample, and this run is the measurement; the observation is reported separately.

## Design

- **Population:** stage_check records with `reason_class = consistent`, edition 6th or 7th, a recorded N other than NX, a recorded positive-node count, report text, and never read by any logged run (ladder, dial, Lightning, red team): 588 records (2026-10-23).
- **Sample:** 60 records, `random.Random(20261024).sample(sorted(pool), 60)`; ids frozen in `hidden-cases.json`.
- **Reader:** the product's evidence ladder unchanged, through Nightshift with signed receipts: R1 Lightning with thinking off may only clear a field that agrees with the registry; R2 Super VL with a 4k budget, then R3 the scan where parsed, may close any value the guard accepts. Nothing is stored.
- Records run one after another.

## Measures (fixed now)

- **Primary:** records with at least one closed field whose value contradicts the registry (N by main category, the count as an integer), out of the scored records; each listed with the registry value, the report value, the rung and the accepted quote.
- Split by field: N contradictions and count contradictions; and how many count contradictions stay in the registry's N category (invisible to the cross-field rule).
- Records fully settled (no field open) and fields left open (to a person).

## Kill and void lines

- **Provider failure:** a record whose ladder run does not complete is listed by id and not scored. Never re-run.
- **Void** if more than 20 of the 60 are provider failures.
- No threshold makes the result "good" or "bad": the count is reported as it is, with its sample size. Every hit is a guarded reading, not ground truth: each is listed with its quote so a reader can check it, and none is called a registry error without that check.

## Prediction (before the run)

1 to 4 of the 60 records contradict the registry on at least one field, mostly counts that stay in the same category. A guess, written down so the result can contradict it.
