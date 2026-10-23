# Pre-registration: does an agent use a value the layer has already checked? (written 2026-10-23, frozen before the first call)

`python -m app.cli agent-probe-2` refuses to run if `app/engine/agent_probe2.py`, `app/engine/agent_probe.py` (reused unchanged) or either schema text differs from the hashes in `agent-probe-2.json`.

## Why (disclosed)

A new hypothesis, designed after the first probe's result (`docs/evidence/agent-probe-results.md`): a pointer to the verdict in the column descriptions was used 0 of 10 times, and the agent counted from the raw count column every time. Two reviewers (a council and an outside model) then recommended testing whether the layer offering the checked value itself, beside the raw one, changes that. The first probe's 10 calls stand as they are and are not re-scored.

## What changed in the layer (before this pre-registration)

- New column `stage_check.positive_nodes_checked` (commit c04b10a): the registry's positive-node count, except where the verdict (`fault_field`) is `node_count`, where the quote-verified report count replaces it; empty where the verdict is `review` or no count is recorded. Stored as a whole number. The raw `lymph_nodes_positive` stays in the layer and in the schema the agent sees. Named for what it holds, not for the question; its description says nothing about how to count patients. Limitation: its name and description, like the raw column's, share the word "positive" with the question.
- The read guard now accepts a declared table alias (commit 54ff42e); in the first probe it refused one query that used one.

## Design

- **Agent, prompt, question, budget:** exactly the first probe's (`app/engine/agent_probe.py`, reused unchanged): Super VL through Nightshift, pinned, signed, no cache, 4k thinking budget, "How many patients are node-positive?", one read-only SQL query, run unchanged, errors never retried.
- **Two arms**, 5 calls each, interleaved (control, treatment, ...):
  - **control:** the first probe's *with* text, byte for byte (`agent-schema-with.txt`): replication and drift check;
  - **treatment:** the same text plus one line, the new column and its description (`agent-schema-checked.txt`).
- **Expected number**, computed before freezing with one read-only query on the live layer: **479** records have `positive_nodes_checked` > 0 (the raw count gives 476: it misses the 6 patients the report shows node-positive and counts 3 the verdict leaves to a person).

## Measures (fixed now)

- **Primary:** treatment queries that read `positive_nodes_checked` **and** return 479.
- Secondary: per arm, queries reading the new column, using `fault_field`, using the raw count; SQL errors; every number returned.

## Kill and void lines

- **"Given the checked value beside the raw one, the agent uses it"** is claimed only if at least 4 of 5 treatment queries read `positive_nodes_checked` and return 479, **and** the control arm still uses `fault_field` in at most 1 of 5 (the first probe replicates). Otherwise the 10 queries and numbers are published as the result, and the README says a checked column beside the raw one was not enough either.
- **Void arm:** more than 2 provider failures; reported per call only. Never re-run, no extra calls, nothing tuned after the run.

## Prediction (before the run)

The treatment arm reads the new column in most calls (it is the one count column whose description mentions a check), but not reliably 4 of 5; the control arm repeats the first probe (the raw count, 476). A guess, written down so the result can contradict it.
