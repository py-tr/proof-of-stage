# Super VL reads the scan itself: results (pre-registered, run 2026-10-24)

Pre-registration: `docs/preregistration/vision-scan.md` + `vision-scan.json` (commit 7d7cacb, frozen before the first model call; the run checked the hashes at start). Logs: `logs/vision-scan.jsonl` (per case: both paths' fields, quotes and reasons), `logs/vision-scan-runs.jsonl`, `logs/vision-scan-2026-10-24.txt`. Run 2026-10-23 23:05 UTC.

## Validity

6 of 6 cases run, 0 failures. Path A (Parse v1 on every page, NVIDIA direct; then Super VL on Parse's text through Nightshift, 4k budget): every Super answer signed by the pinned key. Path B (Super VL on the page images, NVIDIA direct, 4k budget): every answer served as `private/nvidia/nemotron-3.5-super-120b-a12b`, the alias NVIDIA's API serves for the requested `nvidia/nemotron-3.5-super-vl-120b-a12b`; no signed receipt (Nightshift 1.2.3 refuses pinned image requests with `no_vision_model`, a gate-ordering bug; see `docs/evidence/nightshift-limits.md` §7). 18 pages in total (5, 5, 3, 3, 1, 1).

## Result

| Measure | Result |
|---|---|
| **Cases where path B matches path A on every field A accepted** | **4 of 6** |
| Fields: same value / contradicting / only A / only B / neither | **6 / 0** / 2 / 1 / 3 |
| Seconds, the Super reads only (B on images, A on Parse's text; Parse itself not counted) | 120 / 176 |
| Completion tokens | 19,044 / 19,064 |

Kill line (path B matches on at least 4 of 6 cases, and no field contradicts): **met**. As pre-registered, the README may say Super VL can read the original scan as a second witness; nothing was wired into the ladder.

Prediction (before the run): "path B matches on 3 or 4 of the 6; most misses are path B's quotes not found in Parse's text, not contradictions." **Held.**

## Per case (statuses only; values are in the log)

| Case | Pages | N | Count | Note |
|---|---|---|---|---|
| TCGA-A1-A0SN | 5 | same | same | |
| TCGA-A2-A0EW | 5 | only A | only A | both of B's quotes not found in Parse's text (`quote_not_in_report`) |
| TCGA-A7-A26H | 3 | neither | only B | A's quotes failed the guard (`quote_does_not_support`, `count_not_in_quote`); B's count passed |
| TCGA-AC-A2FK | 3 | same | same | |
| TCGA-AN-A0XN | 1 | same | neither | a one-page summary form: N printed, no count (both abstained) |
| TCGA-AN-A0XP | 1 | same | neither | the same form |

## What it means, and what it does not

- Reading the page images, Super VL reached the same guarded values as the Parse pipeline on 4 of 6 scans and never a different one; on one scan it settled a field the text path could not.
- Two of the 4 matching cases are one-page summary forms where only a printed N is at stake, so the multi-page agreement is 2 of 4 (A1-A0SN, AC-A2FK). n = 6: a pass of a pre-registered line, not a rate.
- The guard ran on Parse's text, so path B's quotes had to match Parse's OCR of the same page; the one full miss (A2-A0EW) is exactly that, not a wrong value.
- Path B is NVIDIA direct, without a signed receipt; through Nightshift it is not possible yet on this setup.
- Parse stays the scan reader on the page (its boxes are what the case page draws); this shows Super VL can serve as a second, independent witness on the same scan.
