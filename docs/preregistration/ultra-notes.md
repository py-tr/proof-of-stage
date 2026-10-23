# Pre-registration: Nemotron Ultra writes the case note (written 2026-10-23, before the first Ultra note)

## Question

The case note (`app/notes/note.py`) is a restating task under a strict guard: every number, category and word must come from the facts a sentence cites. Super, thinking on, passed 12 of 20 at run time. Does Nemotron Ultra (`nvidia/nemotron-3-ultra-550b-a55b`), the largest Nemotron, follow the rules more often?

## Design

- **Cases:** the 25 review-queue cases (the ids in `baseline-cases.json`), one note each, run once, in that order.
- **Ultra:** NVIDIA direct (Nightshift has no Ultra lane, so no signed receipt; the served model id is checked on every response). Default thinking (on), `max_tokens` 4000, the same facts, system prompt and guard as Super's note. Logged to `logs/case-notes-ultra.jsonl`; the page keeps reading Super's notes.
- **Comparison:** Super's notes, thinking on, already in `logs/case-notes.jsonl`, re-judged by the same current guard (the newest thinking-on note per case).
- Disclosed: the guard's connecting vocabulary was tuned on Super's notes, which favours Super.

## Measures (fixed now)

- Notes that pass the guard, out of 25; the first failing check of each rejected note; seconds and completion tokens per note.
- Provider failures are listed and counted as not passing. Never re-run.

## Kill line

- Ultra replaces Super as the note writer only if it passes at least 12 of 25 **and** more than Super under the same guard. Otherwise the result is reported and the note stays with Super. Nothing is re-tuned after the run.

## Prediction (before the run)

Ultra passes more notes than Super (a larger model follows a format better), at more seconds per note. A guess.

## Correction (2026-10-23, written during the run, design unchanged)

"Nightshift has no Ultra lane" above is wrong. Nightshift 1.2.3 lists `nvidia/nemotron-3-ultra-550b-a55b` and answers with a verified receipt signed by the pinned key (probe 2026-10-23: 14.1 s against 1.0 s direct for a one-line answer). Through Nightshift, Ultra's reasoning arrives inside the answer text, ending in a `</think>` with no opening tag; `strip_think` now removes it. The run stays on NVIDIA direct as registered. A Nightshift run of Ultra notes would be a separate, new measurement.
