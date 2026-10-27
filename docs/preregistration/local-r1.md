# Pre-registration: a local Nemotron does the first read on this PC (written 2026-10-24, frozen before the first call)

`python -m app.cli local-r1` refuses to run if `app/engine/local_r1.py`, `app/engine/lightning.py`, `app/engine/rungs.py`, `app/reader/reader.py` or `app/reader/quotes.py` differ from the hashes in `local-r1.json`.

## Why (disclosed)

Pathology reports are the kind of text an owner may not want to send to a cloud API. The ladder's first rung (R1) reads with cloud Nemotron Lightning through Nightshift, and closes a field only when the quote-verified reading agrees with the registry. Nightshift can run the same model family on this PC (a Jobs API job with "privacy": "local-only"). This test asks whether that local lane can do R1's job on the same records, with the same prompt, guard and closing rule. An earlier note that "chat calls never go local" came from Nightshift 1.2.1 with a different setup and the chat endpoint; this test uses the Jobs API, which was checked once (one unscored call, 2026-10-24) to resolve the local lane. Reviewed before freezing by an outside model and a council (`open-agent/research/council-9-four-tests-2026-10-24.md`).

## Design

- **Records:** the 28 of `lightning-cases.json` (the dial test's records, already read by cloud Lightning once and in three timing trials). The local weights have not seen them; the claim is limited to "on the dial records", where the registry's two node fields agree.
- **Reader:** the reader's system prompt and guard unchanged (`app/reader/reader.py`, `quotes.py`); R1's closing rule as in the cloud Lightning test (`lightning.r1_closings`: a field closes only if its accepted value agrees with the registry and the reading is self-consistent).
- **Provider:** Nightshift 1.2.3 Jobs API, `kind` best_of_n, `n` 1, `auto_synthesize` off, `privacy` local-only, the messages plus an empty assistant think turn (as the existing `local_job`), no max_tokens. Each attempt has its own item id; an empty answer is retried once with a new id (`local_job`, frozen by an earlier pre-registration, retries with the same id and is not used here).
- **Referee:** the dial run's logged 4k Super read (`logs/dial-sample.jsonl`, field `control`); no new cloud call on the report text. Each closed field is agree / disagree / unconfirmed against it (`dial.compare`).
- **Local-only checklist, on every attempt (frozen; a missing field fails):** job `privacy` == local-only; job `lanes_resolved` == [`nemotron-3-5-lightning-3-2`]; attempt `lane` == that lane; attempt `model.resolved` starts with `local-runtime/nemotron`; `model.honored` is true; job `policy.egress_honored` is true; `finish_reason` present and not "length".

## Measures, claim, void

- **Primary:** settled records (both open fields closed by R1), out of all 28; a failure, timeout or empty answer after the retry is not settled.
- **Claim** "on the dial records, a local Nemotron did the first read on this PC without the report leaving it, by Nightshift's job record" only if **settled >= 15 of 28** (the bar that put Lightning into R1: Super's 15, fixed before this test), **contradicted = 0**, **and every attempt of every record passes the checklist and no record failed**. One failed check voids the claim regardless of the count.
- **What 0 contradicted can mean:** the closing rule produces 0 whenever the model declines to close, so 0 alone is not evidence of quality; the threats to the claim are one referee disagreement, one non-local attempt, or settled under 15.
- **Report-only:** unconfirmed closings (cloud Lightning: 5 of 38), seconds (wall clock including 2 s polling, and the attempt's `elapsed_ms`), estimated tokens, retries, the resolved model string. Honesty row, not a bar: cloud Lightning settled 18 of 28 in its test and 16, 17, 16 in the timing trials.
- **Void:** more than 9 of 28 records fail. Never re-run, nothing tuned after the run.
- **Differences from cloud R1, disclosed:** Jobs API instead of chat completions; an empty assistant think turn instead of `enable_thinking: false`; no max_tokens; a job record and attempt instead of a signed chat receipt; the quantisation of the local file is not known to us; the guard is the current one (unchanged since the cloud Lightning run's guard round 6; the R1 swap commit after that run, 2b7221b, changed only which model rungs.py and the reader's call pin, not the guard or the closing rule).

## Prediction (before the run)

Fewer settled than cloud Lightning, around 12 to 16 of 28; 0 contradicted; every attempt local. Whether it reaches 15 is a coin flip. A guess, written down so the result can contradict it.
