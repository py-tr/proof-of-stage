# Pre-registration: Super VL reads the scan itself (written 2026-10-24, frozen before the first model call)

`python -m app.cli vision-scan` refuses to run if `app/engine/vision.py`, `app/reader/reader.py`, `quotes.py`, `app/scans/scans.py` or the prompt differ from the hashes in `vision-scan.json`.

## Question

The scan rung (R3) today reads Nemotron Parse's text of the original PDF; Super VL, a vision-language model, never sees a page in the product. Can Super VL read the scanned pages as images and reach the same guarded values as the Parse + Super pipeline?

## Design

- **Cases:** the first 6 review-queue cases (sorted) that were never scanned before and have a pathology-report PDF on the GDC: TCGA-A1-A0SN, A2-A0EW, A7-A26H, AC-A2FK, AN-A0XN, AN-A0XP (selected 2026-10-24 by downloading PDFs only; no model call). None is one of the 6 scan-box cases the Parse box pipeline was designed on.
- **Path A (today's R3):** Nemotron Parse (v1, NVIDIA direct) reads every page; Super VL reads Parse's joined text through Nightshift (pinned, signed, no cache), 4k thinking budget.
- **Path B (new):** Super VL reads the page images (the same rendered pages, JPEG) on NVIDIA direct, because Nightshift returns HTTP 502 on images (`docs/evidence/nightshift-limits.md` §7); 4k thinking budget; no signed receipt (the served model id is checked).
- Both paths: the reader's system prompt unchanged; the same guard, run on Parse's text of the same pages (a quote must be found there and show its value). Path B's quotes come from reading the image, so OCR differences between the page and Parse's text count against it; that is part of what is measured.

## Measures (fixed now)

- Per case and field (N, the positive-node count): **same** (both paths accept the same value), **contradicts** (both accept, different values), **only A**, **only B**, **none**.
- Seconds and completion tokens per path; failures listed, never re-run.

## Kill line

- **The image read passes** only if, on at least 4 of the 6 cases, path B accepts the same value as path A on every field path A accepted (and at least one field), **and** no field contradicts anywhere. Then the README may say Super VL can read the original scan as a second witness. Otherwise the table is the result, Parse stays the scan reader, and the README says so. Nothing is re-tuned after the run; nothing is wired into the ladder in this run.

## Prediction (before the run)

Path B matches path A on 3 or 4 of the 6 cases; most misses are path B's quotes not found in Parse's text (OCR differences), not contradictions. A guess.
