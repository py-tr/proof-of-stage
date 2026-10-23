# 0005: First write wins

**Context.** The same case can be read many times (re-runs, budget changes, guard fixes). If each read overwrote the last, a reviewer's decision could end up resting on a value that changed after it was made.

**Decision.** Readings and decisions go into append-only tables in Zetaris Postgres; a field keeps its first stored value (`kept-earlier` in `app/engine/run_case.py`), and every reviewer decision is a new row in `oa_pg.flag_log`. The case page shows whether the latest ladder run still reads the stored value, but never replaces it.

**Evidence.** On the 25 queue cases (2026-10-23, after the evening re-run of the 2 errored cases), the latest run matches 40 of the 41 stored report values; on the other the latest read gives the same main category less precisely (TCGA-A2-A0EW: N2A stored, N2 latest).

**Cost.** A stored value from an older guard stays until a person acts on it. That is the point, but it means the page has to show how a value compares with the latest read.
