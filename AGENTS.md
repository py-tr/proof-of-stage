# AGENTS.md: rules for AI coding agents working in this repository

This file is read by Cursor's agent at the start of every session. Follow it exactly.

## What this project is
A Python service with a small one-page web UI. It reads source documents with NVIDIA Nemotron models, checks each answer against the source text and a rule engine, and stores results in Zetaris. Uncertain results go to a human review queue; the system never guesses.

## Stack
- Python 3.12+, `uv` or `pip` + `pyproject.toml`; FastAPI for the API; plain HTML + vanilla JS (no framework) for the UI.
- Tests: `pytest`. Every module ships with tests. Run `pytest -q` before you say a task is done, and paste the summary line.
- Formatting: `ruff format` + `ruff check`. Type hints on public functions.

## Secrets and config
- **Never** write a key, token or password into code, tests, fixtures, logs or commit messages.
- All config comes from environment variables (loaded from `.env`, which is git-ignored). Provide `.env.example` with placeholder values only.
- Variables: `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `NVIDIA_API_KEY`, `ZETARIS_REST_URL`, `ZETARIS_ORG_ID`, `ZETARIS_API_KEY`, `SAMPLE_MODE`.
- Never print an environment variable's value. Log only whether it is set.

## AI providers (both are required; keep them separate)
1. **Meterless Nightshift (the primary provider)**, an OpenAI-compatible local runtime at `METERLESS_BASE_URL`.
   - Every request sends headers `Authorization: Bearer <token>`, `meterless-app: <app id>`, and a **unique `meterless-scope` per work item** (never the shared default), so the runtime's memory never mixes items. Item ids must be unique per work item; never reuse an item id across runs.
   - **Verify the receipt on every response** (`response.meterless.receipt`): record `winning_route.model`, `winning_route.kind`, `egress.destination`, `egress.sent.context_sources`, `receipt_id`. Nightshift chooses the model itself (an identified app's pinned model id is only recorded, not obeyed), so by default require only that the winning model is a Nemotron model (`nvidia/nemotron*` or a local Nemotron lane); require an exact model only when the caller asks for it. If the model/kind/family differs from what the caller required, or `context_sources` contains anything besides `messages`, **reject the answer** (raise a typed error); never silently accept it.
   - Local-only work runs through the **Jobs API** (`POST /jobs` with `"privacy": "local-only"`, `"auto_synthesize": "off"` (a mode word; a boolean is rejected with 400)); verify `lanes_resolved` contains only local lanes, then read `GET /jobs/{id}/attempts/{seq}`.
   - Use a 180 s timeout; treat 5xx / empty responses as retryable (max 2 retries, with backoff).
2. **NVIDIA direct** (`https://integrate.api.nvidia.com/v1`, `NVIDIA_API_KEY`), the second provider, for calls that need a guaranteed specific model. Same verification idea: check the `model` field of the response against the requested model OR its known served alias (NVIDIA reports `nvidia/nemotron-3.5-super-vl-120b-a12b` as `private/nvidia/nemotron-3.5-super-120b-a12b`); keep an alias table in config and record the served name.
- Model ids live in ONE config module, never scattered string literals.
- Respect rate limits: a shared client-side limiter (default ≤ 20 requests/minute to NVIDIA).

## Data platform: Zetaris
- REST: `POST {ZETARIS_REST_URL}/sql-editor/sqls/run` with `Authorization: Bearer`, `X-Org-ID`, a fresh UUID `X-Request-ID`, and the body `{queryId, sql, source: "SqlEditor", limit}`.
- The data model is a **Zetaris Unified Semantic Layer (USL)**. Results are written append-only (INSERT … WHERE NOT EXISTS) to a Postgres datasource registered in Zetaris. UPDATE / DELETE are not supported there.
- Use straight double quotes in Lightning SQL. Never run `docker compose down -v`.

## Meterless engine
- The long-running batch uses the **Markovian** engine (vendored reference). Keep its conformance tests passing (`npx tsx conformance/runner.ts` in the vendored folder) and our own kill-and-resume test green.

## Honesty rules (product and tests)
- An answer is accepted only with a **verbatim quote** found in the source (punctuation-insensitive match). Otherwise it goes to the review queue with a reason.
- **SAMPLE_MODE=true** runs the real logic on bundled sample DATA with no network calls. It must never replay saved model outputs.
- Evaluation scripts read fixed, committed item lists and seeds; they report the failures too.

## Working style for agents
- Make the smallest change that completes the task; don't refactor unrelated code.
- If something is ambiguous, write the question in your reply instead of guessing.
- After each task, give: files changed, the commands run, and the test summary.
