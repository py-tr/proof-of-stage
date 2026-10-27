# Nemotron 3.5 Bolt at the first read (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/bolt-r1.md` + `bolt-r1.json` (frozen before the first call). Run 20261025T184813, log `logs/bolt-r1.jsonl`, summary `logs/bolt-r1-runs.jsonl`. The shipped evidence chain's first read only (`rungs.climb(..., abort_after=1)`, closing rule unchanged: the first read may close only a field that agrees with the registry), with `nvidia/nemotron-3.5-bolt-e4b` in Lightning's place, thinking off, NVIDIA direct. The dial test's 30 records; referee the always-4k Super VL read logged by today's shipped-cost run.

## Result

| On the same 30 records | Records settled | Closings vs the 4k read | Completion tokens |
|---|---|---|---|
| **Bolt (E4B), this run** | **16 of 30** | 32 agree, **0 contradicted**, 2 unconfirmed | 4,414 |
| Lightning (shipped), shipped-cost run | 17 of 30 | 33 agree, 0 contradicted, 3 unconfirmed | 5,599 |

0 provider failures. **Claim** (at least 14 settled, 0 contradicted): **met**.

Prediction (before the run): "Before the run, by the coding agent: Bolt settles 10-17 of 30 (a smaller model may abstain or misquote more often than Lightning's 17); 0-2 closings contradicted (claim uncertain: a contradiction kills it); 0-2 failures."

## What it means, and what it does not

- The edge-sized Nemotron does the first read almost as well as Lightning on these consistent records (16 vs 17 settled), with no contradiction and fewer completion tokens: NVIDIA's "execution routes down", one size further.
- It does not ship: Nightshift has no Bolt lane, and every text call the product makes goes through Nightshift (decision 0004). It is an edge candidate, measured; on a machine that runs Bolt locally it is the natural first read.
- Easy records (registry fields agree), n = 30, one run, no re-run; tokens, not price.
