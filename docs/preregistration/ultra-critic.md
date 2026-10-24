# Pre-registration: Ultra as a second reader that can only object (written 2026-10-24, frozen before the first call and before the blind labels are frozen)

`python -m app.cli ultra-critic` refuses to run if `app/engine/critic.py`, `app/engine/second_reader.py`, `app/reader/reader.py`, `app/reader/quotes.py` or the prompt differ from the hashes in `ultra-critic.json`. Designed by a combo council (research/combo-council-CHAIR-final-2026-10-24.md in the project knowledge base), including a skeptic's fixes.

## Question

Our guard checks that a quote is in the report and shows its value; it does not ask whether the report says something else elsewhere (a total in another part, a printed category). Can Nemotron Ultra, as a second reader that may only object, catch stored values that the report contradicts, without crying wolf?

## Design

- **Population:** every report value the layer stored for the 25 review-queue cases (`stage_check.report_n` / `report_nodes_positive`, first write kept): **41 values**, each with its accepted quote (none missing).
- **Planted control (disclosed):** 5 rows (3 counts, 2 N categories) built with seed 20261024 from real (case, field) pairs: the value shown is another queue case's stored value for that field, different from the real one; the quote shown is the real one. Frozen in `ultra-critic.json` (TCGA-A7-A26H count, E2-A1B4 count, A1-A0SN count, AC-A2FK N, AR-A1AT N). Interleaved with the real rows, logged `planted`, never stored, tallied apart. Limit: it checks that the critic fires and quotes verifiably against a wrong value, an easier task than catching a real miss.
- **Calls:** 46, one after another; Ultra (`nvidia/nemotron-3-ultra-550b-a55b`) through Nightshift, pinned in the signed receipt, verified against the pinned key, no cache; thinking on without a budget (the hosted Ultra rejects a reasoning budget); max_tokens 8,000. Ultra sees the field, the stored value, its quote and the full report, and answers agree / contradiction (a value and ONE verbatim quote) / cannot tell.
- **The check on an objection:** the reader's own guard (`judge_field` / `judge_count`): the quote must be in the report and show the objecting value, and that value must differ from the stored one (N by main category).
- **Effect:** none in this run. Nothing is written to the layer; an objection could only ever send a case to a person, never accept or change a value. The log is committed unread and scored only against the frozen labels.

## Measures (fixed now)

- Over the 41 real rows, every class: agree / contradiction verified / contradiction unverified (with the guard's reason) / cannot tell / unusable / provider error; seconds and completion tokens.
- After the labels: verified objections **right** (the label disagrees with the stored value), **wrong** (the label agrees), **unscored** (the label states no value); **missed** = agree or cannot tell where the label disagrees; every objection listed with both quotes.
- Plants: **detected** = a verified objection on a planted row; and whether the objected value equals the real one.
- **Only the first completed run counts** (the first run that wrote a summary row); an aborted run is listed and excluded; no row is ever re-called.

## Ship line and void

- **Void:** more than 8 provider failures or more than 8 unusable answers among the 41 real rows; then a per-row report only, never re-run.
- **Ships** (a read-only line on the case page and a `/how` card from the log; never a `flag_log` write before submission) only if **plants detected ≥ 4 of 5** with verified quotes **and** verified objections on real values **≤ 8** **and right > wrong** **and wrong ≤ 1**. Otherwise the evidence file says "Ultra as a second reader: measured, not on the critical path". Written either way; a "wrong" objection may be a label error and is published with both quotes; no relabelling, no prompt change, no second run.

## Prediction (before the run)

At most 3 verified objections on the real values; plants detected at least 4 of 5. A guess.
