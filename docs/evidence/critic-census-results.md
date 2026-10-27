# Ultra, the shipped second reader, on the census-2 hits (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/critic-census.md` + `critic-census.json` (frozen before the first call). Run 20261025T180313, log `logs/critic-census.jsonl`, envelopes `docs/evidence/attest/critic-census-envelopes.jsonl`. `critic_v2.ask` unchanged (Nemotron 3 Ultra, thinking on, Nightshift, pinned, signed, no cache), with each census reading and its quote as the value under review; Ultra never saw the verdicts (the builder's review: AI-drafted, builder-confirmed).

## Result

| Fields | Ultra says contradiction | ... with a verified objection | Ultra agrees | Failures |
|---|---|---|---|---|
| Reading fell (12) | **2** | 1 | 10 | 0 |
| Reading stood (12) | **0** | 0 | 12 | 0 |
| Unsure (1) | 0 | 0 | 1 | 0 |

**Claim** (contradiction on at least half of the fallen fields and on at most 2 standing): **not met**. Kill (objections on fallen not above standing): **not fired**.

Prediction (before the run): "Before the run, by the coding agent: Ultra objects on 5-8 of the 12 fallen fields (likely on the bilateral and per-part ones where the report states the total elsewhere) and on 0-2 of the 12 standing fields; verified objections on fallen fewer (3-6) because a sum of parts sits in no single quote; claim likely met; 0-2 provider failures."

**Scoring note:** Rescored from logs/critic-census.jsonl with the frozen per-field verdicts in critic-census.json: the run's own summary row (logs/critic-census-runs.jsonl) is wrong because each row's 'verdict' key was overwritten by Ultra's own verdict before scoring (a bug in app/engine/critic_census.py found after the run). No call was re-run; the per-field log is unchanged.

## Field by field

| Case | Field | Registry → reading | Review | Ultra | Verified |
|---|---|---|---|---|---|
| TCGA-A2-A1G4 | NPOS | 2 → 1 | stands | agree | - |
| TCGA-A2-A25B | NPOS | 2 → 1 | falls | agree | - |
| TCGA-AC-A3EH | N | N3 → N1A | falls | contradiction | yes |
| TCGA-AC-A3EH | NPOS | 12 → 3 | stands | agree | - |
| TCGA-AN-A0XV | N | N2 → N1 | stands | agree | - |
| TCGA-AO-A03L | N | N2 → N1A | falls | agree | - |
| TCGA-AO-A03L | NPOS | 4 → 3 | falls | agree | - |
| TCGA-AO-A1KQ | NPOS | 2 → 1 | falls | agree | - |
| TCGA-AR-A254 | NPOS | 9 → 7 | falls | agree | - |
| TCGA-AR-A2LN | N | N0 → N1A | stands | agree | - |
| TCGA-AR-A2LN | NPOS | 0 → 1 | stands | agree | - |
| TCGA-AR-A5QM | N | N0 → N2 | falls | agree | - |
| TCGA-AR-A5QM | NPOS | 0 → 4 | falls | agree | - |
| TCGA-BH-A0B5 | NPOS | 5 → 6 | stands | agree | - |
| TCGA-BH-A0B7 | NPOS | 1 → 3 | stands | agree | - |
| TCGA-BH-A0BD | NPOS | 2 → 1 | unsure | agree | - |
| TCGA-BH-A18H | N | N0 → N1A | falls | agree | - |
| TCGA-BH-A18H | NPOS | 0 → 2 | falls | agree | - |
| TCGA-E2-A108 | NPOS | 4 → 5 | stands | agree | - |
| TCGA-E2-A154 | N | N0 → N1C | stands | agree | - |
| TCGA-E2-A154 | NPOS | 0 → 2 | stands | agree | - |
| TCGA-EW-A1IZ | NPOS | 5 → 4 | stands | agree | - |
| TCGA-EW-A1P5 | NPOS | 3 → 1 | stands | agree | - |
| TCGA-GM-A4E0 | N | N3A → N2A | falls | contradiction | - |
| TCGA-GM-A4E0 | NPOS | 10 → 9 | falls | agree | - |

## What it means, and what it does not

- The finding: Ultra shares the deep read's traps. It agreed with 10 of the 12 readings that fell (the per-part counts and the other-breast readings), and objected on none of the 12 that stood. Its two objections were both right in substance: TCGA-AC-A3EH's N (the report prints pT3 N2; verified) and TCGA-GM-A4E0's N, where it added the sentinel's 1 to Part C's 9 but answered 10, a count, in the N field, so the objection check rejected it as an invalid category. A second model reading the same specimen is not a fix for a per-part sum: the sum has to be code (`docs/evidence/parts-bench-results.md`).
- The second reader can only object; an objection sends a case to a person and never changes a value. This measures whether its objections land where the deep read was wrong, on 25 values it had never seen.
- A sum of parts sits in no single quote, so an objection about a per-part total may fail the one-quote check even when Ultra is right; both counts are reported.
- The verdicts it is scored against are one lay review (AI-drafted, builder-confirmed). One run, no re-run.
