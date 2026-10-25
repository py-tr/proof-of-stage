# Pre-registration: IRS 990-EZ read level, does the filed return say which database field is wrong? (written 2026-10-25, frozen before the first call)

`python scripts/irs_read.py` refuses to run if `app/irs/read.py`, `app/reader/quotes.py` or the reading prompt differ from the hashes in `irs-read.json`, if the prediction there still reads `[fill]`, if more than 6 of the 16 returns had no document at the freeze, or if a run is already logged (`logs/irs-read-runs.jsonl`): it runs once.

## Why

The product's pattern is: a database record breaks an identity, a model reads the source document, code accepts a value only with a verbatim quote, and the verdict names the field the record gets wrong. It was built on pathology reports and tried on FEC campaign-finance scans (`fec-read.md`, `fec-read-vl.md`). This test asks whether it works on a second non-medical domain: the IRS Statistics of Income (SOI) extract of Form 990-EZ data, keyed by the IRS from paper returns, against the returns themselves. On a 990-EZ, Part I line 9 (total revenue) - line 17 (total expenses) = line 18 (excess or deficit). In the 2016 extract, paper-filed records (`elf == N`) break this by $2 or more about 1,500 times; e-filed records essentially never do. Which number is wrong is settled only by reading the return.

## Sample (frozen in `irs-read.json`)

- **Year:** the 2016 SOI extract (`https://www.irs.gov/pub/irs-soi/16eofinextractez.zip`; sha256 frozen; the `.dat` member read in-process with `zipfile`, never extracted). Chosen because the main session's counts and its verified example come from it and its tax periods (mostly 2014-2016) are in Candid's PDF archive; no other year was looked at for this sample.
- **Population (1,523 eligible of 230,745 rows, 112,556 paper):** `elf == N`; `totrevnue`, `totexpns`, `totexcessyr` integers; |totrevnue - totexpns - totexcessyr| >= $2; one row per (EIN, tax period), the first in file order kept; sorted by (EIN, tax period).
- **Design cases excluded:** the three returns opened before this design (the main session's verified example 352517049 / 201506, and the scout's 061762420 / 201507 and 311741739 / 201506), by (EIN, tax period).
- **Draw:** `random.Random(20261025).sample(eligible, 16)`; the run reads them in draw order.
- **Documents:** each return fetched before the freeze (no model) from `https://990s.foundationcenter.org/990_pdf_archive/{EIN[0:3]}/{EIN}/{EIN}_{YYYYMM}_990EZ.pdf` (Candid), sequentially with a 2 s pause and a browser User-Agent, into its own new folder `data/irs/pdf/<EIN>_<period>/return.pdf` (git-ignored, data only, opened only by pypdfium2). A miss is recorded as **no document** and never replaced by another draw. Outcome, sha256, page count and page-1 text length are frozen; the run re-checks the sha256 and never downloads again. **11 of 16 downloaded; 5 no document** (Candid answered 403 AccessDenied, the same answer S3 gives for a name that does not exist, checked on an impossible tax period). The stop rule (more than 6 missing) was not triggered.

| # | EIN | tax period | db line 9 | db line 17 | db line 18 | db gap | PDF | pages | page-1 text chars |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 462315047 | 201512 | 112,922 | 106,990 | 5,930 | 2 | no document | | |
| 2 | 451733782 | 201512 | 151,898 | 154,186 | -2,293 | 5 | ok | 15 | 4,558 |
| 3 | 273163951 | 201506 | 34,050 | 5,284 | 28,786 | -20 | no document | | |
| 4 | 264579813 | 201412 | 195,607 | 174,873 | 20,826 | -92 | ok | 7 | 4,652 |
| 5 | 841213411 | 201412 | 79,351 | 78,105 | 1,226 | 20 | ok | 8 | 4,681 |
| 6 | 930495047 | 201512 | 7,647 | 4,990 | 2,659 | -2 | ok | 12 | 4,457 |
| 7 | 582373397 | 201512 | 30,078 | 34,511 | -4,483 | 50 | ok | 12 | 4,638 |
| 8 | 465041709 | 201412 | 2,765 | 2,773 | 0 | -8 | ok | 12 | 4,671 |
| 9 | 202280101 | 201412 | 29,012 | 30,169 | -1,154 | -3 | ok | 12 | 4,432 |
| 10 | 460783293 | 201512 | 67,545 | 73,877 | -6,322 | -10 | ok | 14 | 4,382 |
| 11 | 426076616 | 201512 | 1,389 | 820 | 596 | -27 | no document | | |
| 12 | 237414028 | 201512 | 20,570 | 13,276 | 7,292 | 2 | no document | | |
| 13 | 860973901 | 201412 | 0 | 493 | -483 | -10 | ok | 12 | 4,469 |
| 14 | 237257998 | 201606 | 11,056 | 5,345 | 5,716 | -5 | no document | | |
| 15 | 141831763 | 201512 | 32,450 | 2,114 | 30,391 | -55 | ok | 4 | 3,957 |
| 16 | 383851753 | 201412 | 140 | 1,153 | -1,015 | 2 | ok | 4 | 3,920 |

db gap = line 9 - line 17 - line 18 as the extract holds them (whole dollars). The page-1 text length was measured at the freeze by code (a count only; no page was read by a person or a model). The 11 text layers are long enough (>= 500 chars), so none is "not read" for lack of text.

## Reading (frozen rules, all in `app/irs/read.py`)

- **Document:** the text layer of PDF page 1 by pypdfium2 (`get_textpage().get_text_range()`). Under 500 characters (after stripping whitespace): **not read**. **No OCR fallback** in this test. Note: on the returns seen at design time this text layer is the archive's OCR of the scanned paper return (dropped decimal points such as "6448446" for 64,484.46, split digits, stray characters), not the filer's typed text; the rules below are written for that.
- **Reader:** Nemotron Super VL (`config.NS_SUPER_VL`) through Nightshift, **text only**, one call per filing: pinned (`require_model`), signed receipt required and checked against the pinned key `NS_RECEIPT_PUBKEY`, `allow_cache=False`, thinking budget 4,000 (`thinking_args(4000)`), a fresh item id per call (`irs-read-<run>-<EIN>-<period>-<random>`). Every envelope is kept in `docs/evidence/attest/irs-read-envelopes.jsonl` (`envelope_tap.capture()`). The prompt (`PROMPT`, sha in the json) asks for lines 9, 17, 18, each as `{"amount", "quote"}`, the amount as the return shows it (no arithmetic), the quote verbatim from the text containing the line's label and the amount.
- **Line accepted** only if all hold: the amount parses (`$`, commas, spaces ignored; parentheses or a leading minus = negative); the quote is found in the page text by `app.reader.quotes.locate` (case, punctuation and whitespace ignored; at least 4 letters/digits); and the amount is inside the quote: some whitespace-separated token of the quote (non-digits stripped at its ends) equals |amount| to the cent, or is written without a decimal point and equals |amount|'s whole dollars (cents optional), or is 3+ plain digits that equal |amount| with the decimal point dropped. The sign is not checked against the quote (OCR loses parentheses); it comes from the model's amount. Whether the quote carries the line's printed label (`total revenue`, `total expenses`, `excess or (deficit)`) is recorded per line but does **not** gate acceptance. **Read cleanly = all three lines accepted.**

## Verdict per filing (frozen, in this order)

1. **not read**: no document, text layer under 500 chars, provider failure, or any of lines 9, 17, 18 not accepted.
2. **record matches return**: every accepted value within $1 of the database (|difference| < $1; the extract holds whole dollars). The database identity break then comes from elsewhere (typically the return itself does not add up and was keyed faithfully).
3. **the return itself does not add up**: the return's own |9 - 17 - 18| >= $2.
4. **the record contradicts the return on [field]**: the return adds up (|9 - 17 - 18| <= $1) and exactly one database value differs by $1 or more from the accepted value. [field] is "line 9 (total revenue)", "line 17 (total expenses)" or "line 18 (excess or deficit)".
5. **other**: everything else (more than one field differs, or a return gap above $1 and under $2).

"record matches return" is checked before "does not add up", as in the FEC test: it is the more specific finding. The log carries the return gap and the differing lines for every filing read, so either reading can be checked.

## Claim, stop, void

- **Claim** "the product's pattern works on a second, non-medical domain" only if **at least 8 of 16 are read cleanly AND at least 3 are "the record contradicts the return on [field]"**, and the run is not void. Otherwise the counts are published and nothing more is claimed. The denominator is all 16, the 5 without a document included (they count as not read).
- **Stop** if more than 6 of 16 had no document at the freeze (5 did not).
- **Void** if more than 4 provider failures (an exception from the Nightshift call, including a receipt that fails verification); after the fifth no further calls are sent. A void run is published as void.
- Never re-run, no extra calls, nothing tuned after the run. The rules were written before any sampled return's text was read; only the design-case returns (excluded) were looked at.

## Data, licence and terms

- The SOI extract is public US government data published by the IRS. Form 990-EZ returns of exempt organisations are public-inspection documents (IRC 6104).
- The PDFs come from Candid's 990 archive (990s.foundationcenter.org). **Candid's terms of use for this archive were not reviewed**; disclosed. Fetching was polite: sequential, a 2 s pause, a browser User-Agent, 16 requests at the freeze plus a handful at design time (a few example returns, and two requests checking what a 403 means). The PDFs are not committed or redistributed; only EINs, tax periods, hashes and the model's quoted lines (in the log) are.
- Downloads are untrusted data: each file in its own new folder under `data/irs/` (git-ignored), read in-process only (zipfile, pypdfium2); nothing in them is executed or imported.

## Outputs

`logs/irs-read.jsonl` (one row per filing: page-1 text, receipt id and signature, raw answer, each line's amount, quote, span, label flag and acceptance, return gap, differing lines, verdict), `logs/irs-read-runs.jsonl` (the summary), `docs/evidence/attest/irs-read-envelopes.jsonl` (signed envelopes).

## Prediction (before the run)

In `irs-read.json` (`prediction`), written by the main session before the run.
