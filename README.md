# Proof of Stage

> The database proves the record is impossible; Nemotron may only quote the report; the semantic layer names which field the quote contradicts; a person decides.

Proof of Stage audits cancer-stage fields in NCI's public cancer data (TCGA-BRCA, 1,097 cases). A Zetaris Unified Semantic Layer finds records that cannot be true as written (for example, a recorded N category that contradicts the record's own positive-node count). NVIDIA Nemotron reads the original pathology report and may accept a value only with a verbatim quote that code finds in the report. The semantic layer then names which registry field the evidence points to: the node count, the N category, or "a person decides". It never edits a record.

**Open Agent Hackathon 2026 · Track 2: "The Agent That Can Explain Why"** (investigate across multiple data sources, connect findings, produce evidence-backed answers).

## What a judge sees in one case

TCGA-A2-A0CV: the registry says N1a and 4 positive nodes; 4 nodes would be N2a, so both cannot be true. Nemotron reads the report and quotes "(2/18) POSITIVE EXAMINED LYMPH NODES"; the guard confirms the quote and that 2 is the positive count inside it; the semantic layer names **the node-count field**. On the original scan, Nemotron Parse boxes the line "METASTASIS IN TWO OF EIGHTEEN (2/18)". This is the live result; in offline sample mode the same case shows the contradiction and lets you play the reader (no model output is bundled or replayed).

## How it works

| Layer | What it does | Where |
|---|---|---|
| Zetaris USL `stage_audit` | 8 tables over 3 live sources: the NCI GDC REST API (cases, recorded stage, node counts), a file store (paraphrased staging rules, report text, Parse blocks) and Postgres (append-only reader output and review log); 8 custom data-quality rules (one basic source-level rule; `fault_named` / `fault_unresolved` are review queues expressed as rules) + the 13 key rules Zetaris generates from the DDL (11 addressable by name; the two composite primary keys run via their first column, and `usl demo` checks their full uniqueness directly); the case page reads only USL tables; its lineage panel comes from `LOAD USL` | `app/usl/`, `app/usl/sql/`, `docs/zetaris-demo.md` |
| Nemotron Super | We request `nvidia/nemotron-3.5-super-vl-120b-a12b`; NVIDIA's API reports it served as `private/nvidia/nemotron-3.5-super-120b-a12b` (its alias, `app/config.py`), and Nightshift's signed receipts name the VL id. Reads the report; returns T, N and the positive-node count, each with ONE verbatim quote; thinking OFF on the first rung, a 4k budget when the cheap read cannot settle a field | `app/reader/reader.py` |
| The guard (code) | Accepts a value only if its quote is in the report **and shows the value**. For N and T: a matching stage token or label ("pN1a", "N Stage: 1a"); for N, a node count that passes the whole count guard below and implies the N (2 positive → N1); for T, a tumour size in its range after a tumour cue (not a node, margin or specimen size); or the words of a category a number cannot show, not negated and about the right element (micrometastasis; "regional lymph nodes … cannot be assessed", not pM; skin or chest-wall invasion, not just "skin"; in situ without invasion). For a count: the first number of a positive fraction ("2/18"; not a score like "8/9", not "eight of eight … free of carcinoma"), or else the number nearest a positive cue ("positive", "metastatic"), never one with a unit or a grade around it in the report; not below any node fraction the report states; and equal to the total when the report states one with a label ("Number of positive lymph nodes: 4"). Each rule closes a hole a red-team or review found (`docs/evidence/guard-floor.md`). Known limits: a per-specimen count or N when the report states the total neither as a fraction nor with a label; a count above every stated fraction | `app/reader/` |
| Nemotron Parse | Reads the original scanned PDF from the GDC; every text block with its box; stored as the USL table `parse_block` | `app/scans/` |
| `stage_check.fault_field` (USL) | node_count / pathologic_n / review, from the registry, the count rule and the quote-verified reading | `app/usl/sql/055_activate_stage_check.sql` |
| Meterless Markovian engine | The official reference, vendored unmodified (`vendor/meterless-markovian`, conformance 8/8); our Node sidecar wraps one method at runtime only to record which carryover level the engine chose. **Two chains.** (1) The evidence ladder, one chain per case: each chunk is a rung (R1 thinking off → R2 4k → R3 the scan); our code writes the carryover `{need, consulted, ledger}`, which picks the next rung and ends the chain when no field is open; the model reads the document beside the engine and never sees the carryover (so no reading can anchor the next), which makes the engine's savings 0 by construction, and we claim none. (2) **The red-team chain**, where Super is the generator: each step it sees the engine's `[CARRYOVER STATE]` (a code-written ledger of its earlier attacks and the guard's verdicts) and proposes a new attack; pre-registered, 3 cases × 20 steps (`docs/evidence/adversary-chain-results.md`) | `app/engine/` |
| Meterless Nightshift | **The provider for every text call.** The evidence ladder's rungs (thinking off, a 4k thinking budget) and the case note go through Nightshift (since 1.2.3 it forwards the thinking switch and the budget; `docs/evidence/nightshift-limits.md` §6), with Super VL required in the signed receipt (a model id alone did not always pin a lane), the receipt's Ed25519 signature verified against a pinned key (`NS_RECEIPT_PUBKEY`; Nightshift publishes no key, so we pinned the key of the first verified receipt and every later one must match), cached answers refused, and `python -m app.cli doctor` printing the signature state and the signer's key fingerprint. NVIDIA direct stays as a documented fallback (`run --provider nvidia`); only Nemotron Parse on the scan images goes direct, because Nightshift offers no lane for it | `app/engine/rungs.py`, `app/notes/note.py`, `app/providers/nightshift.py`, `app/providers/receipts.py` |
| Case page | One case at a time: the headline, the USL steps, the highlighted quote, the guard checks, rejected answers, the case note with its Nightshift receipt, decisions written back to Zetaris, "Try to fool it" | `app/web/` |

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate   # Unix: source .venv/bin/activate
pip install -e .
pytest -q                                          # 253 tests, no network
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
| `python -m app.cli adversary` | the pre-registered red-team chain (refuses to run if the frozen cases, prompt or guard changed) |
| `python -m app.cli doctor` | checks every dependency; a signed Super VL call through Nightshift |
| `python -m app.cli serve` | the case page |

Nightshift setup we used (1.2.3, Windows): Adaptive compute, Self-refine, Answer fusion, Reasoning scaffold, Optimistic streaming and Tier-split **off** (so an answer is one model's own text); the cloud Lightning lane moved from Race to Judge. **Nightshift 1.2.3 switches Super VL off by default** (Meterless measured it unstable: 31 of 94 hosted calls failed); we opted back in with its documented flag `NVIDIA_SUPER_VL = "true"` (a key in the runtime's `state/engine-kv.json`, set while Nightshift is closed), so every read stays on the model all our measurements used. Without it every pinned call is refused with Nightshift's own message naming the flag.

## Results (live, 2026-10-22/23; every number has its file)

| Result | Value | Source |
|---|---|---|
| Records that cannot be true as written (N vs count, 6th/7th edition) | 24 of 1,097 (+1 missing N the count could fill = the 25-case review queue; a review found our rule had counted a 26th, a record with no edition, through SQL's NULL logic; fixed) | `logs/usl-dq-2026-10-23.txt` |
| Fields named by the evidence (every queue case through the ladder with the current guard, 2026-10-23) | **21 of 25** queue cases: 8 node-count field, 13 N field (incl. 1 missing N); 4 for a person (micrometastasis or isolated tumour cells with no count, no axillary nodes, or a report that contradicts both registry fields). Values are append-only (first write wins): one named case, TCGA-E2-A1B4 (N1mi), rests on a reading from 2026-10-22 that the current ladder did not reproduce (its new read was rejected and flagged); the page re-checks every stored value with the current guard | `stage_check` (`docs/zetaris-demo.md` step 4), `logs/batch-ladder-2026-10-23b.txt` |
| The thinking-off rung on the 25 queue cases (latest run per case) | closed one field in 9 cases and both fields in none: a field it may close must agree with the registry, and on a contradiction case a reading cannot agree with both registry fields, so every case went on to the 4k rung; the scan rung ran in 2 | `logs/markovian-chunks.jsonl` |
| Case notes through Nightshift, re-run with the pinned key and the current guard (25 queue cases, 2026-10-23) | 20 answers, **all 20 signed by the pinned key** (fingerprint `7a6d14e27e1a`), verified, Super VL, none cached; 5 calls failed: 3 Nightshift 502s, 1 timeout, and 1 **refused by our receipt check because a local Lightning lane won the race** (the model check working). The note guard accepted 12 at run time; 8 rejections were for harmless connecting words outside its fixed vocabulary, so we added 15 such words (do, does, where, using, applies, drives, identifies, pathology, whether, nodal, …; `app/notes/note.py`) after seeing them: 19 of the same 20 now pass, 1 is still rejected ("staging"). This tuning was done on these notes, so 19 of 20 is not an independent measurement. Latency median 35.9 s, range 13.8–388 s. The first batch (before pinning): 24 answers, 19 pass the current guard | `logs/notes-batch-2026-10-23b.txt`, `logs/case-notes.jsonl`, `logs/notes-batch-2026-10-23.txt` |
| Data-quality pack | 8 custom rules + 13 Zetaris key rules (`LIST DQ USL`), run by `usl dq` | `logs/usl-dq-2026-10-23.txt`, `docs/zetaris-demo.md` |
| Red-team chain (pre-registered, Super as the Markovian generator, 3 cases × 20 steps) | 1 bug in 60 attacks, plus 3 kinds of documented-limit accept; all 8 wrong accepts are rejected by the guard that followed (fixes designed after the run, so not a new measurement). Tokens: 62,806 measured prompt tokens; 7,243 estimated saved against a transcript that resends every attack | `docs/evidence/adversary-chain-results.md` |
| Thinking budget (Super, 42 fields of a spike set; a measurement, not the ladder) | off 26/42 · 1k 28 · 4k 30 · unlimited 30; the "unlimited" arm was reused from a run on 2026-10-21, before the build window | `docs/evidence/thinking-budget.md` |
| Scan boxes (Parse → Super → guard, pre-registered) | v1: 0 of 3 passed (the kill line failed); v2: 4 of 6 passed | `docs/evidence/scan-boxes.md` |
| Earlier flagging pipeline, held-out (pre-registered) | 2/4 flags right (50%, 95% CI 15–85), 12× the 4.2% base rate, recall 2/13 | `docs/evidence/heldout-flagging.md` |

## Nightshift: what 1.2.1 could not do, and what 1.2.3 fixed

We integrated Nightshift first and measured where it could not do the job (`docs/evidence/nightshift-limits.md`): on 1.2.1 it replaced the client's thinking switch with the model's default (thinking on), forwarded no `reasoning_budget`, and cut cloud calls at 45 s, so the ladder's two text rungs and the red-team generator had to go to NVIDIA directly. We reported it to Meterless with the code lines (`providers.js`, `nvidiaThinkingBody`); 1.2.3's code now says "a caller that names a kwarg gets exactly that kwarg (2026-10-22: it used to be replaced by the row default)".

Measured on 1.2.3, Super VL pinned, the reader prompt on full reports (`logs/nightshift-123-super-vl-2026-10-23.txt`): thinking off 1.9–8.7 s; a 4k budget 74–92 s and not cut (the 45 s constant is still in the code); every answer Super VL, signed by the pinned key, none cached. Nightshift's usage reports no reasoning-token count, so through Nightshift the budget shows only as completion tokens of about the budget plus the answer (4,174 and 4,215 at 4,000); the to-the-token measurement is the one made directly (`docs/evidence/thinking-budget.md`). Budgeted reads take longer through Nightshift than directly (40.7 s directly for the same report).

Still direct: Nemotron Parse on the scan images (1.2.3 offers a `vision` class through Super VL, but no lane for Parse); and the finished red-team run v2, pre-registered on NVIDIA direct because 1.2.1 could not carry its budget (`docs/evidence/adversary-chain-results.md`).

## Reflection on the Zetaris USL

**Built** (`app/usl/sql/`, run in order by `usl setup`): identified 3 kinds of source (the NCI GDC REST API; file-store CSVs of paraphrased rules, report text and Parse blocks; our own Postgres results), onboarded each (`020–022` REST, `010–016` file store, `002–005` Postgres), queried each, compiled one USL `stage_audit` (8 tables, primary and foreign keys, 87 table and column descriptions in `040_descriptions.sql`), queried it (the case page reads only USL tables; `usl demo` is a timed query pack) and added data-quality rules (one basic source-level rule, `nodes_within_tested`, plus 7 custom rules and the 13 key rules Zetaris generates from the DDL).

**How it saved time.** What we measured: the whole cross-source audit, 21 rule results over 1,097 cases from three source types, runs with one command in 44.8 s (`usl dq`, `logs/usl-dq-2026-10-23.txt`), and the reproducible demo pack in 21 s (`docs/zetaris-demo.md`). We did not time a manual or hand-coded alternative, so we claim no "hours saved" number. What we did not have to build: an ETL step (the verdict `stage_check.fault_field` is one SQL CASE over the GDC API, the CSVs and Postgres, joined in place); a reload step (a value the reader appends to Postgres is in the next USL query); a lineage view (the page's lineage panel comes from `LOAD USL`); our own key checks (the 13 key rules come from the DDL).

**How it can help in our work.** The layer is a pattern, not a cancer tool: a record table, a source-document table, a rule table, the model's verified readings and a verdict, with every write append-only. Only the rule table is about staging. The same shape fits other "does the record match its source document" audits (trial source-data checks, claims against clinical notes, invoices against an ERP); we have not tested those.

**How to improve it** (each one observed while building; build journal ids in brackets):
1. A schema change needs REMOVE USL + COMPILE, so a failed compile takes the live layer down; a validate-only compile or an ALTER USL would avoid that (M17).
2. `double` is rejected in USL DDL with "Invalid DDL statement" (`decimal` works); an error naming the type would save a search (M17).
3. A file-store table keeps its first schema when the CSV header changes; we had to drop and re-register it (M17).
4. `'O''Brien'` returns `OBrien` (adjacent literals are concatenated) instead of `O'Brien`; backslash escaping works (M14).
5. The Postgres datasource takes INSERT but not UPDATE, DELETE or CREATE VIEW; fine for an append-only log, worth documenting.
6. Each REST call takes about 3 s; a read-only batch endpoint (several statements per call) would make pages faster.
7. `RUN DQ` cannot address a composite-key rule by the name `LIST DQ USL` prints (`case_id,page_no,block_index` gives "mismatched input ','"); running it through its first column works.
8. What helped: the NOT NULL mismatch error suggested the exact COALESCE fix (M17).

## Meterless Runtime as a provider: where we stand (provider contract v4)

Graded against the levels in Meterless' own "Grade my provider integration" prompt (meterless.ai/engines.html). Run `python -m app.cli doctor` to see each check live.

| Level | What the contract asks | Us | Where |
|---|---|---|---|
| L0 Text | `meterless/*` routing modes on `/v1/chat/completions`, the real bearer token, 401/403 shown as unauthorized | partly: health reads `/v1/models` (online / unauthorized / offline); `doctor` sends a plain request on `meterless/text`, which returned a string on 1.2.1 (routed to a local Lightning lane); on our 1.2.3 setup it finds no lane, because an opted-in Super VL stays out of automatic routing and no other lane is on Race. The product's calls name the explicit `nvidia/nemotron-3.5-super-vl-120b-a12b` and require it in the signed receipt (on 1.2.1 one explicit request for another model was won by Super VL and refused by that check) | `app/providers/nightshift.py`, `app/cli.py` |
| L1 Discovery | `/v1/models` and `/v1/meterless/classes` (both shapes), unknown `meterless/*` ids kept | yes: `nightshift.discover()`; doctor prints the text class state and confirms Super VL is a cloud lane | `app/providers/nightshift.py` |
| Errors | the server's message first, then its `fix[]`; a 429 retries after 2, 4 and 8 s | yes | `app/providers/nightshift.py` |
| Local-only | local-only work never reaches a cloud provider | yes: Jobs API with `privacy: local-only`, every resolved lane checked | `nightshift.local_job` |
| L2+ | attachments, media, transcription, 3D, Quick Connect | not used (a text-only audit) | |

One deliberate difference: the contract sends `meterless-scope: user` on chat; we send a unique `meterless-scope` per work item, so the runtime's memory never mixes one case's report into another's answer (we saw the runtime inject memories into requests early on). Every receipt is checked: the winning model, `egress`, `context_sources` (only `messages`), the cache status and the Ed25519 signature against the pinned key.

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

Built solo with AI coding tools: the first commits by Cursor's agent, then Claude Code (Claude Opus 5.5) writing code directly, with independent model reviews (Fable) before each commit; every commit carries its co-author trailer. Pre-registered tests and their failures, including a void run, are in `docs/preregistration/` and `docs/evidence/`; the guard's review rounds (two red-team passes, two judge-panel passes) are in `docs/evidence/guard-floor.md`.
