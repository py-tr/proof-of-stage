# Does an agent reading the layer's descriptions use the verdict? Results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/agent-probe.md` + `agent-probe.json`, `agent-schema-with.txt`, `agent-schema-without.txt` (commit e06b501, frozen before the first call; the run checked the hashes at start). Logs: `logs/agent-probe.jsonl` (every call: the SQL, the reason, the receipt, the result), `logs/agent-probe-runs.jsonl`, `logs/agent-probe-2026-10-23.txt`. Run 2026-10-23 20:21 UTC.

## Validity

10 of 10 calls answered: Nemotron Super VL through Nightshift, signed receipts verified against the pinned key, not cached, 4k thinking budget, interleaved arms. 0 provider failures. **Neither arm void.**

## Result

| Arm | Queries using `fault_field` | Counted from | Results |
|---|---|---|---|
| **with** the pointers in the N and count descriptions | **0 of 5** | the count column (`lymph_nodes_positive`), 5 of 5 | 476, 476, refused, 476, 476 |
| **without** the pointers | **0 of 5** | the count column, 5 of 5 | 476, 476, 476, 0, 476 |

Kill line ("the pointer changes the agent's query": at least 4 of 5 *with* and at most 1 of 5 *without* use `fault_field`): **not met**. The descriptions did not change the agent's answer.

Prediction (before the run): "*without* counts from one registry column, most likely the N column; *with* uses `fault_field` sometimes but not 4 of 5." **Half held:** it counted from one column, but the count column, every time, in both arms. That is the column whose own description carries the pointer in the *with* arm.

## What the agent's answer misses

The agent's 476 (`recorded_stage`, all editions, `lymph_nodes_positive > 0`) leaves out **all 6 patients** whose report the layer reads as node-positive while the count column records 0 (TCGA-A7-A26E, A7-A26H, AO-A1KP, BH-A0BS, BH-A0DD, E2-A572; checked by query: 0 of the 6 are counted). E2-A572's report says "Lymph node status: Positive 8 / 13". So an agent grounded in the layer's descriptions, given the pointer to the verdict in the description of the very column it used, still gave an answer the verdict would correct, and nothing in its answer showed it.

## Two failures that are ours, not the model's

- **"with" call 3 was refused by our read guard**, not by Zetaris: the guard rejects table aliases (`FROM … recorded_stage r`, "name is outside the registry audit sources"); the same query without the alias passes (checked). The guard is over-strict; it was not changed for this run.
- **"without" call 4 returned 0** because it read `stage_check.lymph_nodes_positive` with `RLIKE '^[0-9]+$'`, and the layer stores counts as decimal text ("4.0"); no column description states that format. A gap in our layer's descriptions.

## What it means, and what it does not

- n = 5 per arm, one question, one model: this is a probe, not a rate. It shows that a pointer sentence in a description is not enough to make this agent use a verdict column; it does not show that no wording or schema design would.
- It supports the README's claim from the other side: the layer's meaning (the descriptions) was clear enough for the agent to write a working query 9 times, and the answer was still wrong for the 6 patients whose record contradicts its report. The verdict has to be applied, not only described.
- Not tested: a column or view that applies the verdict for the agent (for example a node-positive flag that is already corrected). That would be a new, separately pre-registered question; nothing here was tuned after the run.
