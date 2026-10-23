# Nemotron Ultra writes the case note: results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/ultra-notes.md` (written before the first Ultra note; its dated correction says Nightshift does list Ultra, and the run stayed on NVIDIA direct as registered). Logs: `logs/case-notes-ultra.jsonl`, `logs/notes-batch-2026-10-23-ultra.txt`.

## Result

| Measure | Result |
|---|---|
| Notes answered | 25 of 25 (no provider failure); every response served as `nvidia/nemotron-3-ultra-550b-a55b` |
| **Notes that pass the guard** | **8 of 25** |
| Super, thinking on, the same 25 cases, the same current guard (newest thinking-on note per case, `logs/case-notes.jsonl`) | 21 of 25 (1 case has no thinking-on note) |
| Median seconds / completion tokens per Ultra note | 56 s / 1,784 |
| **Kill line (Ultra replaces Super only if at least 12 of 25 and more than Super)** | **hit: the note stays with Super** |

Why Ultra's 17 notes failed (first failing check): 12 used a word that none of their cited facts has ("determines", "documents", "translates", "triggers", …), 3 wrote fact ids into the text, 1 was not JSON, 1 sentence had no citation. Ultra writes fuller explanatory prose; the guard allows only the facts' words plus a fixed connecting vocabulary.

Prediction (before the run): "Ultra passes more notes than Super, at more seconds per note." **Did not hold** on passes; it did take longer (Super thinking on: about 20–60 s).

## What it means, and what it does not

- The guard's connecting vocabulary was tuned on Super's notes (disclosed before the run), so this measures "who follows this guard", not "who writes the better note". Several rejected Ultra sentences are accurate restatements that use a verb the vocabulary lacks.
- Nothing is re-tuned after the run: the vocabulary stays as frozen, and the case note stays with Super through Nightshift.
