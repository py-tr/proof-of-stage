# Pre-registration: Ultra, the shipped second reader, on the census-2 hits (written 2026-10-25, frozen before the first call)

`python scripts/critic_census_run.py run` refuses to run if `app/engine/critic_census.py`, `critic_v2.py`, `critic.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `critic-census.json`, if the census fields or their verdicts changed, if the prediction is not written, or if it has run once.

## Why (disclosed)

The second reader's record rests on 3 logged objections, all right, on the 41 stored values (`docs/evidence/ultra-critic-results.md`). Councils 14 and 15 asked whether it objects where a reading is known to be wrong. The census-2 deep read closed 25 values that differ from the registry. After the builder's review (`docs/evidence/hidden-2-lay-reads.json`; AI-drafted, builder-confirmed), 12 fall, 12 stand and 1 is unsure. Ultra has never seen these values or the verdicts. Designed after the census and its review; disclosed.

## Design

- **Fields:** the 25 census-2 hit values, each with the review's verdict, frozen in the json. One field-level exception: TCGA-AC-A3EH's count stands while its N falls, because the report prints N2, neither the registry's N3 nor the reading's N1A.
- **Call:** `critic_v2.ask`, imported unchanged: the same prompt, Nemotron 3 Ultra, thinking on, through Nightshift, pinned, signed, no cache, one scope per call. The value under review is the census reading and its accepted quote, where the shipped critic used the stored value. Ultra answers agree, contradiction or cannot_tell; a contradiction goes through the unchanged objection check (its quote is in the report, shows its value, and the value differs).
- **Nothing is stored.** Every envelope is kept.

## Claim, kill, void

- **Claim:** Ultra says "contradiction" on at least 6 of the 12 fallen fields and on at most 2 of the 12 standing fields. Also reported: the same counts with a verified objection. The one-quote rule cannot verify a sum of parts, so verified objections on the 5 per-part fields are expected to be fewer.
- **Kill:** objections on fallen fields not above objections on standing fields. The second reader's claim then stays at "3 logged objections".
- **Void:** more than 5 provider failures. Never re-run.

## Prediction

In the json, written before the run.
