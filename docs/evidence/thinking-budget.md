# Super thinking-budget table (2026-10-22)

*Pre-existing, declared in `metadata.json`: the 42-report set and its truth labels, the confirm and honesty runs and the unlimited arm (2026-10-21 ~20:00 UTC) come from spikes before the build window; the off, 1k and 4k arms ran 2026-10-22 10:19–11:35 UTC in the same spike, outside this repository, before its first commit.*

PREREG.md was written before any call, and `test_score.py` passed its 3 hand cases before calling. Items: the same 42 fresh TCGA-BRCA reports and GDC T/N truth as the confirm and honesty runs, so 84 fields in total.
Model: Super `nvidia/nemotron-3.5-super-vl-120b-a12b`, the same id as the honesty run. The prompt is the honesty run's plain direct prompt, unchanged, and is scored with the honesty scorer's `parse` (also unchanged).
Calls: 2026-10-22 10:19–11:35 UTC. 140 HTTP attempts (the cap), temperature 0.

**How the budget was set.** It used `chat_template_kwargs {"enable_thinking": true, "reasoning_budget": N}`. **The NVIDIA endpoint honours it on Super.** The 1k arm stopped at exactly 1,023 reasoning tokens on 23 items, and the 4k arm at 4,095 on 2 items. Every item stayed at or under budget + 32 (42/42 in both arms), so the fallback was not needed.
Exactly what was sent, besides the model, the messages and temperature 0:
- OFF: `{enable_thinking: false}`, max_tokens 1200.
- 1k: `{enable_thinking: true, reasoning_budget: 1024}`, max_tokens 2048.
- 4k: `{enable_thinking: true, reasoning_budget: 4096}`, max_tokens 5120.
- Unlimited: the honesty run's `llm_super` (thinking on, no budget, max_tokens 32000, run 2026-10-21 ~20:00 UTC). It was reused and made no new calls.

## Table (n = 42 items, 84 fields; a missing, unparseable or TX/NX field counts as wrong)

| Arm | Both right /42 | Wrong fields /84 | Median latency | p90 latency | Median completion tokens (median reasoning) | Finish reasons | Truncations | Fixed / broke vs OFF |
|---|---|---|---|---|---|---|---|---|
| **Thinking OFF** | **26/42** (26/41 answered) | 19 (17/82 answered) | **0.6 s** | 7.0 s | **19** (0) | stop 41; 1 item missing (cap) | 0 | n/a |
| **Budget 1k** | 28/42 | 15 | 13.8 s | 48.6 s | 1,039 (1,023; the budget bound on 23/42) | stop 42 | 0 | +4 / −2 |
| **Budget 4k** | **30/42** | **13** | 17.5 s | 50.9 s | 1,002 (985; bound on 2/42) | stop 42 | 0 | +5 / −1 |
| Unlimited (honesty run, reused) | 30/42 | 13 | 8.9 s | 37.0 s | 1,034 (1,015; max 4,558) | stop 42 | 0 | +5 / −1 |

Notes on the table:
- Fixed/broke counts both-right flips per item against OFF. The OFF arm has no answer for TCGA-AR-A5QN, which every thinking arm gets right. On the 41 items OFF answered, the "fixed" counts are 3 / 4 / 4 (1k / 4k / unlimited). On the same 41 items, both-right is 26 / 27 / 29 / 29.
- **4k = unlimited, item for item:** all 42 predictions are identical. Only 1 of the 42 items ever needed more than 4,096 reasoning tokens, and capping it changed nothing.
- **1k costs two items against 4k.** TCGA-BH-A18N went from T2 to T4b, a new error that OFF had right. TCGA-GM-A2DI was T1/N1mi under 1k against T1/N0 under 4k and truth.
- Latency is load-sensitive across sessions. The budget arms ran 14 h after the unlimited arm on a busier endpoint (13 HTTP 500s and 2 dropped connections at about 340 s in this run). Completion tokens are the fair cost comparison. The 4k and unlimited arms spend the same median tokens (about 1,000), so the latency gap between them is load, not budget.

## What it shows

On a pathology-report extraction task (42 easier reports, not the review queue), Super's reasoning dial does what NVIDIA documents, and it is measurable on the hosted API. `reasoning_budget` is enforced closely: every item stayed at or under the budget + 32 tokens (42/42), with no truncations once max_tokens = budget + 1024. Thinking OFF already gets 26/42 at about 19 tokens and 0.6 s. Thinking adds 4 items (30/42) and removes 6 wrong fields (19 → 13), at about 1,000 completion tokens per item. A 4k budget keeps all of that gain: its predictions are identical to unlimited thinking on all 42 items. A 1k budget keeps half of it (28/42). So the shippable setting is "OFF for the cheap first pass, 4k budget for the Super seat". That gives a hard, predictable cost and latency ceiling per item at no accuracy loss on this sample. Honest limits: n = 42, so 26 vs 30 is a signal, not a claim. The budget mainly protects the tail (max reasoning 4,558 → 4,095), because the median item needs only about 1k reasoning tokens.

## ⚠ Didn't run properly

- **Start-gate deadlock (about 13 h lost).** The waiter `tb.py wait` treated any python `run.py` process and any recent write in the other spikes' `data/` folders as activity. The other spikes' waiters did the same, and each waiter's 4-minute log writes kept the others from ever seeing "quiet". So all gates waited in a circle from 2026-10-21 ~20:50 UTC. The waiter was stopped, and `tb.py call` then `tb.py score` ran in a strict sequential chain (logged in the spike's folder). My own waiter log is `data/run.log`. My original chain also ran `tb.py score` once on empty data after the waiter was killed; the chain's later `score` overwrote that output.
- **The cap was hit one item short.** 140 attempts were used: 125 returned 200, 13 returned 500 and 2 were ConnectionErrors at about 340 s. OFF ran last, so it has no answer for TCGA-AR-A5QN. That item is scored as 2 wrong fields as pre-registered, which inflates OFF's wrong count by 2 and the fixed counts by 1. 41-item figures are given above. No retry beyond the cap was made.
- The unlimited arm is from a different session (2026-10-21 ~20:00 UTC), so its latency is not comparable like-for-like (see the note above).
- Temperature 0 is not deterministic on this endpoint. Logged on 2026-10-24: Super direct, thinking off, the same prompt 5 times at temperature 0 gave 4 answers (1 timed out), all 4 textually different (`logs/capability-retest-2026-10-24.jsonl`, probes `temp0-super-*`). There was one seed per arm.

*Written up on 2026-10-22 from the spike's notes (a pre-window spike, declared in `metadata.json`). The spike scripts and raw call logs are not committed.*
