# A second, independent blind labeller (pre-registered, scored 2026-10-26)

Pre-registration: `docs/preregistration/second-labeller.md` (written before any second label existed) and `second-labeller-scorer.md` (the scorer, committed before any second label). Freeze note: `docs/preregistration/second-labeller-freeze-note.md`; labels sha16 `5ba1405a9ca4b9d4`, committed before scoring. Scores: `logs/second-labeller-scores.json` (`python scripts/second_labeller.py score`, offline, the frozen scoring rules, the per-case answers recorded when the first labels were scored; no model call).

## Result

| Measure | Result |
|---|---|
| The two labellers agree (25 queue cases, three outcomes) | **22 of 25, Cohen's kappa 0.82** |
| The product against the second labeller | **19 of 25** |
| Super alone at a 4k budget, no quote check | **19 of 25** |
| Super alone, thinking off | 12 of 25 |
| The rule that never reads the report (always blames N) | 9 of 25 |
| On the 22 cases where both labellers agree: product / Super 4k / Super off / rule | 17 / 17 / 9 / 7 |
| Deep-read bench against the second labeller (correct / wrong accepts) | Super 33 / 2, Ultra 33 / 3, Lightning 25 / 2: Super keeps the seat |

## What it means, and what it does not

- The labels are not one person's any more: an independent lay labeller agrees with the builder on 22 of 25 (kappa 0.82).
- The product does not fall behind Super alone (the pre-registered headline condition): the two are level, 19 and 19, as they were on the builder's labels (18 and 17). The thinking budget still moves the answer (Super off 12, 4k 19).
- Both labellers are lay readers, not pathologists. The second labeller worked on the builder's PC in a private window with only the blind sheet on screen; the builder explained the buttons only. The export's `labeller` field is a string hard-coded in the sheet ("the builder ..."), disclosed in the freeze note.
- Timing (from the timestamps the sheet saves with each label): the 25 labels were saved over 13.7 minutes, a median of 26 seconds between labels (the builder: 52.8 minutes, median 119 s). The second labeller read much faster than the builder; they still agree on 22 of 25. The case-page part of the addendum (5 cases, three questions) was not run.
