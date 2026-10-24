# 0005: First write wins

**Context.** The same case can be read many times (re-runs, budget changes, guard fixes). If each read overwrote the last, a reviewer's decision could end up resting on a value that changed after it was made.

**Decision.** Readings and decisions go into append-only tables in Zetaris Postgres; a field keeps its first stored value (`kept-earlier` in `app/engine/run_case.py`), and every reviewer decision is a new row in `oa_pg.flag_log`. The case page shows whether the latest ladder run still reads the stored value, but never replaces it.

**Evidence.** On the 10 records where the registry columns disagree, the latest signed runs reproduce all 18 stored report values (`docs/evidence/nightshift-provenance.md`). (Correction 2026-10-24: this entry used to cite 40 of 41 on all 25 queue cases; no committed file backs that count, so it is withdrawn.)

**Cost.** A stored value from an older guard stays until a person acts on it. That is the point, but it means the page has to show how a value compares with the latest read.
