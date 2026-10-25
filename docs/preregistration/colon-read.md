# Pre-registration: a second cancer type, the impossible colorectal records (written 2026-10-25, frozen before the first call)

`python scripts/colon_read.py` refuses to run if `app/engine/colon_read.py` or its prompt differ from the hashes in `colon-read.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

To show the product's pattern carries to another registry slice with the same public sources: GDC's clinical fields for TCGA-COAD and TCGA-READ (the fields the breast layer onboards) and the same TCGA report corpus. Chosen on 2026-10-25 after a feasibility count (12 impossible of 591 by the count rule; 10 with a report), before any model read a colorectal report.

## Design

- **Population:** every TCGA-COAD / TCGA-READ case with a recorded pathologic N and a recorded positive-node count (GDC API at freeze time): **592**. **Impossible** under the paraphrased colon count rule (N0 none; N1 1–3; N2 4 or more; colon has no N3, so a count of 10 or more is N2, unlike breast): **10**; N1c with 0 positive nodes is valid (tumour deposits without a positive node) and is not counted. With a report in the corpus: **8**, all read (a census, no sample).
- **Reader:** Super VL through Nightshift, signed, no cache, 4k thinking budget, a fresh item id; the reader's prompt with "breast" replaced by "colorectal" and the colon T and N category lists (frozen, sha in the json); the reader's own guard (`judge_field`, `judge_count`, imported unchanged) checks every quote word for word. One read per case (the breast ladder's first-rung closing rule uses the breast count rule, so it is not used here; disclosed). Envelopes kept.
- **Verdict (colon rule):** "the report contradicts the count" (an accepted count differs from the registry's and agrees with the recorded N), "the report contradicts the stage field" (an accepted N differs from the recorded one and agrees with the recorded count), otherwise "a person decides".

## Claim, void

- **Claim** "the pattern carries to a second cancer type" only if the report names a contradicted field (with a verified quote) on **at least half of the records read**. Otherwise the coded table is the result.
- **Void:** more than 3 provider failures. Never re-run. Nothing is written to the breast layer.

## Prediction

In the json, written before the run.
