# The scan witness, two sizes: Nano Omni vs Super VL (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/scan-witness.md` + `scan-witness.json` (frozen before the first call). Run 20261025T185306, log `logs/scan-witness.jsonl`, summary `logs/scan-witness-runs.jsonl`. Both models read the page images of the 13 review-queue cases with cached scans (38 pages), the reader's prompt, a 4k thinking budget, NVIDIA direct; the quote check ran on Nemotron Parse's text of the same pages; each N and count scored against the frozen blind labels.

## Result

| Model | Correct | Wrong | Not accepted | Completion tokens | Seconds | Failures |
|---|---|---|---|---|---|---|
| **Nemotron 3 Nano Omni** (30B, 3B active) | **11** | **2** | 8 | 38,343 | 879.7 | 0 |
| Nemotron 3.5 Super VL (120B, 12B active) | 11 | 3 | 7 | 37,836 | 804.7 | 0 |

**Claim** (Omni wrong at most Super VL's, correct at least Super VL's minus 2, **and fewer completion tokens**): **not met**, on the token clause only (38,343 vs 37,836: both spent most of their 4k budget). Kill not fired.

Prediction (before the run): "Before the run, by the main session: Super VL about 12-16 correct, 1-3 wrong on the 13 scans; Nano Omni about 9-15 correct, 1-4 wrong, with clearly fewer tokens; claim uncertain (a smaller model may misread digits on scans); 0-4 failures (Omni overload)."

## What it means, and what it does not

- On the scanned pages the small multimodal Nemotron read as well as Super VL against the blind labels (11 correct each; 2 wrong against 3), at a quarter of the active parameters. It did not use fewer completion tokens, because both models spent most of the thinking budget, so the pre-registered seat rule (which required a token saving) does not give it the scan-witness seat. It is a measured row: equal accuracy, smaller model, no token saving at this budget.
- The scan witness stays a measured, report-only capability (Super VL's earlier line: 4 of 6 cases matched, 0 contradictions); neither is wired into the shipped chain.
- n = 13 cases (26 values, 21 with a labelled value), one lay labeller, one run, NVIDIA direct (Nightshift refuses pinned image requests), no re-run.
