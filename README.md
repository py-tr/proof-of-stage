# Proof of Stage

> The database proves the record is impossible; Nemotron may only say which field is wrong, and only by quoting the scanned report; a person decides.

Proof of Stage audits cancer-stage fields in NCI's public cancer data (TCGA-BRCA, 1,097 cases). A Zetaris Unified Semantic Layer finds records that cannot be true as written (for example, a recorded N category that contradicts the record's own positive-node count). NVIDIA Nemotron reads the original pathology report and may accept a value only with a verbatim quote that code finds in the report. The semantic layer then names which registry field the evidence points to: the node count, the N category, or "a person decides". It never edits a record.

**Open Agent Hackathon 2026 · Track 2: "The Agent That Can Explain Why"** (investigate across multiple data sources, connect findings, produce evidence-backed answers).

*Status: draft README, written as the build progresses (TODO markers are open items).*

## What a judge sees in one case

TCGA-A2-A0CV: the registry says N1a and 4 positive nodes; 4 nodes would be N2a, so both cannot be true. Nemotron reads the report and quotes "(2/18) POSITIVE EXAMINED LYMPH NODES"; the guard confirms the quote and that 2 is the positive count inside it; the semantic layer names **the node-count field**. On the original scan, Nemotron Parse boxes the line "METASTASIS IN TWO OF EIGHTEEN (2/18)". TODO: screenshot / GIF.

## How it works

| Layer | What it does | Where |
|---|---|---|
| Zetaris USL `stage_audit` | 8 tables over 3 live sources: the NCI GDC REST API (cases, recorded stage, node counts), a file store (paraphrased staging rules, report text, Parse blocks) and Postgres (append-only reader output and review log); 8 custom data-quality rules (incl. one basic source-level rule) + the 13 key rules Zetaris generates from the DDL; the app reads only USL tables; lineage from `LOAD USL` | `app/usl/`, `app/usl/sql/`, `docs/zetaris-demo.md` |
| Nemotron Super (VL 120B) | Reads the report; returns T, N and the positive-node count, each with ONE verbatim quote; thinking OFF on the first rung, a 4k budget when the guard needs it | `app/reader/reader.py` |
| The guard (code) | Accepts a value only if its quote is in the report; for a count, the number must be the positive count inside the quote (a fraction's first number) | `app/reader/` |
| Nemotron Parse | Reads the original scanned PDF from the GDC; every text block with its box; stored as the USL table `parse_block` | `app/scans/` |
| `stage_check.fault_field` (USL) | node_count / pathologic_n / review, from the registry, the count rule and the quote-verified reading | `app/usl/sql/055_activate_stage_check.sql` |
| Meterless Markovian engine | The official reference, vendored unmodified (`vendor/meterless-markovian`, conformance 8/8), runs one chain per case: each chunk is a rung of an evidence ladder (R1 thinking off → R2 4k → R3 the scan); our code writes the carryover `{need, consulted, ledger}`, which ends the chain when no field is open. No token savings are claimed for these 1–3-step chains (the engine's own docs: savings start around step 5) | `app/engine/` |
| Meterless Nightshift | The default provider: Super VL pinned, every Ed25519 receipt signature verified, cached answers refused. Budgeted reads go to NVIDIA directly because Nightshift does not forward a thinking budget (reported to Meterless) | `app/providers/nightshift.py`, `app/providers/receipts.py` |
| Case page | One case at a time: the headline, the USL steps, the highlighted quote, the guard checks, rejected answers, decisions written back to Zetaris, "Try to fool it" | `app/web/` |

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate   # Unix: source .venv/bin/activate
pip install -e .
pytest -q                                          # 185 tests, no network
set SAMPLE_MODE=true && python -m app.cli serve    # offline: 4 bundled cases, no model output replayed
```

Live mode needs a Zetaris instance and keys in `.env` (see `.env.example`):

| Command | What it does |
|---|---|
| `python -m app.cli usl setup` / `usl dq` | build the USL (idempotent) / run every data-quality rule |
| `python -m app.cli usl demo --write` | the timed, reproducible query pack → `docs/zetaris-demo.md` |
| `python -m app.cli scans --case TCGA-A2-A0CV` | Nemotron Parse on the original scanned report |
| `python -m app.cli run --case TCGA-A1-A0SN [--store]` | one case through the Markovian evidence ladder; trace in `logs/` |
| `python -m app.cli serve` | the case page |

Nightshift settings we used (Preferences): Adaptive compute, Self-refine, Answer fusion, Reasoning scaffold, Optimistic streaming and Tier-split **off** (so an answer is one model's own text); the cloud Lightning lane moved from Race to Judge (so a pinned Super is never substituted).

## Results (live, 2026-10-22; every number has its file)

| Result | Value | Source |
|---|---|---|
| Records that cannot be true as written (N vs count, 6th/7th edition) | 24 of 1,097 | `usl dq` |
| Fields named by the evidence | 7 (3 count field, 4 N field incl. 1 missing N); 18 "review", of which 15 not read yet | `stage_check` |
| Thinking budget (Super, 42 fields) | off 26/42 · 1k 28 · 4k 30 · unlimited 30 | TODO: declare the reused pre-window arm or re-measure |
| Scan boxes (Parse → Super → guard, pre-registered) | v1 failed 0/3; v2 passed 4/6 | TODO: link the spike report |
| Earlier flagging pipeline, held-out (pre-registered) | 2/4 flags right (50%, 95% CI 15–85), 12× the 4.2% base rate, recall 2/13 | TODO: link |

## Why some calls bypass Nightshift (we tried first)

Nightshift is our default provider: every text call goes through it with Super VL pinned, the receipt's Ed25519 signature verified and cached answers refused. Three kinds of call go to NVIDIA directly, each after we tried Nightshift and measured why it could not do the job (build journal M19–M25; reported to Meterless):

| Call | What happened through Nightshift (Windows edition) | Evidence |
|---|---|---|
| **Thinking OFF** (the cheap first rung) | Nightshift replaces the client's `chat_template_kwargs` with the model's default (thinking on); no request field or header changes it | its `providers.js` (`nvidiaThinkingBody`); 6/6 test calls answered with thinking |
| **A 4k thinking budget** (the deep rung) | no `reasoning_budget` is forwarded, so thinking is unbounded, and cloud calls are cut at 45 s (`provider_deadline`), also when streaming; a real report needs ~40 s at 4k | `CLOUD_FETCH_DEADLINE_MS = 45_000`; 3 runs cut at 45.2 s; the same body via NVIDIA: 4.0 s (off), 40.7 s (4k) |
| **Images** (Nemotron Parse on scans, the scan witness) | this edition has no Vision duty, so no lane can take an image request | the Lanes panel; another team saw `class_no_route` |

What we changed so Nightshift's answers are one model's own text: Adaptive compute, Self-refine, Answer fusion, Reasoning scaffold, Optimistic streaming and Tier-split off; cloud Lightning moved from Race to Judge, after which a pinned Super won 10/10 races. If Meterless adds a per-request thinking switch, the two text rungs move back through Nightshift with a one-line change (`provider=` in `app/engine/rungs.py`).

## Limits (honest)

- Hosted Nemotron Parse 2.0 returned an empty document on our key (even on NVIDIA's own example); we use Parse v1.
- Two of six scan boxes missed on a sparse one-page form; the page then shows no box and a person decides.
- The checks cover N vs the node count in the 6th/7th editions; T, M and stage groups are not audited yet.
- Research data, not for clinical use. TODO: more from the test ledger.

## Data and licences

See `data/README.md`. Code: Apache-2.0 (`LICENSE`); the vendored Meterless Markovian reference is credited in `NOTICE` (Apache-2.0, unmodified).

## How this was built (AI-usage disclosure)

Built solo with AI coding tools: the first commits by Cursor's agent, then Claude Code (Claude Opus 5.5) writing code directly, with independent model reviews (Fable) before each commit; every commit carries its co-author trailer. Design decisions, pre-registered tests and failures: TODO (link the build journal / test ledger).
