# Nemotron Parse 2.0 vs Parse v1 in the shipped scan pipeline: results (pre-registered, run 2026-10-24)

Pre-registration: `docs/preregistration/parse-bench.md` + `parse-bench.json` (commit add7cb5, frozen before the first call). Run 20261024T171040, log `logs/parse-bench.jsonl`, summary `logs/parse-bench-runs.jsonl`. The overlay packet (scan images) stays local in `data/scans/_parse_bench/` (not committed); the item map (`logs/parse-bench-map.json`, SHA-256 4ba88e59… logged before scoring and re-checked) and the builder's scores (`logs/parse-bench-scores-builder.json`) are committed.

## Result

| | Parse v1 (shipped) | Parse 2.0 |
|---|---|---|
| Pages | 14 read, 0 failures, 0 empty | 19 called: **7 read, 12 empty** (finish_reason "length", 3,500 completion tokens, no text) |
| Super reads on the joined text | 6 of 7 (TCGA-A1-A0SN: Nightshift 502, a provider failure, not re-run) | 7 of 7 (5 abstained on empty text) |
| Accepted value equal to the frozen layer value | 10 of 12 pairs | 2 of 12 |
| Box judged "on the line" (builder, two passes, blind) | 6 of 10 boxed values | 1 of 2 |
| **Pairs passing** (value and box) | **6 of 12** | **1 of 12** |
| Discordant pairs | v1 only: A2-A0EW count, A7-A26H N and count, AC-A2FK N and count | none |

**Ship rule** (v1-only passes = 0, 2.0-only ≥ 1 on a multi-page case, 2.0 empty/truncated pages ≤ v1's): **not met** on every condition. **v1 stays**; 2.0 is a measured row. Not void (0 provider page failures; the 12 empty pages are answers, counted as truncated). Prediction ("value agreement about equal; boxes similar; ship rule not met slightly more likely"): the decision held, the "about equal" part did not.

## What it means, and what it does not

- Hosted Parse 2.0 was intermittent in our runs: the first 7 pages came back normally (stop, about 2 s), then every page from the 8th on came back empty at the token limit (about 6 s each), the behaviour seen on 10-19 (a pre-window probe) and 10-22. Same image preparation throughout, so the cause is on the service side; it works some of the time.
- v1's boxes on cases not used in design: 6 of 10 on the right line. The 4 misses: the one-page summary form (AN-A0XN, AN-A0XP; boxes a line above or below, the failure mode the design spike found) and TCGA-BH-A0DD (both boxes one line low on a multi-page report).
- Scored by the coding agent (Claude Code), twice, on the shuffled packet before reading the map; the second pass is not independent of the first. The builder's own pass can only remove passes (any split is a non-pass) and so cannot change the decision.
- Not tested: 2.0 at NVIDIA's documented larger canvas, or 2.0 on a day the service is stable. No re-run.
