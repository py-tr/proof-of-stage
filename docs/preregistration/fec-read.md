# Pre-registration: FEC read level, does the scanned filing say which database field is wrong? (written 2026-10-25, frozen before the first call)

`python -m app.cli fec-read` refuses to run if `app/fec/read.py` or `app/fec/guard.py` differs from the hashes in `fec-read.json`, if the prediction there still reads `[fill]`, if more than 4 PDF downloads failed at the freeze, or if a run is already logged (`logs/fec-read-runs.jsonl`): it runs once.

## Why

The rule level (`docs/evidence/fec-rule-results.md`): 136 of 3,156 paper-filed 2018 Senate reports in the FEC database break cash on hand at beginning + total receipts - total disbursements = cash on hand at close (Form 3 lines 23 + 24 - 26 = 27); 110 by $2 or more. Which number is wrong is settled only by reading the filing. This test asks whether the shipped scan reader, Nemotron Parse, plus the amount guard reads the four lines off the scanned summary page cleanly enough to name the field, on a sample drawn before any model call. Designed by the council; the design points below are its decisions, implemented as written.

## Sample (frozen in `fec-read.json`)

- **Population:** the pulled reports (`data/fec/raw/`, OpenFEC `/reports/house-senate/`, Senate, cycle 2018), duplicate rows dropped exactly as `scripts/fec_counts.py` does (4,307 reports).
- **Eligible (93):** `means_filed == paper`; `guard.classify(identity_gap) == impossible`; |record gap| >= $2; a `pdf_url`; `is_amended` false (the most recent version; 17 superseded versions are out). An eligible report can itself be an amendment or termination report (`amendment_indicator` A or T) as long as nothing supersedes it; the indicator is recorded per filing.
- **Spike filings excluded:** the 2026-10-24 spike opened four filings, identified by their beginning image numbers (listed in the json and in `SPIKE_IMAGES`); all four are consistent records, so none could be eligible and the exclusion removes nothing. The spike's first attempt (8 filings) is not identifiable by id; by the research note it used consistent filings only, so it cannot overlap either. Disclosed, not checked by id.
- **Draw:** the eligible list sorted by (file_number, beginning_image_number), `random.Random(20261025).sample(list, 12)`; the run reads them in draw order. Filing id = the FEC file number.
- **PDFs:** downloaded before the freeze (no model involved) from each record's `pdf_url` on docquery.fec.gov with httpx and a browser User-Agent, into a new folder per filing, `data/fec/pdf/<filing_id>/filing.pdf` (git-ignored, data only, opened only by pypdfium2 to render pages). Outcome, bytes, sha256 and page count are frozen; the run re-checks the sha256 and never downloads again. **All 12 downloaded (0 failures).**

| # | filing id | committee | record gap ($) | PDF pages |
|---|---|---|---|---|
| 1 | 1231288 | Louis Gallo for US Senate | 4,900.00 | 13 |
| 2 | 1229754 | Friends of Piper | -8,973.83 | 14 |
| 3 | 1202879 | Courtland Sykes for Senate | 70.39 | 17 |
| 4 | 1193884 | Terry Henderson for Senate | 50,839.28 | 7 |
| 5 | 1314003 | Barkley for Senate | -9.00 | 12 |
| 6 | 1542282 | Dale Kerns for Office | 6,676.96 | 7 |
| 7 | 1254843 | Committee to Elect Chuck Boyce | -300.76 | 12 |
| 8 | 1236339 | Pat Harris for Senate 2018 | -2,654.41 | 35 |
| 9 | 1169553 | Ben Nelson 2012 | -2,000.90 | 10 |
| 10 | 1231036 | BoyantonForSenate | 94,957.46 | 14 |
| 11 | 1227521 | Eve Reyes-Aguirre Committee to Elect | 70.87 | 23 |
| 12 | 1188691 | Courtland Sykes for Senate | -68.00 | 14 |

Record gap = beginning + receipts - disbursements - close as the database holds them. Two filings are from the same committee (Courtland Sykes); the draw is by filing, disclosed.

## Reading (frozen rules, all in `app/fec/read.py`)

- **Model:** NVIDIA hosted `nvidia/nemotron-parse` v1 through `app/providers/nvidia.parse_page` (the shipped scan reader; NVIDIA direct is the stated exception), served model checked by the client. **No other model**: the values are taken from Parse's text by deterministic code and checked by the guard, so there is no Super read, no Nightshift call and no envelope.
- **Pages:** Parse reads PDF pages **3, 4, 5 and 6, counted 1-based** (0-based indices 2-5), each rendered as the scan reader does (centred on a white 1024x1280 canvas, grayscale, JPEG quality 60). All four pages are read for every filing (at most 48 Parse calls), one attempt per page (the client's own transport/429/5xx retries only). A page the PDF does not have is "absent", not a failure. The range is never extended.
- **Page text:** a page's blocks' text in Parse's order joined by newlines. This text is the document the guard checks.
- **Summary page:** the first page (lowest number) of those read whose text matches both `cash on hand at (the) beginning` and `cash on hand at (the) close` (case-insensitive, any whitespace between words). None: the filing is **not read**.
- **Lines:** the page text split at newlines, LaTeX row ends (`\\`) and `</tr>`; empty lines dropped.
- **Label of each field:** the phrase, else a line that starts with the line number followed by words:
  - beginning: `cash on hand at (the) beginning`, or line `23`
  - receipts: `total receipts this period`, or line `24`
  - disbursements: `total disbursements this period`, or line `26` (so line 22 "TOTAL DISBURSEMENTS (add Lines ...)" and line 17 are never taken)
  - close: `cash on hand at (the) close`, or line `27`
- **Amount:** in the text after the label, blank out parenthesised text containing letters ("(from Line 16, page 3)") and references such as "Line 26", "from 25", "page 3"; cut at the first later start of another cash-summary label (`23`-`27` followed by words, "cash on hand", "total receipts/disbursements", "subtotal"); take the **last** amount left (digits with optional thousands commas and two decimals; a leading `$` and enclosing parentheses kept, a minus sign never taken). If the label line has no amount, the next line is used unless it carries another cash-summary label. Candidates are tried in page order; the first that yields an amount wins.
- **Quote:** the verbatim page text from the start of the label line to the end of the amount.
- **Guard:** `app/fec/guard.check_value(field, amount, quote, page_text)` must accept it (quote found in the page text, the amount inside it, the field's label or line number inside it). **Read cleanly = all four lines accepted.**

## Verdict per filing (frozen, in this order)

1. **not read**: the PDF failed, no summary page in pages 3-6, or any of the four lines not accepted.
2. **record matches filing**: every document value is within $1 of the database (differences under $1 are the database's known cents keying, not a difference).
3. **the filing itself does not add up**: the document's identity gap (23 + 24 - 26 - 27) is $2 or more.
4. **the filing contradicts the record on [field]**: the document adds up (gap under $2) and exactly one field differs from the database by $1 or more.
5. **other**: the document adds up and more than one field differs.

Disclosed overlap: a filing whose four values all equal an impossible record cannot add up itself, so "record matches filing" is in practice a filing that does not add up and was keyed faithfully; it is listed first because it is the more specific finding. The json log carries the document gap and the list of differing fields for every filing read, so either reading of 2 and 3 can be checked.

## Claim, stop, void

- **Claim** "the pattern transfers at the read level" only if **at least 5 of 12 read cleanly AND at least 3 name exactly one field** (verdict 4). Otherwise the counts are published and nothing more is claimed. The denominator is all 12.
- **Stop** the same day if more than 4 PDF downloads fail (they did not: 0 of 12).
- **Void** if more than 4 Parse page failures (an exception or an empty block list); once the fifth failure happens no further pages are sent. A void run is published as void.
- Never re-run, no extra calls, nothing tuned after the run. The rules above were written without looking at any of the 12 filings' pages.

## Outputs

`logs/fec-read.jsonl` (one row per filing: pages read, page texts, the summary page, each field's amount, quote and guard result, record gap, document gap, differing fields, verdict), `logs/fec-read-runs.jsonl` (the summary), `data/fec/pdf/<filing_id>/parse.json` (raw Parse blocks, not committed).

## Prediction (before the run)

In `fec-read.json` (`prediction`), written by the main session before the run.
