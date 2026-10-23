# Pre-registration: Lightning as the cheap rung (written 2026-10-23, frozen before the first call)

`python -m app.cli lightning` refuses to run if `app/engine/lightning.py`, `rungs.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `lightning-cases.json`.

## Question

The ladder's first rung (R1) is Super with thinking off: on the dial test's 28 scored records it settled 15 and closed 31 fields, and the always-4k control contradicted none of them (`docs/evidence/dial-sample-results.md`). Can Nemotron Lightning (`nvidia/nemotron-3.5-lightning-30b-a3b`, 30B with 3B active), a much smaller model, do R1's job as safely, and for less?

## Design

- **Records:** the 28 records the dial test scored (ids frozen in `lightning-cases.json`; the 2 dial provider failures stay out).
- **Lightning R1:** one read per record through Nightshift, Lightning pinned in the signed receipt, cloud kind required (the local Lightning lane is refused), no cache, thinking off, the reader's prompt and guard unchanged. R1's rule unchanged: a field closes only if its accepted value agrees with the registry and the reading's own N and count agree under the count rule.
- **Compared with:** Super's R1 in the dial run (same records; its closings, tokens and seconds from `logs/dial-sample.jsonl` and `logs/markovian-chunks.jsonl`), and the dial run's always-4k Super control as the referee. No new Super calls.
- Records run one after another, after the M0 baseline finishes (so the two runs do not share Nightshift's capacity).

## Measures (fixed now)

- Records settled (both N and the count closed) and fields closed: Lightning against Super's 15 and 31.
- For each Lightning closing, the 4k control's verdict: agree / disagree / unconfirmed.
- Completion tokens and seconds: Lightning against Super's R1, summed over the scored records.

## Kill and void lines

- **Unsafe:** the control disagrees with more than 10% of Lightning's closings (the dial test's line). Reported, never re-tuned.
- **Not worth it:** Lightning settles fewer records than Super's R1 (15). Then R1 stays Super whatever the cost.
- Lightning replaces Super at R1 only if it is neither unsafe nor settles fewer.
- **Provider failure:** listed by id, not scored, never re-run. **Void** if more than 9 of the 28 fail.

## Prediction (before the run)

Lightning is safe (0 or 1 disagreement) but settles fewer records than Super, because a smaller model's quotes fail the guard more often. A guess.
