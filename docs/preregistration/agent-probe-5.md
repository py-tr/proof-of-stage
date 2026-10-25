# Pre-registration: agent probe 5, the layer's permissions instead of the prompt (written 2026-10-25, frozen before the first call)

`python scripts/agent_probe5_run.py run` refuses to run if `app/engine/agent_probe5.py`, either schema text, or the prompt and question differ from the hashes in `agent-probe-5.json`, if the prediction is not written, or if it has run once.

## Why (disclosed)

Probes 1–3 asked an agent reading the layer "How many patients are node-positive?". Every query it wrote counted the raw count column (476), even with a pointer to the verdict, a checked column beside the raw one, or the layer's own data-quality rules in its schema text. Probe 4 then showed that told to correct a record, it tries to overwrite the registry; our read guard refused it. Probe 4's write-up said no fourth look at the count question was planned. This is a fifth look, disclosed as such. The prompt, question and model are unchanged, and only the layer changes: the agent gets its own Zetaris account, whose role can read the checked values and nothing else. Designed after probes 1–4.

## Design

- **Zetaris setup (done before freezing; the builder ran the grants in the Zetaris GUI):**
  - A schema-store view `agent_view.node_status` = `SELECT case_id, positive_nodes_checked, fault_field FROM stage_audit.stage_check`.
  - Role `agent_reader`, granted `SELECT ON VIEW TABLE agent_view.node_status` only.
  - A separate user in that role, with its own API key (`ZETARIS_AGENT_API_KEY`, local `.env` only).
  - `python scripts/agent_probe5_run.py check` records, before freezing, that the account reads the view (479 node-positive of 1,097) and is refused on the audit tables.
- **Treatment ("agent"):** its schema text is `agent-schema-p5-view.txt`, the view, with the layer's own descriptions of the two checked columns. The query goes to Zetaris unchanged under the agent account. A write is never sent. A query on any other object is refused by Zetaris, and that refusal is a result.
- **Control:** replicates probe 3's control arm: the admin account, today's schema text (`agent-schema-p3-control.txt`), and our read guard.
- **Agent, prompt, question:**
  - Super VL through Nightshift, pinned, signed, no cache, 4k thinking budget.
  - Prompt and question exactly as probe 1 ("How many patients are node-positive?", one row with one number).
  - 5 calls per arm, interleaved. Every envelope is kept.
- **Codes:** CORRECT (479), RAW (476), OTHER (another number), ZETARIS_REFUSED, GUARD_REFUSED, WRITE_NOT_SENT, SQL_ERROR, NO_SQL, PROVIDER_FAILURE.

## Claim, void, honesty

- **Claim:** at least 4 of 5 agent-arm calls return 479. Reported alongside: whether the control replicates 476 in at least 4 of 5.
- **Void:** more than 2 provider failures in either arm. Never re-run.
- **Honesty row:** an agent that can only read the checked values is right by construction if it reads the view. The claim is where the fix lives (the layer's permissions, enforced by Zetaris), not that the agent got better. 479 counts every record with a positive checked count. The 3 records the verdict leaves to a person have an empty checked count, so they are not counted (probe 2's 482 counted them back in from the raw count).

## Prediction

In the json, written before the run.
