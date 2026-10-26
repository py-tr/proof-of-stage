# Pre-registration: "Ask the layer", Nemotron tool calls through Nightshift (written 2026-10-26, frozen before the first scored call)

`python scripts/ask_layer_run.py run` refuses to run if `app/agent/ask.py` or `app/agent/ask_eval.py` differs from the hashes in `ask-layer.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

- **The problem:** our agent probes found that an agent writing SQL over the semantic layer never returned the checked count in 35 calls (it counted the raw column).
- **The new fact:** a probe on 2026-10-26 found that Meterless Nightshift returns real tool calls from Nemotron Lightning and Super, each served as requested (`logs/probe-nightshift-update-2026-10-26.txt`).
- **The agent built on it** (`app/agent/ask.py`):
  - Lightning, thinking off (NVIDIA's own description of Lightning's job: tool calls and result validation), answers questions by calling three read-only tools our code runs on the Zetaris layer: the three node-positive answers, the review queue, and a case's verdict with its accepted quotes;
  - every response must carry a signed receipt naming Lightning, from the pinned key, not cached;
  - an answer is shown only if the agent read the layer, and every number and case id in it appears in a tool result or the question.
- **Development, disclosed:** while building it, the agent was tried on two questions that overlap questions 1, 4, 7 and 8 below ("Why is TCGA-E2-A572 flagged…", "How many patients are node-positive, and how many…"). In the first try it answered without calling a tool, which led to two changes made before this freeze: a tool call is required in the first round, and an answer given without reading the layer is refused.

## Design

- **Questions:** 12, frozen in the json with their expected answers. The expected answers are computed by code from the live layer (the same queries the tools run), not by a model.
- **Calls:** each question is asked once.
- **Scoring (lexical, frozen in `ask_eval.py`):**
  - a number question is right when the expected number appears in the shown answer;
  - a field question is right when the shown answer names the field ("count", "N stage", or "person");
  - a refused answer is wrong.
- **Publication:** every answer is published verbatim in the log, so the lexical scoring can be checked by eye.
- Nothing is stored.

## Claim, kill, void

- **Claim:** at least 10 of 12 shown answers right, and every model response carries a verified signed Nightshift receipt naming Lightning.
- **Kill:** fewer than 8 of 12 right, or any response not signed by the pinned key or not answered by Lightning.
- **Void:** more than 3 provider failures. Never re-run.
- **Honest limit:** the tools return the layer's checked values, so this measures whether the agent picks the right tool and reports its result faithfully. It does not measure re-reading the reports.

## Prediction

In the json, written before the run.
