# Pre-registration: the scan witness, two sizes: Nano Omni vs Super VL (written 2026-10-25, frozen before the first call)

`python scripts/scan_witness_run.py run` refuses to run if `app/engine/scan_witness.py`, `app/reader/reader.py`, `quotes.py` or `app/scans/scans.py` differ from the hashes in `scan-witness.json`, if the prompt changed, if the prediction is not written, or if it has run once.

## Why (disclosed)

Super VL reading the page images passed a written-down line as a second witness on scans (vision-scan: 4 of 6 cases matched the Parse path, 0 contradictions). NVIDIA's pattern routes work to the smallest model that does the job. Nemotron 3 Nano Omni (3B active) is the small multimodal Nemotron. Councils 15 and 17 asked whether it can be the scan witness. A one-page probe (not a claim) showed it reads page images; it returned 503 on an earlier probe today. Designed after the vision-scan test; disclosed.

## Design

- **Cases:** the 13 review-queue cases with cached scans (`data/scans/`, 38 page images). All 13 have frozen blind labels.
- **Models:** both read every page image of a case, interleaved per case, with the reader's prompt and a 4k thinking budget, NVIDIA direct. Nightshift refuses pinned image requests, so this is disclosed.
- **Check:** the quote check runs on Nemotron Parse's text of the same pages, unchanged.
- **Scoring:** each N and positive count is scored against the blind label (correct, wrong, or not accepted), with completion tokens and seconds per model. Nothing is stored.

## Claim, kill, void

- **Claim:** Nano Omni's wrong values are at most Super VL's, its correct values at least Super VL's minus 2, and it uses fewer completion tokens. It would then be the scan witness: a report-only second reading of the scanned page.
- **Kill:** Omni has more than Super VL's wrong values plus 1, or fewer than half of Super VL's correct values. Super VL then keeps its earned line, and Omni gets a measured row.
- **Void:** more than 4 failures for either model. Never re-run.

## Prediction

In the json, written before the run.
