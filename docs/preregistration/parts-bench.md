# Pre-registration: the part-aware count, on three sets (written 2026-10-25, frozen before the first call)

`python scripts/parts_bench_run.py run` refuses to run if `app/engine/parts_bench.py`, `app/reader/parts.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `parts-bench.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

The census-2 review found two traps in the shipped deep read:
- in 5 of the 7 readings that fell, a separately submitted sentinel node was left out of the total;
- in 2, the reader read the other breast in a bilateral case.

Council 15 (both seats, and both outside reviews) asked for a fix that is tested honestly. The fix is `app/reader/parts.py`. Super VL lists every specimen part with its own verbatim quote and never returns a total. Code checks each quote with the shipped rules (unchanged), drops parts on the other breast when the GDC record's side is known, takes a labelled total when one is verified, and otherwise adds the verified parts. A sum appears in no single quote, so the product's one-quote rule would show it to a person as "parts_sum"; this test scores the number either way and reports the status. Designed after the census and its review, on the 7 readings that fell; disclosed. Nothing is wired into the shipped chain.

## Design

One Super VL call per record (4k thinking, Nightshift, pinned, signed, no cache). Each record's side comes from GDC `diagnoses.laterality`: the diagnosis that carries a pathologic N, fetched and frozen in the json before the first call. Three sets, frozen in the json:

- **A, designed on (disclosed, so a pass is weak evidence):** the 18 census-2 hit records, 24 fields. TCGA-AC-A3EH's N is excluded: the report prints N2, neither value. A fallen field is fixed if the new value matches the registry or is left open. A standing field is kept if the new value is still the census reading. The N value is the count rule applied to the new count.
- **B, blind labels (the honest test):** the 25 review-queue records. The new count is scored against the frozen blind label's count, wherever the label states one. The shipped deep read scored 16 correct, 0 wrong, 1 not accepted on these (`reader-bench-results.md`).
- **C, regression:** 40 census-2 records the shipped reader agreed with (no hit), whose reports state two or more node fractions (seed 20261026, from a pool of 123). A new count that differs from the registry is a new disagreement.

## Claims, kill, void

- **A:** at least 8 of the 11 fallen fields fixed, and at least 10 of the 12 standing fields kept.
- **B:** count correct on at least 15 labelled cases and wrong on at most 1.
- **C:** at most 2 new disagreements.
- **Kill:** A: fewer than 6 fixed, or more than 3 standing lost. B: more than 2 wrong. C: more than 3 new disagreements. A killed set is published as a loss, and the shipped reader and its Limits line stay.
- **Void:** more than 10 provider failures. Never re-run.

## Prediction

In the json, written before the run.
