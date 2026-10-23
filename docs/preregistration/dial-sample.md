# Pre-registration: where the reasoning dial pays (written 2026-10-23, frozen before the first call)

`python -m app.cli dial` refuses to run if the code it measures (`app/engine/dial.py`, `rungs.py`, `run_case.py`, `app/reader/reader.py`, `quotes.py`) differs from the hashes in `dial-cases.json`.

## Question

On the 25-case review queue the thinking-off rung never settles a case (a contradiction case cannot agree with both registry fields), so there the ladder costs more than reading everything at a 4k budget. Does the dial pay on the records it is meant for, the ones whose registry fields agree with each other, and is the cheap read safe there?

## Design

- **Population:** stage_check records with `reason_class = consistent`, edition 6th or 7th, a recorded N, a recorded positive-node count and report text: 618 records (2026-10-23), none read by the model before.
- **Sample:** 30 records, `random.Random(20261023).sample(sorted(case_ids), 30)`; the ids are frozen in `dial-cases.json`.
- **Ladder:** the product's evidence ladder unchanged, through Nightshift (Super VL pinned in the signed receipt): R1 thinking off may close a field only if the read agrees with the registry and is self-consistent under the count rule; R2 a 4k budget for what is still open; R3 the scan if one was parsed. Nothing is stored.
- **Control:** one 4k-budget read of the same report through Nightshift on every record, nothing stored.
- Records run one after another; every call's receipt must verify against the pinned key.

## Measures (fixed now)

- Records settled at R1 (both N and the count closed by the thinking-off read) out of the scored records.
- Fields closed at R1, and for each the 4k control's verdict: **agree** (accepted, same value), **disagree** (accepted, other value) or **unconfirmed** (the control did not accept a value).
- Completion tokens and seconds: the ladder (all its rungs) against the control (always 4k), summed over the scored records, from Nightshift's usage.

## Kill and void lines

- **The cheap read is unsafe here** if the control disagrees with more than 10% of the fields R1 closed. Reported as the result, never re-tuned.
- **Provider failure:** a record whose ladder errors or whose control call still fails after the client's retries is reported by id and not scored. Never re-run.
- **Void** if more than 10 of the 30 records are provider failures; then only the per-record list is reported.

## Prediction (before the run)

At least half the scored records settle at R1, and the ladder uses fewer completion tokens than the always-4k control. A guess, written down so the result can contradict it.
