# Pre-registration: "Ask the layer" v2 (written 2026-10-26, after v1's miss, frozen before the first scored call)

`python scripts/ask_layer_v2_run.py run` refuses to run if `app/agent/ask.py`, `ask_v2.py`, `ask_eval.py` or `ask_v2_eval.py` differs from the hashes in `ask-layer-v2.json`, if the prediction is not written, or if it has run once.

## Why (disclosed: designed after v1's miss)

- **v1** (`docs/preregistration/ask-layer.md`, result in `docs/evidence/ask-layer-results.md`, which stands) scored **9 of 12** against a bar of 10.
- **Two of its three misses were case questions where Lightning called the cohort tool instead of the case tool.** One of those answers, "333", was a real number from the wrong tool, and it passed v1's guard.
- **v2 keeps v1's model, prompt, tools, receipt check and scoring unchanged.** It adds two checks in code (`app/agent/ask_v2.py`):
  1. when the question names a case, the first round forces the `case_verdict` tool (a named tool choice), and the answer is refused unless `case_verdict` ran for that case;
  2. the numbers in a case answer must appear in that case's own `case_verdict` result (or the question), not merely in any tool result.
- **One gate call was made before this freeze, not scored:** "Which field does the report contradict for TCGA-E2-A1B4?". Nightshift honoured the named tool choice and the answer was right (`logs/probe-nightshift-update-2026-10-26.txt`).
- **A smoke question on an off-topic question** ("the weather in Prague") was answered with layer facts instead of "the tools cannot answer". This limit is noted, and not part of this bar.

## Design

- **Questions:** 12, frozen in the json with expected answers computed by code from the live layer.
  - 9 case questions name cases v1 never asked about.
  - 3 aggregate questions are new wordings over the same tools (v1 got its 6 aggregate questions right).
- **Calls:** each question is asked once.
- **Scoring:** v1's frozen lexical rules, with every answer published verbatim.
- Nothing is stored.

## Claim, kill, void (v1's, unchanged)

- **Claim:** at least 10 of 12 shown answers right, and every response signed by the pinned key and answered by Lightning.
- **Kill:** fewer than 8 of 12 right, or any response not signed or not Lightning.
- **Void:** more than 3 provider failures. Never re-run.

## Prediction

In the json, written before the run.
