# Agent probe 3: given the layer's own data-quality rules, does the agent use the verdict? Results (pre-registered, run 2026-10-24)

Pre-registration: `docs/preregistration/agent-probe-3.md` + `agent-probe-3.json` (commit 582c664, re-frozen before any call in 2dd38ec for a lint-only change). Run 20261024T160521, log `logs/agent-probe-3.jsonl`, summary `logs/agent-probe-3-runs.jsonl`.

## Result

| Arm | Calls | Provider failures | Codes | Numbers returned |
|---|---|---|---|---|
| control (today's schema text) | 5 | 0 | RAW 5 | 476 ×5 |
| treatment (+ the layer's 8 DQ rules, as `LOAD USL` returns them) | 5 | 0 | RAW 5 | 476 ×5 |

**Claim line** (treatment CORRECT ≥ 4/5 with control 0/5, or 5/5 with control ≤ 1/5): **not met** (0 and 0). Every query, in both arms, counted `recorded_stage.lymph_nodes_positive > 0`; none read `stage_check`, `fault_field` or `positive_nodes_checked`, and none copied a rule into its filter (FILTER 0). No SQL errors.

Prediction ("treatment mostly FILTER or RAW, CORRECT 0–1; control RAW or CHECKED; claim not met"): **held** (all RAW).

## What it means, and what it does not

- Three pre-registered looks, one answer: a pointer to the verdict in the descriptions (0 of 10), the checked value beside the raw one (1 of 5), and now the layer's own data-quality rules rendered into the schema (0 of 5). Given this schema and this question, Nemotron Super goes to the table whose name says "recorded stage" and counts the raw column.
- This is why the product writes the verdict into the layer's own rows and answers the question itself (`usl demo` step 11), instead of relying on an agent to discover it.
- Not shown: whether an instruction to apply the rules, a smaller schema, or a different question would change it; none was tested, and no fourth look is planned. n = 5 per arm, one model, one prompt.
