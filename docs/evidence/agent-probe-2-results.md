# Does an agent use a value the layer has already checked? Results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/agent-probe-2.md` + `agent-probe-2.json`, `agent-schema-with.txt` (control), `agent-schema-checked.txt` (treatment: the same text plus one line) (commit f80f050, frozen before the first call; the run checked the hashes at start). The layer change it tests: `stage_check.positive_nodes_checked` (commit c04b10a). Logs: `logs/agent-probe-2.jsonl`, `logs/agent-probe-2-runs.jsonl`, `logs/agent-probe-2-2026-10-23.txt`. Run 2026-10-23 20:51 UTC.

## Validity

10 of 10 calls answered: Super VL through Nightshift, signed receipts verified against the pinned key, not cached, 4k thinking budget, the first probe's prompt and question, interleaved arms. 0 provider failures. **Neither arm void.**

## Result

| Arm | Read `positive_nodes_checked` | Read it and returned 479 | Counted from the raw count | Results |
|---|---|---|---|---|
| **control** (the first probe's text) | 0 of 5 | 0 | 5 of 5 | 0, 476, 476, 476, 0 |
| **treatment** (+ the checked column) | **1 of 5** | **0** | 4 of 5 | 476, no query, 476, **482**, 476 |

Kill line ("the agent uses the checked value": at least 4 of 5 treatment queries read the column and return 479, with the control still at most 1 of 5 on `fault_field`): **not met**. The control replicated the first probe (0 of 5 used `fault_field`).

Prediction (before the run): "the treatment reads the new column in most calls, but not reliably 4 of 5; the control repeats the first probe." **Half held:** the control repeated; the treatment read the column in 1 call, not most.

## The one call that read the checked column

Treatment call 4: `... WHERE CAST(COALESCE(NULLIF(TRIM(positive_nodes_checked), ''), NULLIF(TRIM(lymph_nodes_positive), '')) AS INT) > 0` returned **482**. Checked by query: it includes **all 6** patients the raw count misses (E2-A572 among them), and the 3 records above 479 are exactly the 3 whose checked value is empty because the verdict leaves them to a person (TCGA-D8-A27L, A2-A0EW, AR-A1AT): the query filled them back in from the raw count. So where the agent used the checked value, it corrected the 6 patients; its fallback silently overrode "a person decides".

## Failures that are ours or the format's

- Treatment call 2 returned no parseable query (the guard saw an empty statement); a result for that call, not retried.
- Control calls 1 and 5 returned 0: `RLIKE '^[0-9]+$'` and `TRY_CAST(... AS INT)` fail on the layer's counts stored as decimal text ("4.0"), which no description states (the same gap as in the first probe, call 4). It was deliberately left undocumented so the control text stayed identical.

## What both probes show together (20 calls)

- Given the layer's descriptions, this agent counted from the raw count column in 18 of 19 working queries. A pointer to the verdict (0 of 10) and a checked column beside the raw one (1 of 5) did not change that habit reliably.
- The problem the project addresses is real for agents: a clear, well-described layer still led to a confident answer that leaves out the 6 patients whose record contradicts its report.
- Not tested: removing or replacing the raw column in the view an agent reads (a review called that near-certain to work and uninformative), a different model, other wordings, or other questions. n = 5 per arm, one question: a probe, not a rate.
- What the project concludes for its own design: the verdict is for the people and tools that read `stage_check` and the case page; we do not claim that agents pick it up on their own.
