# Pre-registration: the Ultra critic, v2 (one Nightshift scope per call) (written 2026-10-24, frozen before the first call)

`python -m app.cli ultra-critic-v2` refuses to run if `app/engine/critic_v2.py`, `app/engine/critic.py`, `app/reader/reader.py`, `app/reader/quotes.py` or the prompt differ from the hashes in `ultra-critic-v2.json`.

## Why there is a v2 (disclosed)

v1 (`ultra-critic.md`, result `docs/evidence/ultra-critic-results.md`) did not meet its ship line because only 2 of 5 planted controls could be judged. The cause was a bug in our code, found after the labels were scored: each call's Nightshift item id was built from case + field + run, so a planted control and the real row with the same case and field shared one scope, H-MEM attached the earlier answer, and our receipt check refused the call (5 calls, 3 of them planted). v1's run and published result stand unchanged.

**v2 changes exactly one thing: every call gets its own item id (scope).** Everything else is v1, byte for byte: the prompt (same hash), the model and settings (Ultra via Nightshift, pinned, signed, no cache, thinking on without a budget, max_tokens 8,000), the 41 stored values and how they are collected, the 5 planted rows (the same list, from `ultra-critic.json`), the interleaving, the guard check on an objection, the scoring function and the ship line.

**Designed after the blind labels were known.** Ultra never sees the labels; the prompt and every rule are frozen from v1, so nothing in v2 could be tuned toward them. A reader should still weigh v2 as a confirmation run, not a first measurement.

## Measures, void line and ship line (unchanged from v1)

- Every class over the 41 real rows; verified objections scored against the frozen labels as right / wrong / unscored; missed; plants detected.
- Only the first completed v2 run counts; no row is re-called.
- **Void:** more than 8 provider failures or more than 8 unusable answers among the real rows.
- **Ships** (a read-only "a second reader objects" line on the case page and a `/how` card; never a write to the layer before submission) only if **plants detected ≥ 4 of 5 and objections on real values ≤ 8 and right > wrong and wrong ≤ 1**. Otherwise: "measured, not on the critical path", and nothing ships.

## Prediction (before the run)

No refused calls from memory (0 receipts with H-MEM records); plants detected at least 4 of 5; the real-value objections close to v1's (3, all on the same cases). A guess.
