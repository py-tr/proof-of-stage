# Second domain, rule level: FEC campaign-finance reports that cannot be true as written (2026-10-24)

Data: OpenFEC `/v1/reports/house-senate/`, Senate committees, cycle 2018, pulled with `scripts/fec_pull.py` (public data, api.open.fec.gov; raw pages not committed). Counts: `python scripts/fec_counts.py 2018` -> `logs/fec-counts-2018.json`. No model call.

## The rule

A committee's report summary (FEC Form 3, detailed summary page, lines 23-27) must add up: **cash on hand at the beginning + total receipts - total disbursements = cash on hand at close**. The FEC database holds those four numbers per report; until 2018 Senate committees filed on paper, and the scans were keyed into the database by a contractor (sources in the project knowledge base, research-second-domain-datasets-2026-10-24.md). `app/fec/guard.py` classifies each record: consistent, impossible (the four numbers are off by $1 or more), cents only (off by less than $1), incomplete (a number missing).

## Result

| 2018 Senate reports (4,307 after dropping duplicate rows) | Impossible (off by >= $1) | Cents only | Consistent | Incomplete |
|---|---|---|---|---|
| **Paper-filed (keyed from scans)**: 3,156 | **136 (4.3%)** | 2,229 | 783 | 8 |
| **Electronically filed**: 1,151 | **1 (0.09%)** | 0 | 1,150 | 0 |

- Records keyed from paper are impossible far more often than electronically filed ones (4.3% against 0.09%). The ratio (about 50 times) rests on a single e-filed impossible record, so it is not a firm number. 26 of the 136 paper gaps are under $2 (17 of them exactly $1), which a rounding step could produce; at $2 or more, 110 paper records remain impossible. All 137 impossible records link a PDF of the filed report; 29 of them are amendments. The largest gaps: $22,409,245.08, $1,823,308.23, $793,033.06, $717,149.14, $649,685.00.
- The cents-only class (71% of paper reports, none of the e-filed) looks like a systematic artefact of keying or processing (whole dollars where the form has cents), not 2,229 separate errors; it is reported as a class and not read.

## What it means, and what it does not

- The same pattern as the cancer registry, in a non-medical domain: a public database whose numbers were typed in from documents contains records that cannot be true as written, and a plain rule finds them. This is the rule level only: which field is wrong is settled by reading the scanned filing (Parse on the summary page, the amount guard in `app/fec/guard.py`); a pre-registered reading of a sample of the 137 is the next step.
- A spike on paper filings that are consistent (outside the 137) found the summary page and accepted all four lines for 3 of 4 filings (12 of 16 fields); one filing put its summary page beyond the pages searched (research note, "FEC spike").
- Not claimed: that any of the 137 is an error by the committee or by the FEC's contractor before its scan is read; the record and the document may disagree for other reasons (amendments, processing).
