# Pre-registration: Nemotron Parse 2.0 vs Parse v1 in the shipped scan pipeline (written 2026-10-24, frozen before the first call)

`python -m app.cli parse-bench` refuses to run if `app/engine/parse_bench.py`, `app/scans/scans.py`, `app/providers/nvidia.py`, `app/reader/reader.py`, `app/reader/quotes.py` or the 2.0 prompt differ from the hashes in `parse-bench.json`.

## Why (disclosed)

Hosted `nemotron-parse-2.0` returned empty output on 10-19 and 10-22, so the pipeline ships v1. On 10-24 a retest found 2.0 working (NVIDIA released Nemotron 3.5 Embed, Rerank and Parse on 10-21). This asks whether 2.0 should replace v1 in the scan rung. Reviewed before freezing by an outside model and a council (`open-agent/research/council-9-four-tests-2026-10-24.md`). The 2.0 converter was written on one design page (TCGA-A2-A0CV page 0, logged in `logs/capability-retest-2026-10-24.jsonl`), not on these cases.

**Not held-out in the strict sense:** all 7 cases already have v1 reads (`blocks.json`), 6 of them were read by Super on Parse text in the vision-scan test and BH-A0DD by the ladder. None was used to design anything here; both models are called fresh, and the old v1 cache is not read.

## Design

- **Cases:** TCGA-A1-A0SN, A2-A0EW, A7-A26H, AC-A2FK, AN-A0XN, AN-A0XP, BH-A0DD (19 pages). AN-A0XN and AN-A0XP are the one-page summary form on which v1's boxes ran low in the design spike: a stratum, a win only there does not ship 2.0.
- **Same image for both:** each page as the pipeline already renders it (centred on the 1024×1280 canvas, greyscale, JPEG quality 60). NVIDIA documents a larger canvas for 2.0; it is not tested here, disclosed. So this compares the two models in the shipped pipeline, not each at its best.
- **v1:** `nvidia.parse_page` as shipped (markdown_bbox tool, max_tokens 3500). **2.0:** NVIDIA's documented prompt `</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>` with the image as a data URI, max_tokens 3500, temperature 0; the `<x_><y_>text<x_><y_><class_…>` output converted to v1's block shape by the frozen `parse2_blocks`.
- **Then the shipped pipeline on each model's own text:** pages joined (`join_pages`), Super VL reads at the 4k budget through Nightshift (pinned, signed), the guard checks the quote against that model's text, the box = the Parse block(s) holding the accepted span (`blocks_for_span`).
- **Unit:** 12 case × field pairs with a frozen layer value (N main category for all 7; positive-node count for the 5 that state one): see the json.

## Pass rule, judging, ship rule

- **A pair passes for a model** when the guard-accepted value equals the frozen layer value **and** the box is judged **"on the line"**.
- **Box rubric (written now):** *on the line* = a red box covers the printed line (or lines) that state the accepted value; *off* = the box is beside the line, more than half a line away, or covers only unrelated text; *missing* = no box drawn. One overlay image per (case, field, model) with a boxed accepted value; the overlays are shuffled with a fixed seed and numbered, and the item→case/model map is written and its SHA-256 logged before anyone scores.
- **Judges:** the builder (the coding agent) scores the packet twice, the second pass without the first's scores; the user scores once if available. A box counts as on the line only if every judge who scored it says so; any split is a non-pass (for both models).
- **Ship 2.0 only if:** v1-only passes = 0, 2.0-only passes ≥ 1 and at least one of them on a multi-page case, and 2.0's empty and truncated pages ≤ v1's. Otherwise v1 stays and 2.0 is published as a measured row. A page is truncated when finish_reason is "length", text is left unparsed, or completion tokens reach 3500; a truncated page's pairs are non-passes.
- **Void:** more than 2 provider page failures for either model. Never re-run, nothing tuned after the run.
- **Report-only:** discordant pairs listed; value-only agreement per model; seconds per page; v1 fresh vs the cached v1 blocks (drift). Super's reads are not deterministic at temperature 0 (logged 10-24), so a single discordant pair may be the reader, not the parser; disclosed.

## Prediction (before the run)

Value agreement about equal (10–12 of 12 for both); boxes similar, 2.0 maybe tighter on the multi-page reports; ship rule not met (v1 stays) is slightly more likely than met. A guess, written down so the result can contradict it.
