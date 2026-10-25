# Pre-registration: the local first read as a product mode (written 2026-10-25, frozen before the first call)

`python scripts/local_mode_run.py run` refuses to run if `app/engine/local_mode.py`, `local_focus.py`, `local_r1.py`, `rungs.py`, `run_case.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `local-mode.json`, if the drawn records changed, if the prediction is not written, or if it has run once.

## Why (disclosed)

Two pre-registered local tests ran the first read alone:
- local R1: 13 of 28 settled, 4 failures from the 4,096-token window;
- local focus: 28 of 60 settled, 0 failures, 0 disagreements with the cloud, every attempt local.

Both missed their "settled" bars, so cloud Lightning kept the first read. Councils 14 and 15 asked for the local story as a product mode, not a side test. This wires the local first read into the shipped evidence chain (`python -m app.cli run --case <id> --local`) and checks it end to end. The bar is safety and locality, not the count of records settled, which already failed twice. Designed after both local tests; disclosed.

## Design

- **Mode:**
  - The shipped `rungs.climb` with an injected reader. The first read (thinking off) is `local_focus.read_focused`, unchanged: local Nemotron Lightning through Nightshift's Jobs API, "privacy": "local-only", the focus step for long reports, and the quote check on the full report.
  - The deep and scan reads are cloud, as shipped. A report the first read does not settle still goes to the cloud deep read, so this mode keeps only the first read on the PC.
  - Nothing is stored.
- **Records:** 20 census-2 records drawn with seed 20261025 from the 298 scored. None was read by an earlier local test. The ids are frozen in the json.
- **Referee:** the census-2 cloud closing for the same field (Lightning cloud at the first read, Super VL 4k after), already logged. No new cloud referee calls.
- **Measures:**
  - first reads passing the local-only job checklist;
  - records settled by the local first read (report only);
  - local closings that agree with, contradict, or are unconfirmed by the cloud closing.

## Claim, kill

- **Claim:** every first read is local by the job checklist, and 0 local first-read closings differ from the census's cloud closing.
- **Kill:** any first read not local, or any disagreement. The mode then ships off by default, labelled experimental, and is not filmed.
- Never re-run.

## Prediction

In the json, written before the run.
