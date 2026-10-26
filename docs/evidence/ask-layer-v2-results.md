# "Ask the layer" v2: Nemotron tool calls through Nightshift (pre-registered, run 2026-10-26)

Pre-registration: `docs/preregistration/ask-layer-v2.md` + `ask-layer-v2.json` (designed after v1's miss, disclosed; frozen before the first scored call). Run 20261026T105547, log `logs/ask-layer-v2.jsonl` (every answer verbatim), run record `logs/ask-layer-v2-runs.jsonl`. v1's result (9 of 12, not met) stands: `docs/evidence/ask-layer-results.md`.

## Result: claim met

| Measure | Result |
|---|---|
| Questions | 12 new ones (0 provider failures) |
| Right (v1's frozen lexical scoring) | **12 of 12** (bar 10) |
| Every response signed by the pinned key and answered by Nemotron Lightning | **yes** (12 tool calls) |
| Case questions (9 cases v1 never asked about) | 9 of 9, each through `case_verdict` for that case |
| Aggregate questions (new wordings) | 3 of 3 |
| Refused by a check | 0 |

## What changed from v1, and what it means

- Two checks in code, not in the prompt:
  1. when the question names a case, the first round forces the case tool, and an answer is refused unless that case was read;
  2. a case answer's numbers must come from that case's own tool result.
- On new questions, every case answer read the right case, and every number traced to that case's record. **What this shows, precisely:** on the 9 case questions, code selected the case tool (a forced tool choice) and Lightning reported that case's record faithfully; Lightning chose the tool itself only on the 3 aggregate questions. It does not show that Lightning routes case questions on its own (v1 showed it sometimes does not).
- Two of the four number questions could not test attribution, because the registry and report values are equal there (TCGA-AC-A2FK 3 and 3, TCGA-E9-A3X8 4 and 4); the two that differ (TCGA-AQ-A1H2 report 7 vs registry 13, TCGA-BH-A0BS report 2 vs registry 0) were answered from the asked side.
- **Read by eye:** all 12 answers are right. One, TCGA-AR-A1AT, correctly says a person must decide, but also describes an N-stage contradiction the layer does not assert. It counts as right under the frozen rule.
- **Limits:**
  - the tools return the layer's checked values, so this measures picking the right tool and reporting it faithfully, not re-reading reports;
  - an off-topic question is answered with layer facts rather than "the tools cannot answer";
  - designed after v1's miss, one run, no re-run.
