# Parse bbox spike: results (2026-10-22 ~17:00 Prague)

Pre-registration: PREREG.md (kill line: ≥2 of 3 cases pass both "located" and "box right").

## Platform findings
- **Hosted `nvidia/nemotron-parse-2.0` is broken on our key:** HTTP 200 with EMPTY content until max_tokens, even on NVIDIA's own documented example image (usage prompt_tokens=6: the image is dropped). Context is 4,096 tokens in total (a 4,096 max_tokens request is a 400). Logged in data/attempts.jsonl, probe1-3.py.
- **Hosted `nvidia/nemotron-parse` (v1) works:** `<img src="data:image/jpeg;base64,…" />` as the message content, `tools`/`tool_choice` = `markdown_bbox`; the answer is in `tool_calls[0].function.arguments` as `[[{"bbox": {xmin,ymin,xmax,ymax}, "text", "type"}, …]]` (0–1 coordinates). 1.0–2.7 s per page; 11 pages, 0 failures.

## Result against the pre-registered kill line: FAIL (0 of 3 pass both)
| Case | 1 Located (exact, the stored corpus quote in Parse text) | 2 Box right (by eye, overlay PNG) |
|---|---|---|
| TCGA-A2-A0CV | ✗ corpus "(2/18) POSITIVE EXAMINED LYMPH NODES" vs Parse "LYMPH NODES: METASTASIS IN TWO OF EIGHTEEN (2/18) EXAMINED LYMPH NODES" (the scan has an overprinted "POSITIVE" the corpus OCR merged in) | ✓ data/overlay/TCGA-A2-A0CV_closest_p0.png |
| TCGA-A7-A26E | ✗ corpus "16 1 mmnh nodes. one of which contains metastatic. carcinoma, l." vs Parse "16 lymph nodes. one of which contains metastatic carcinoma, [" | ✓ covers the lymph-node section incl. "pN: 1A" (data/overlay/TCGA-A7-A26E_closest_p3.png) |
| TCGA-AN-A0XO | ✓ "N Stage: 1" | ✗ boxes ~1 line below the text (data/overlay/TCGA-AN-A0XO_N_p0.png) |

## Diagnosis (not a pass)
- Check 1 fails because the corpus OCR is WORSE than Parse on the target lines (Parse reads "lymph" where the corpus has "1 mmnh"); Super's quotes copy the corpus errors.
- Check 2's offset on AN-A0XO is probably a resize mismatch (we sent 990×1280; Parse's canvas is 1024×1280). GUESS until tested: pad pages to exactly 1024×1280.
- Side finding: the A2-A0CV scan prints "PATHOLOGIC STAGE: pT2N1aMX" on page 1.

## Proposed re-registered variant (needs its own kill line, written before running)
Parse → Super reads Parse's text → the guard checks Super's quote against Parse's text → the box comes from the Parse block holding the quote; pages padded to 1024×1280.

---
# Variant v2 results (2026-10-22 ~17:40 Prague): PASS, 4 of 6 (kill line ≥4 of 6)
Pipeline: page padded to 1024×1280 → `nvidia/nemotron-parse` blocks → Super (production reader, 4k thinking) reads the joined Parse text → guard → box = the Parse block(s) holding the accepted span. Overlays: data/v2/overlay/. Every call: data/v2/attempts.jsonl.

| Case | Guard located the quote in Parse text | Box on the right line (by eye) | Pass |
|---|---|---|---|
| TCGA-A2-A0CV | ✓ N, count | ✓ "LYMPH NODES: METASTASIS IN TWO OF EIGHTEEN (2/18)…" | ✓ |
| TCGA-A7-A26E | ✓ N, count | ✓ the lymph-node block (slightly low; it contains the quoted lines) | ✓ |
| TCGA-EW-A424 | ✓ N, count | ✓ "Negative for carcinoma in one lymph node examined (0/1)"; ✓ count block p2 | ✓ |
| TCGA-3C-AAAU | ✓ N, count | ✓ "POSITIVE LYMPH NODES: TOTAL: 4 of 13" | ✓ |
| TCGA-AN-A0XO | ✓ N | ✗ Parse split "T Stage: 2 N Stage: 1…" into two blocks placed ~1 line low | ✗ |
| TCGA-AN-A0XS | ✓ N | ✗ a thin box just under the line (y ~8–10 px low) | ✗ |

- Values on Parse text = values stored from the corpus OCR for every N (6/6) and every count stored from both (3/3); 3C-AAAU count 4 is new; AN-A0XO/A0XS abstain on the count (none stated).
- Both failures are the same page type (the sparse one-page TSS form); Parse's y runs ~8–10 px low there. Not fixed or re-tested here; any fix (e.g. snapping a box to the nearest ink line) must be tested on pages not used to design it.
- Not claimed: Parse is "more accurate" than the corpus OCR (one better line on A7-A26E is an example, not a measurement).

*Copied from the project's research notes (2026-10-22). Raw call logs and spike scripts stay in those notes and are not part of this repository.*
