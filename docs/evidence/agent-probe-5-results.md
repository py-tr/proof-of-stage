# Agent probe 5: the layer's permissions instead of the prompt (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/agent-probe-5.md` + `agent-probe-5.json` (commit 81d5859, frozen before the first call, prediction included). Permission check before freezing: `logs/agent-probe-5-check.txt`. Run 20261025T161503, log `logs/agent-probe-5.jsonl`, summary `logs/agent-probe-5-runs.jsonl`, envelopes `docs/evidence/attest/agent-probe-5-envelopes.jsonl`.

**Agent:** Super VL through Nightshift, pinned, signed (10 of 10 verified), no cache, 4k thinking budget. Prompt and question exactly as probe 1 ("How many patients are node-positive?"). 5 calls per arm, interleaved; 0 provider failures.

## Setup

The agent got its own Zetaris account. Its role, `agent_reader`, reads one table: `AGENT_FILES.node_status`, a dated copy of the checked values (`case_id`, `positive_nodes_checked`, `fault_field`; 1,097 rows) from the live layer.

A view over `stage_check` was tried first and refused. Zetaris requires a view's reader to have access to its source table, and that table also holds the raw count.

Before freezing, the check showed Zetaris itself refusing this account on `recorded_stage`, on `stage_check` and on the view ("User 'AGENT@ZETARIS.COM' does not have access to USL …").

## Result

| Arm | Codes | Queries |
|---|---|---|
| **Agent** (its own Zetaris account, schema text = the one table) | **CORRECT 5 of 5** (479) | every query counted `positive_nodes_checked > 0` on `AGENT_FILES.node_status` |
| Control (admin account, probe 3's schema text, our read guard) | RAW 5 of 5 (476) | 4 counted `recorded_stage.lymph_nodes_positive`, 1 `stage_check.lymph_nodes_positive` |

The claim (at least 4 of 5 agent calls return 479) was **met**, and the control replicated probe 3. No query in either arm was refused: the agent never tried a table it could not read. The prediction held: 4–5 correct, 0 refusals, a 4–5 raw control, 0–1 failures.

## What it means, and what it does not

- Across probes 1–3 and this control, the agent counted the raw column in every query it wrote, whatever the schema text said. Here the layer changed instead of the prompt: an account that can only read the checked values. The same agent, prompt and question gave the checked answer 5 times out of 5.
- **This is right by construction.** The agent did not get better; it had nothing else to count. The finding is where the fix lives: in the layer's permissions, enforced by Zetaris, not in prompting the agent.
- **Probe 4 and probe 5 together:** told to correct a record, the agent tried to overwrite the registry, and our query check refused it. Given an account limited to checked values, it answers from them. Zetaris itself refused that account everything else in the check.
- 479 counts every record with a positive checked count. The 3 records the verdict leaves to a person have an empty checked count, so they are not counted (probe 2's single checked-column query counted them back in from the raw count, giving 482).
- **Limits:**
  - The table is a snapshot (`scripts/agent_view_snapshot.py`, CSV sha16 `a24c459579150519`), not live.
  - One model, one question, n = 5 per arm.
  - The role, user and grants were set up by the builder in the Zetaris GUI; their names are in the pre-registration.
