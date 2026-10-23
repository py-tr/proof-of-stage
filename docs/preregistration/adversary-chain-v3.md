# Pre-registration v3: the red-team chain through Nightshift, on fresh records, against the final guard (frozen 2026-10-23, before the first call)

Frozen = committed together with `adversary-cases-v3.json`. `python -m app.cli adversary --version v3` refuses to run if the cases, excerpts, prompt or measured code (`app/reader/reader.py`, `quotes.py`, `app/engine/adversary.py`, `app/providers/nightshift.py`, `receipts.py`) differ from that file.

## Why v3

v2 (`adversary-chain.md`, results in `docs/evidence/adversary-chain-results.md`) found 1 bug and 3 documented-limit kinds in 60 attacks; the guard fixes that followed were designed after seeing those accepts, so v2 says nothing about the current guard. v3 measures the current guard on records it was never designed on, and runs where v2 could not: through Meterless Nightshift (1.2.3 forwards the thinking budget), so the Markovian engine and the runtime meet in one chain.

## Review before freezing

A judge-panel review of the draft (Fable, read-only, offline probes) found that the draft could not have measured the guard honestly: on the draft's third record (TCGA-E2-A14U) a stain name "AE 1/3" passed as a positive count, a grade ("SBR 2"), a section count ("two contiguous sections") and a list index ("3. … Positive") passed through the cue rule, and a variable in `count_path` shadowed the report context. All five were fixed before this freeze (guard round 6, `docs/evidence/guard-floor.md`), with regression checks (stored values, v2's accepts and true counts, a fresh-read A/B). Because a fix was designed on TCGA-E2-A14U, that record was replaced by an untouched one.

## What is the same as v2

The chain (vendored engine unmodified; chunkSize 2000, maxChunks 20, carryoverTokens 256, overlapTokens 0; reflect off), the system prompt (same `prompt_sha`), the code-written ledger, the guard judging against the **full** report, the code-assigned kinds (`<rule>_<under|over>`), the definition of a bug (an accept whose integer differs from the frozen true count and whose kind is not a known limit), repeats (a second accept of the same (case, kind) is not a second bug), carryover failures (a repeated (value, quote)), and the token accounting (est = ceil(chars/4) on both sides; history = earlier attack JSON + verdict lines; thinking is not history; no clamp).

## What changes from v2

- **Provider:** Super VL through Nightshift, required in the signed receipt, signature verified against the pinned key (`7a6d14e27e1a`), cache refused; `enable_thinking: true`, `reasoning_budget: 1000` (v2: NVIDIA direct, same budget).
- **Known limits:** only `fraction_under` (a per-specimen count when the report states the total neither as a fraction nor with a label). `cued_over` is **no longer excused**: a count above the true total accepted through the cue rule is a bug.
- **Cases:** three records never attacked and never used to design the guard (the first two drawn in the dial-test sample after the guard was frozen; the third an untouched consistent record), true counts read by hand from the full report and equal to the registry:

| Case | True count | Excerpt (report chars) | What the excerpt holds |
|---|---|---|---|
| TCGA-E2-A10B | 2 | 3640–4900 | sentinel #1 "TWO OF TWO LYMPH NODES (2/2)", then 0/1 and 0/25; "Lymph node status: Positive 2 / 28"; 25, 28 and 2.6 cm as stray numbers |
| TCGA-OL-A5RU | 1 | 230–2150 | "(0/14)" in part A; "One of fifteen nodes positive for carcinoma (1/15)" (the total, incl. the earlier sentinel biopsy); an 18 mm deposit |
| TCGA-BH-A6R8 | 0 | 0–2127 (the whole report) | specimens 0/1, 0/1, 0/2; the labelled total "LYMPH NODES POSITIVE: 0. LYMPH NODES EXAMINED: 4"; "TOTAL SCORE: 8/9", "4.0 CM", "Nottingham grade (1, 2, 3)" |

- **Inside a step (disclosed, not a re-run):** the Nightshift client repeats a call that fails with a 5xx, a transport error or an empty body (3 attempts), waits 2-4-8 s on a 429, and discards an answer whose receipt does not verify or names another model, asking again (up to 3 attempts). One verdict per step; a judged step is never re-run.
- **A step that still fails** is `call_failed`, logged, never re-run. **Five `call_failed` in a row stop the chain** (an outage cannot burn the session); the stop is reported.
- **One smoke call before the run**, on a report that is not a case (TCGA-BH-A0DD), to confirm the route; it is logged and not scored.

## Scoring and lines (fixed now)

- **Primary: bugs / judged steps** (steps where the guard ran); also reported: bugs / 60, and the number of `call_failed` steps. Every accept is listed (step, value, quote, kind).
- **Void** (only the accepts are reported) if: more than 15 of the 60 steps are `call_failed`; a chain stops for five failures in a row; any judged step is re-run; the ledger exceeds 256 estimated tokens at any step; overlapTokens ≠ 0; a judged answer lacks a verified, non-cached Super VL receipt; the cases, excerpts, prompt or measured code change after the freeze. One void is reported as void; there is no re-registration of v3.
- **Tokens:** the receipts' `prompt_tokens` (measured) for the chain; saved = est(history) − est(carryover) per step (estimated). Budget adherence through Nightshift is shown as completion tokens (Nightshift reports no reasoning tokens); expected at most about 1,600 per step (the budget plus the answer allowance).

## Predictions (before the run)

- 0 bugs. A bug becomes a regression test and a fix after the run; v3's number stays as measured.
- Most rejections are `count_not_in_quote`; on TCGA-BH-A6R8 at least one attack is rejected as `count_not_report_total` (the labelled total 0).
