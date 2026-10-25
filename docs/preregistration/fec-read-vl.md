# Pre-registration: FEC v2, Nemotron Super VL reads the handwritten cash summary (written 2026-10-25, frozen before the first call)

`python scripts/fec_read_vl.py` refuses to run if `app/fec/read_vl.py`, `app/fec/read.py` or the reading prompt differ from the hashes in `fec-read-vl.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

FEC v1 (`docs/evidence/fec-read-results.md`) found the summary page on 10 of 12 filings, but text extraction misread handwritten amounts. A spike on three v1 pages (design cases: 1202879, 1231036, 1227521) showed Super VL reading the page image: identical to the builder's read on two pages (5 of 5 lines each), 3 of 5 on the third; and the FEC database, typed by a person from the same paper, disagreed with Super VL exactly where one of them was wrong (one database typing error, two model misreads). This test measures that design on filings nobody has looked at.

## Design

- **Sample:** 24 filings drawn with `random.Random(20261026)` from v1's eligible pool (2018 Senate paper filings, impossible by the cash identity, gap ≥ $2, PDF present, most recent version), minus v1's 12 and the 3 rows with a negative (internal) file number. All 24 PDFs downloaded before freezing (no model).
- **Page:** Nemotron Parse (v1, NVIDIA direct) reads pages 3–6; the v1 rule picks the Detailed Summary Page (`read.find_summary_page`, unchanged). Not found = "not read".
- **Reading:** one Super VL call per filing on that page image (rendered at 1.6x, greyscale JPEG quality 85), 4k thinking budget, NVIDIA direct (Nightshift 1.2.3 refuses pinned image requests; reported). The prompt asks for lines 23–27 exactly as written, no arithmetic, crossed-out boxes noted.
- **The second reader:** the value the FEC typed into its database from the same paper form, for lines 23 (beginning), 24 (receipts), 26 (disbursements), 27 (close).
- **Per line:** agree (equal to the cent) / disagree / unread. **Per filing:** "both readers agree on all four lines" / "the readers disagree on line N: a person decides" / "the readers disagree on k lines: unsettled" / "not read". For filings where all four agree, the document's own gap (23 + 24 − 26 − 27) is reported.

## Measures, claim, void

- **Claim** "Super VL reads the handwritten cash summary" only if **≥ 16 of 24 filings are read and Super VL agrees with the FEC database on ≥ 80% of the lines it read**. Otherwise the counts are the result.
- **Reported:** filings where both readers agree on all four lines and the filing still does not add up (the committee's own arithmetic); every single-line disagreement, listed (a typing error in the database or a misread; after the run the builder looks at each page and says which, labelled as a lay read, not part of the claim).
- **Void:** more than 6 filings fail at the provider. Never re-run; nothing tuned after the run.

## Prediction

In the json, written before the run.
