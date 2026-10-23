# Pre-registration: does an agent that reads the layer's descriptions use the verdict? (written 2026-10-23, frozen before the first call)

`python -m app.cli agent-probe` refuses to run if `app/engine/agent_probe.py`, the prompt or either schema text differs from the hashes in `agent-probe.json`.

## Question

The README claims that a semantic layer gives meaning, not truth, and that our layer carries a per-record verdict (`stage_check.fault_field`) with pointers to it in the descriptions of the N and count columns. Does an agent that knows the layer only through its descriptions actually use the verdict when asked a plain question, and do the pointers change that?

## Design

- **Agent:** Nemotron Super VL through Nightshift (pinned in the signed receipt, verified against the pinned key, no cache, a new item id per call), thinking budget 4,000.
- **What it sees:** a fixed instruction (write ONE read-only SQL query returning one number, fully qualified names, JSON out) and the layer's 8 tables with every column and its description, exported from the live contract on 2026-10-23 into `agent-schema-with.txt`. No row values, no example query, no counts, nothing from `usl demo`.
- **Question:** "How many patients are node-positive?"
- **Two arms**, 5 calls each, interleaved (with, without, with, ...):
  - **with:** the descriptions as they are in the layer (the N and count columns carry the pointer "audited: where this field and the other node field cannot both be true, stage_check.fault_field names the field the report contradicts");
  - **without:** the same text with only those 4 pointer sentences removed (`agent-schema-without.txt`); `fault_field` and its own description are still listed.
- Each query runs **unchanged** through the read guard on the live layer. A guard refusal or SQL error is a result for that call, never retried or repaired.

## Measures (fixed now)

- **Primary:** queries that use `fault_field`, per arm (out of the calls answered).
- Secondary: queries that use the N column, the count column or the report reading; SQL errors; the number each query returns (compared afterwards with 336 / 328 / 333 from `usl demo` step 11, which counts a narrower cohort, so a different number is not by itself wrong).

## Kill and void lines

- **"The pointer changes the agent's query"** is claimed only if at least 4 of 5 *with* queries use `fault_field` **and** at most 1 of 5 *without* queries do. Otherwise the 10 queries and their numbers are published as the result, and the README says the descriptions did not (or did not alone) change the agent's answer.
- **Void arm:** more than 2 provider failures in an arm; that arm is reported per call only. Never re-run, no extra calls.
- Nothing is tuned after the run: not the prompt, not the descriptions, not the question.

## Prediction (before the run)

The *without* arm counts from one registry column (most likely the N column) in most calls; the *with* arm uses `fault_field` in some calls but not reliably 4 of 5, because the pointer is one clause in a long schema. A guess, written down so the result can contradict it.
