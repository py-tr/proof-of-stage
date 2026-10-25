# Pre-registration: a second, independent blind labeller (written 2026-10-25, before any second label exists)

## Why (disclosed)

Every accuracy number against the blind labels rests on one lay labeller, who is also the builder: the product 18 of 25 and Super alone 17 (`docs/evidence/baseline-m0-results.md`), and the deep-read bench (`reader-bench-results.md`). Every judge in councils 13 and 14 named this as the main weakness. A second person who did not build the system labels the same 25 review-queue records blind.

## Design

- **Sheet:** the same blind sheet as the first labeller (`scripts/make_label_sheet.py`). It shows the registry's recorded N and positive-node count, the paraphrased count rule and the full pathology report, and never the system's verdict, readings or quotes. The labeller opens it on their own device, or in a private window, so no earlier labels preload.
- **Labeller:** one person who has not seen the system's output, the case page or the first labels. Recruited by the builder, named only as "a second lay labeller". Labels are made without the builder's help on any case. The builder may explain the sheet's buttons only.
- **Freeze:** the exported `labels.json` is hashed (sha16) and committed as `docs/preregistration/second-labeller-labels.json`, before any scoring code reads it.
- **Scored, by the frozen scoring rules unchanged** (`app/engine/labels.py`):
  - agreement between the two labellers (raw, and Cohen's kappa over the three outcomes);
  - the product, Super alone (thinking on and off) and the rule alone against the second labeller;
  - and against the cases where both labellers agree.
- **Reported whatever comes out:** if the product falls behind Super alone against the second labeller, that is the headline row.

## Deadline

Labels must be frozen by Mon 2026-10-26 16:00 Prague, or this test is reported as not run.
