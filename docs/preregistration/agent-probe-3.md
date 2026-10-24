# Pre-registration: does an agent use the verdict when the layer hands over its own DQ rules? (written 2026-10-24, frozen before the first call)

`python -m app.cli agent-probe-3` refuses to run if `app/engine/agent_probe3.py`, `app/engine/agent_probe.py` (reused unchanged) or either schema text differs from the hashes in `agent-probe-3.json`.

## Why (disclosed)

The third look at one question, designed after two published misses: a pointer to the verdict in the column descriptions was used 0 of 10 times (`docs/evidence/agent-probe-results.md`), and a checked column beside the raw one was read 1 of 5 (`agent-probe-2-results.md`). A claims audit on 2026-10-24 then found that the layer's own contract (`LOAD USL`) already carries every registered data-quality rule at table level, with its name and SQL expression; neither probe showed them to the agent. Reviewed before freezing by an outside model and a council (`open-agent/research/council-9-four-tests-2026-10-24.md`), whose changes are adopted: closed codes with integers computed in advance, the rule block as the only difference, a strict claim line. The first two probes stand as published.

## Design

- **Agent, prompt, question, budget:** the first probe's, reused unchanged (`app/engine/agent_probe.py`): Super VL through Nightshift, pinned, signed, no cache, 4k thinking budget, "How many patients are node-positive?", one read-only SQL query, run unchanged, errors never retried. Item ids are new (`agent-p3-{run}-{arm}-{i}`), one per call.
- **Two arms, 5 calls each, interleaved** (control, treatment, ...):
  - **control** (`agent-schema-p3-control.txt`, 8,723 characters): today's schema text exactly as `schema_text()` renders the live `LOAD USL` contract: the four "audited:" pointers and the checked column `positive_nodes_checked` are in it. It is not probe 2's text: since then the tables come in a different order and the two count columns gained "stored as decimal text such as 4.0". So the control is a fresh baseline, not a replication.
  - **treatment** (`agent-schema-p3-rules.txt`, 10,332 characters): the same bytes plus, under each table that has rules, the line `DATA QUALITY RULES:` and one line per rule, `name: expression`, in contract order, whitespace collapsed (`stage_check` 7 rules, `recorded_stage` 1). Nothing else: no instruction to use them, no explanation of which way an expression points (a row passes when the expression is true), no selection. The rules' `cte` fields are empty and not shown; the 13 generated key rules are not in `dqAnnotations` and not shown.

## Codes (frozen; integers computed before freezing, queries in the json)

Each answered call gets one code from its SQL and the number it returned, in this order:

1. **FILTER:** the SQL contains a registered expression verbatim (case and spacing ignored), or returns a rule-filtered count (node-positive by the raw count AND one rule or its negation, or all 7 rules): 461, 15, 475, 1, 463, 13, 359, 117, 471, 5, 463, 13, 473, 3, 341.
2. **CORRECT:** the SQL uses `fault_field`, does not read `positive_nodes_checked`, and returns a verdict-corrected count: 479 (count-based, review rows left out), 482 (review rows counted from the raw count), 557 (N-based, review left out), 560 (N-based, review by N).
3. **CHECKED:** reads `positive_nodes_checked` and returns 479.
4. **CHECKED_FALLBACK:** returns 482 otherwise.
5. **RAW:** returns 476.
6. **OTHER:** anything else, including SQL errors and empty answers.

Collision, disclosed: the verdict-corrected count equals the checked column's count (479) because the checked column is the verdict applied; the integer alone cannot separate them, so the code also reads the SQL. A query that reads both `fault_field` and the checked column is coded CHECKED (conservative).

## Measures, claim, void

- **Primary:** CORRECT calls per arm.
- **Claim** "given the layer's own data-quality rules, the agent uses the verdict" only if treatment CORRECT is **4 of 5 with control 0 of 5**, or **5 of 5 with control at most 1 of 5** (one-sided Fisher 0.024 for both). The denominator is all 5 slots; a provider failure is a non-success. Otherwise the coded table is the result and the README states no rate.
- **Secondary (registered):** FILTER per arm; every code and number; SQL errors.
- **Void arm:** more than 2 provider failures. Two failures in the treatment arm already make the claim unreachable; that is a miss, not a reason to re-run. Never re-run, no extra calls, nothing tuned after the run.

## Prediction (before the run)

Treatment: the agent mostly copies rules into its filter or counts the raw column (FILTER or RAW), CORRECT 0 or 1 of 5; control: RAW or CHECKED, CORRECT 0. The claim is not met. A guess, written down so the result can contradict it.
