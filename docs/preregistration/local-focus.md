# Pre-registration: local first read with an on-PC focus step (written 2026-10-24, frozen before the first call)

`python -m app.cli local-focus` refuses to run if `app/engine/local_focus.py`, `local_r1.py`, `lightning.py`, `rungs.py`, `app/reader/reader.py` or `quotes.py` differ from the hashes in `local-focus.json`.

## Why (disclosed)

Designed after the local R1 test (`docs/evidence/local-r1-results.md`): local Nemotron Lightning settled 13 of 28, and the 4 longest reports never reached the model. Nightshift's job log says why: with this PC's 16 GB GPU it loads the local lane with a 4,096-token window instead of 16,384 ("Memory is tight"), and those prompts did not fit. Nothing else held GPU memory (Ollama had no model loaded; Nightshift's llama-server was the only model process). The focus step below was designed on those 4 failed records (two of them read locally as unscored diagnostics, logged in this session's notes); so this test uses records the local lane has never read. The local R1 result stands as published.

## Design

- **Records:** the 60 of `hidden-cases.json` (the hidden-errors test; none is in the dial or local R1 sets). 6 of them are longer than 7,000 characters.
- **Focus step (on this PC, code, no model):** a report of at most 7,000 characters goes whole. A longer one is split into sentences at "." and ";", every sentence matching a lymph-node / nodal-stage / metastasis cue is kept with the sentence before and after, in report order, joined and cut at 7,000 characters; the user message then says "Pathology report (excerpt)". The 7,000 comes from the local R1 run (8,046 characters fit the window, 8,116 did not).
- **Reader:** the reader's system prompt and guard unchanged; every quote is checked against the **full** report, so an excerpt can only cost an acceptance. R1's closing rule as before (`lightning.r1_closings`).
- **Provider:** the local R1 test's job runner, unchanged (`local_r1.run_job`: Jobs API, local-only, best_of_n n=1, auto_synthesize off, empty think turn, a fresh item id per attempt, one retry of an empty answer) and its frozen local-only checklist on every attempt.
- **Referee:** the cloud ladder's closed values for the same records from the hidden-errors run (`logs/hidden-errors.jsonl`, run 20261023T194427: cloud Lightning R1, then Super R2 at 4k). A local closing is agree / disagree (different value) / unconfirmed (the cloud ladder left that field open).

## Measures, claim, void

- **Primary:** settled records (both open fields closed by R1), out of all 60; a failure is not settled.
- **Claim** "a local Nemotron did the first read on this PC, long reports included through an on-PC focus step, without the report leaving it" only if **settled ≥ 33 of 60** (the 15-of-28 bar that put Lightning into R1, scaled: ceil(60 × 15/28)), **0 disagreements with the cloud ladder**, **every attempt passes the checklist, and no record failed**.
- **Report-only:** the 6 focused records and how many settled; unconfirmed closings; seconds; retries. Honesty row: cloud Lightning settled 34 of these 60 at R1 in the hidden-errors run.
- **Void:** more than 20 of 60 records fail. Never re-run, nothing tuned after the run.
- **Disclosed:** the referee's R1 values come from cloud Lightning, the same model family, so agreement there is not independent evidence; on this set every registry is internally consistent, so R1 closes only values that agree with the registry; 0 disagreements is what the closing rule produces whenever a reader declines to close.

## Prediction (before the run)

Settled about 28 to 36 of 60; 0 disagreements; every attempt local; at least 4 of the 6 focused records reach the model, 2 or more of them settle. Reaching 33 is uncertain. A guess, written down so the result can contradict it.
