# "Ask the layer": Nemotron tool calls through Nightshift (pre-registered, run 2026-10-26)

Pre-registration: `docs/preregistration/ask-layer.md` + `ask-layer.json` (questions, expected answers and code hashes frozen before the first scored call). Run 20261026T104625, log `logs/ask-layer.jsonl` (every answer verbatim), run record `logs/ask-layer-runs.jsonl`.

## Result: claim not met (kill not fired)

| Measure | Result |
|---|---|
| Questions | 12 (0 provider failures) |
| Right (lexical scoring, frozen) | **9 of 12** (bar 10) |
| Every response signed by the pinned key and answered by Lightning | **yes** (14 tool calls) |
| Aggregate questions (node-positive answers, impossible records, queue size) | 6 of 6 right |
| Case questions | 3 of 6 right |
| Answers refused by the guard | 1 |

## The three misses

- **TCGA-E2-A572 report count:** Lightning called the cohort tool instead of the case tool and wrote "4". The guard refused the answer, because 4 was in no tool result.
- **TCGA-A2-A0EW:** the case tool returned "a person decides"; Lightning reported "the N field is wrong". Shown, and wrong.
- **TCGA-A2-A0CV registry count:** Lightning called the cohort tool and answered "333 positive lymph nodes". 333 is in that tool's result (the cohort's checked answer), so the guard let it through.

## What it means, and what it does not

- Nemotron tool calls work through this Nightshift build, each signed and naming the model.
- The guard stops invented numbers. It does not stop a real number taken from the wrong tool result: the third miss shows that limit.
- Not shipped. No retry was run.
