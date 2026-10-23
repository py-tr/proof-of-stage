# Proof of Stage

> The database proves the record is impossible; Nemotron may only quote the report; the semantic layer names which field the quote contradicts; a person decides.

Proof of Stage audits cancer-stage fields in NCI's public cancer data (TCGA-BRCA, 1,097 cases). A Zetaris Unified Semantic Layer finds records that cannot be true as written (for example, a recorded N category that contradicts the record's own positive-node count). NVIDIA Nemotron reads the original pathology report and may accept a value only with a verbatim quote that code finds in the report. The semantic layer then names which registry field the evidence points to: the node count, the N category, or "a person decides". It never edits a record.

**Open Agent Hackathon 2026 · Track 2: "The Agent That Can Explain Why"** (investigate across multiple data sources, connect findings, produce evidence-backed answers).

*Status: draft README, written as the build progresses (TODO markers are open items).*

## What a judge sees in one case

TCGA-A2-A0CV: the registry says N1a and 4 positive nodes; 4 nodes would be N2a, so both cannot be true. Nemotron reads the report and quotes "(2/18) POSITIVE EXAMINED LYMPH NODES"; the guard confirms the quote and that 2 is the positive count inside it; the semantic layer names **the node-count field**. On the original scan, Nemotron Parse boxes the line "METASTASIS IN TWO OF EIGHTEEN (2/18)". This is the live result; in offline sample mode the same case shows the contradiction and lets you play the reader (no model output is bundled or replayed). TODO: screenshot / GIF.

## How it works

| Layer | What it does | Where |
|---|---|---|
| Zetaris USL `stage_audit` | 8 tables over 3 live sources: the NCI GDC REST API (cases, recorded stage, node counts), a file store (paraphrased staging rules, report text, Parse blocks) and Postgres (append-only reader output and review log); 8 custom data-quality rules (one basic source-level rule; `fault_named` / `fault_unresolved` are review queues expressed as rules) + the 13 key rules Zetaris generates from the DDL (10 addressable by name; the two composite primary keys run via their first column); the case page reads only USL tables; its lineage panel comes from `LOAD USL` | `app/usl/`, `app/usl/sql/`, `docs/zetaris-demo.md` |
| Nemotron Super (VL 120B) | Reads the report; returns T, N and the positive-node count, each with ONE verbatim quote; thinking OFF on the first rung, a 4k budget when the cheap read cannot settle a field | `app/reader/reader.py` |
| The guard (code) | Accepts a value only if its quote is in the report; for a count: the first number of a positive fraction in the quote ("2/18"; not a score like "8/9", not "eight of eight … free of carcinoma"), or else the number written nearest a positive cue ("positive", "metastatic"), never one with a unit after it (mm, %, months) or "examined"/"size" before it; and it may not be below any node fraction the report states, so one specimen's count cannot pass as the total. Each rule closes a hole a red-team found (`docs/evidence/guard-floor.md`). Known limits: a per-specimen count when no fraction states the total; a count above every stated fraction | `app/reader/` |
| Nemotron Parse | Reads the original scanned PDF from the GDC; every text block with its box; stored as the USL table `parse_block` | `app/scans/` |
| `stage_check.fault_field` (USL) | node_count / pathologic_n / review, from the registry, the count rule and the quote-verified reading | `app/usl/sql/055_activate_stage_check.sql` |
| Meterless Markovian engine | The official reference, vendored unmodified (`vendor/meterless-markovian`, conformance 8/8), runs one chain per case: each chunk is a rung of an evidence ladder (R1 thinking off → R2 4k → R3 the scan); our code writes the carryover `{need, consulted, ledger}`, which picks the next rung and ends the chain when no field is open. The engine runs the control flow; the model reads the document beside it and never sees the carryover (so no reading can anchor the next). The engine's own savings estimate is therefore 0 by construction (every run in `logs/markovian-runs.jsonl`); we claim no savings for this chain. Planned: a second chain where the model is the generator (the red-team lane) | `app/engine/` |
| Meterless Nightshift | Integrated as a provider: Super VL pinned, each receipt's Ed25519 signature verified, cached answers refused (`python -m app.cli doctor` shows a signed call). **The case note runs through Nightshift**: Super VL restates the case's numbered USL facts in 1–4 sentences, each citing the facts it uses; code rejects any sentence whose numbers or stage categories are not in the facts it cites, and the page shows the signed receipt under the note. **The ladder's reads go to NVIDIA directly**, because Nightshift cannot take a thinking switch, a budget or an image (next section, reported to Meterless); every logged rung shows `receipt_id: null`. Planned: the red-team lane through Nightshift | `app/notes/note.py`, `app/providers/nightshift.py`, `app/providers/receipts.py` |
| Case page | One case at a time: the headline, the USL steps, the highlighted quote, the guard checks, rejected answers, the case note with its Nightshift receipt, decisions written back to Zetaris, "Try to fool it" | `app/web/` |

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate   # Unix: source .venv/bin/activate
pip install -e .
pytest -q                                          # 216 tests, no network
set SAMPLE_MODE=true && python -m app.cli serve    # offline: 4 bundled cases, no model output replayed
```

Live mode needs a Zetaris instance and keys in `.env` (see `.env.example`):

| Command | What it does |
|---|---|
| `python -m app.cli usl setup` / `usl dq` | build the USL (idempotent) / run every data-quality rule |
| `python -m app.cli usl demo --write` | the timed, reproducible query pack → `docs/zetaris-demo.md` |
| `python -m app.cli scans --case TCGA-A2-A0CV` | Nemotron Parse on the original scanned report |
| `python -m app.cli run --case TCGA-A1-A0SN [--store]` | one case through the Markovian evidence ladder; trace in `logs/` |
| `python -m app.cli note --case TCGA-A2-A0CV` | a cited case note by Super through Nightshift; log in `logs/case-notes.jsonl` |
| `python -m app.cli serve` | the case page |

Nightshift settings we used (Preferences): Adaptive compute, Self-refine, Answer fusion, Reasoning scaffold, Optimistic streaming and Tier-split **off** (so an answer is one model's own text); the cloud Lightning lane moved from Race to Judge (so a pinned Super is never substituted).

## Results (live, 2026-10-22/23; every number has its file)

| Result | Value | Source |
|---|---|---|
| Records that cannot be true as written (N vs count, 6th/7th edition) | 24 of 1,097 (+1 missing N the count could fill = the 25-case review queue) | `docs/zetaris-demo.md` (`usl dq`) |
| Fields named by the evidence (after the ladder batch, 2026-10-23) | **20 of 25** queue cases: 8 node-count field, 12 N field (incl. 1 missing N); 5 for a person (micrometastasis, no count stated) | `stage_check`, `logs/batch-2026-10-23.txt` |
| The thinking-off rung on contradiction cases | cleared 0 fields in 15 cases: a self-consistent reading cannot agree with both contradicting fields, so every case escalated to the 4k rung (the rung catches a wrong fast read: TCGA-A1-A0SN) | `logs/markovian-chunks.jsonl` |
| Case notes through Nightshift (25 queue cases, 2026-10-23) | 24 answers, **24 of 24 receipt signatures verified** (Super VL every time, none cached), 1 call failed with a Nightshift 502 after retries; the guard accepted 19 at run time and rejected 5. One of those 5 was our tokenizer's fault ("POSITIVE: 1." was not read as 1; fixed; that answer now passes, so 20 of 25 under the current guard); the other 4 are correct rejections (2 wrote fact ids into the text, 1 sentence cited nothing, 1 answer was not JSON). Latency median 22.8 s (Nightshift keeps thinking on), range 6.2–124 s | `logs/notes-batch-2026-10-23.txt`, `logs/case-notes.jsonl` |
| Data-quality pack | 8 custom rules + 13 Zetaris key rules, all keys valid; reproducible query pack in 21 s | `docs/zetaris-demo.md` |
| Thinking budget (Super, 42 fields of a spike set; a measurement, not the ladder) | off 26/42 · 1k 28 · 4k 30 · unlimited 30; the "unlimited" arm was reused from a run on 2026-10-21, before the build window | research spike (knowledge base), TODO: copy into `docs/evidence/` |
| Scan boxes (Parse → Super → guard, pre-registered) | v1: 0 of 3 passed (the kill line failed); v2: 4 of 6 passed | research spike (knowledge base), TODO: copy into `docs/evidence/` |
| Earlier flagging pipeline, held-out (pre-registered) | 2/4 flags right (50%, 95% CI 15–85), 12× the 4.2% base rate, recall 2/13 | TODO: link |

## Why some calls bypass Nightshift (we tried first)

Nightshift is integrated (Super VL pinned, the receipt's Ed25519 signature verified, cached answers refused), but the three kinds of call the ladder makes go to NVIDIA directly, each after we tried Nightshift and measured why it could not do the job (build journal M19–M25; reported to Meterless; the evidence files are being copied into `docs/evidence/`):

| Call | What happened through Nightshift (Windows edition) | Evidence |
|---|---|---|
| **Thinking OFF** (the cheap first rung) | Nightshift replaces the client's `chat_template_kwargs` with the model's default (thinking on); no request field or header changes it | its `providers.js` (`nvidiaThinkingBody`); with thinking-off requested, the same report took 4.0 s via NVIDIA and still ran past 45 s via Nightshift |
| **A 4k thinking budget** (the deep rung) | no `reasoning_budget` is forwarded, so thinking is unbounded, and cloud calls are cut at 45 s (`provider_deadline`), also when streaming; a real report needs ~40 s at 4k | `CLOUD_FETCH_DEADLINE_MS = 45_000`; 3 runs cut at 45.2 s; the same body via NVIDIA: 4.0 s (off), 40.7 s (4k) |
| **Images** (Nemotron Parse on scans, the scan witness) | this edition has no Vision duty, so no lane can take an image request | the Lanes panel; another team saw `class_no_route` |

What we changed so Nightshift's answers are one model's own text: Adaptive compute, Self-refine, Answer fusion, Reasoning scaffold, Optimistic streaming and Tier-split off; cloud Lightning moved from Race to Judge, after which a pinned Super won 10/10 races. If Meterless adds a per-request thinking switch, the two text rungs move back through Nightshift with a one-line change (`provider=` in `app/engine/rungs.py`).

## Limits (honest)

- Hosted Nemotron Parse 2.0 returned an empty document on our key (even on NVIDIA's own example); we use Parse v1.
- Two of six scan boxes missed on a sparse one-page form; the page then shows no box and a person decides.
- The checks cover N vs the node count in the 6th/7th editions; T, M and stage groups are not audited yet.
- The ladder reads the report text from the local corpus copy and the scan from the local Parse cache (the same text the USL serves); moving those reads onto the USL tables is planned.
- Append-only storage: the first value written for (case, method, field) stays, even if a later read is better; later reads are logged as `kept-earlier`.
- "Impossible" means impossible under our paraphrased count rules (data/README.md), not the AJCC manual itself; edition windows overlap (6th 2002–2010, 7th 2009–2018).
- The GDC REST table is cached (refreshed by `usl setup`); report text and scans are not committed (licences and size).
- Research data, not for clinical use.

## Data and licences

See `data/README.md`. Code: Apache-2.0 (`LICENSE`); the vendored Meterless Markovian reference is credited in `NOTICE` (Apache-2.0, unmodified).

## How this was built (AI-usage disclosure)

Built solo with AI coding tools: the first commits by Cursor's agent, then Claude Code (Claude Opus 5.5) writing code directly, with independent model reviews (Fable) before each commit; every commit carries its co-author trailer. Design decisions, pre-registered tests and failures: TODO (link the build journal / test ledger).
