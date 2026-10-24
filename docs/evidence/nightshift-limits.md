# Nightshift and Nemotron thinking: what we measured (2026-10-23)

Meterless Nightshift, Windows edition, NVIDIA cloud lanes, model `nvidia/nemotron-3.5-super-vl-120b-a12b`. Router extras off (Adaptive compute, Self-refine, Answer fusion, Reasoning scaffold, Optimistic streaming, Tier-split); cloud Super VL in Race + Verify; cloud Lightning moved to Judge; the local lane stopped. Reported to Meterless.

## 1. The same reader request, direct and through Nightshift (one real ~9.8k-character report, TCGA-A1-A0SN)

| Request | Result |
|---|---|
| NVIDIA direct, `chat_template_kwargs: {enable_thinking: false}` | 200 in **4.0 s**, 143 completion tokens, 0 reasoning |
| NVIDIA direct, `{enable_thinking: true, reasoning_budget: 4000}` | 200 in **40.7 s**, 3,698 completion tokens (3,534 reasoning) |
| Nightshift, thinking off requested, max_tokens 1500 | 502 after ~27 s (routed to cloud Lightning, `empty_response`) |
| Nightshift + header `meterless-tier-split: off` (2 tries) | 502, Super VL `empty_response` (16.6 s, 39.9 s) |
| Nightshift + tier-split off, max_tokens 8000 | 502 `provider_deadline` at 45.2 s |
| Nightshift + tier-split off, `stream: true` | 200 headers, no content, cut at 45.2 s |
| Nightshift, a short prompt ("Reply with one word: ready") | 200 in 1–3 s, Super VL, 32–50 completion tokens |

## 2. Why (read in the installed Nightshift engine's JavaScript)

1. `providers.js` (`nvidiaThinkingBody`, ~line 1233) builds the NVIDIA body's `chat_template_kwargs` as `{enable_thinking: want}`, where `want` comes from `req.reasoning` or else the model row's default; the client's own `chat_template_kwargs` is not forwarded.
2. Nothing sets `req.reasoning` from a client chat request (`proxy.js` forwards `reasoning_effort` / `effort` for other providers and a fixed passthrough list).
3. The Nemotron 3.5 rows in `models.js` default to `reasoning: true`.
4. No `reasoning_budget` is sent, so thinking is unbounded.
5. `CLOUD_FETCH_DEADLINE_MS = 45_000` (`providers.js`, ~line 254) cuts the call; in practice also when streaming.

## 3. Other ways we tried to turn thinking off through Nightshift (2026-10-23, all failed)

| Attempt | Result |
|---|---|
| `/no_think` as the first line of the system prompt (a red-team prompt, 600-character excerpt) | 123 s, 502 (three 45 s cuts) |
| An assistant prefill `<think></think>` after the user message (the reader prompt, a full report) | 68 s, 502 |
| Shorter input: the red-team prompt on a 350 / 600 / 1,300-character excerpt | 9.8 s / 30.8 s (3,840 of 4,000 tokens) / cut at 45.2 s, answer truncated |
| The same red-team prompt at step 3, with a ledger of two failed attempts | 130 s, 502: the model thinks longer once easy answers are ruled out |
| The pre-registered red-team chain v1 through Nightshift | its first 3 steps each failed at 136 s; the run was stopped and declared void (`docs/preregistration/adversary-chain.md`) |

## 4. What we did about it on 1.2.1 (superseded by §6: since 1.2.3 the ladder runs through Nightshift)

- Calls that need a thinking switch or budget (the reader's two rungs, the red-team generator) go to NVIDIA direct, where both are honoured to the token (`docs/evidence/thinking-budget.md`).
- Nightshift writes the case note, a short prompt that fits its contract: 24 of 24 answers were Super VL with a valid Ed25519 receipt signature, none from cache; median 22.8 s (`logs/notes-batch-2026-10-23.txt`).
- A model id alone does not pin a Nightshift lane, so every call requires the winning model in the signed receipt and rejects a substitute.
- If Nightshift gains a per-request thinking switch, the rungs move back with a one-line change (`provider=` in `app/engine/rungs.py`).

## 5. Three Nightshift models on the case-note job (2026-10-23, after Meterless said Super VL had reliability issues)

Each model pinned explicitly (`require_model`, signature against the pinned key, cache refused), the note prompt on 3 cases (`logs/nightshift-note-models-2026-10-23.jsonl`):

| Model requested | Answers | Notes |
|---|---|---|
| `nvidia/nemotron-3.5-super-vl-120b-a12b` | 1 of 3 (42.7 s, signed, passed the guard) | 1 × 502, 1 timeout (500–540 s with retries) |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | 0 of 3 | 502s and a timeout |
| `nvidia/nemotron-3-super-120b-a12b` | 0 of 3 | one call was **won by Super VL instead** and refused by our receipt check (an explicit id did not pin the lane on this Windows build); 502 and a timeout |

The same note prompt sent to NVIDIA directly at the same time: 146.7 s with thinking on (as Nightshift sends it), 1.3 s with thinking off. So the hosted model itself was slow; through Nightshift the call meets the 45 s cut. Nothing in our code changes: the note keeps Super VL, and the receipt check keeps refusing a substituted model.

## 6. Nightshift 1.2.3 (Windows, installed 2026-10-23): the limits above are fixed

Read in the new engine code: `proxy.js` now passes `chat_template_kwargs` and `reasoning_budget` through, and `providers.js` (`nvidiaThinkingBody`) lets "a caller that names a kwarg get exactly that kwarg (2026-10-22: it used to be replaced by the row default)"; `reasoning_budget` is sent from the request. `CLOUD_FETCH_DEADLINE_MS` is still 45 000, but budgeted reads were not cut in practice (below). 1.2.3 also gates Super VL off by default ("temporarily excluded … after repeated empty, aborted and 500 responses"; their note: 31 of 94 hosted calls failed in two reviews); we opted back in with the documented flag `NVIDIA_SUPER_VL = "true"` (in the engine's key-value store, `state/engine-kv.json`), so that every read stays on the model all our measurements used. An opted-in Super VL stays out of automatic races; only an explicit request reaches it, so `meterless/text` alone finds no lane on this setup.

Measured through Nightshift 1.2.3, Super VL pinned, the reader prompt on full reports (`logs/nightshift-123-super-vl-2026-10-23.txt`):

| Rung | Result |
|---|---|
| Thinking off (`enable_thinking: false`) | 3 of 3 answered in 1.9 s, 7.0 s, 8.7 s (163–273 completion tokens) |
| 4k budget (`enable_thinking: true`, `reasoning_budget: 4000`) | 2 of 2 answered in 74.3 s and 91.7 s, 4,174 and 4,215 completion tokens (the budget plus the answer), not cut |
| Every answer | Super VL in the signed receipt, signature verified against the pinned key (`7a6d14e27e1a`, unchanged by the update), none from cache |

So the evidence ladder now runs through Nightshift by default (`app/engine/rungs.py`, `LADDER_PROVIDER`); `run --provider nvidia` keeps NVIDIA direct.

Images on 1.2.3: the `vision` class is ready (served by Super VL), but Nemotron Parse is not offered and the `perception` class is "unavailable" ("no lane carries the processing capability"), so Parse on the original scans stays on NVIDIA direct.

## 7. Probes on 1.2.3 (2026-10-23 evening)

- **Super VL with a scan image, pinned, through Nightshift:** two calls with one page of the TCGA-A2-A0CV scan (PNG 1024×1280, then a 211 KB JPEG), thinking off: both failed with HTTP 502 after the client's retries. The same JPEG to NVIDIA direct answered in 14.8 s (1,349 prompt tokens, so the image was read), but it reasoned in the answer text despite `enable_thinking: false` and stopped at the 1,500-token cap. So reading a scan with Super VL (a "scan witness") is not possible through Nightshift on this setup; a direct-only measurement is possible but not run yet.
- **Ultra through Nightshift:** `nvidia/nemotron-3-ultra-550b-a55b` is listed and answers with a verified receipt (pinned key). Its reasoning arrives inside the answer text, ending in `</think>` with no opening tag (NVIDIA direct puts it in `reasoning_content`); `strip_think` now removes it. One-line answer: 14.1 s through Nightshift, 1.0 s direct.
- **Lightning (cloud) through Nightshift:** thinking off, signed and pinned, 0.7 s for a one-line answer.

## 8. Nightshift injected H-MEM memory across work items (2026-10-24, the Ultra critic run)

In the pre-registered Ultra critic run (46 calls, Ultra pinned, every call with its own unique `meterless-scope` item id), 5 answers came back with `egress.sent.context_sources = ['messages', 'hmem:1 records']`: Nightshift's built-in H-MEM added a memory record to the request. Every one of the 5 was a call whose report had already been sent earlier in the same run (a second field of the same case, or a planted control on a case already read). Our receipt check requires `context_sources` to be exactly `['messages']` (AGENTS.md) and refused all 5 as `ReceiptMismatch`; they are reported as failures and were not re-run (`logs/ultra-critic.jsonl`).

What follows: (1) memory can cross per-item scopes when the same document repeats, which would quietly break the independence of a blind read; (2) every answer this project accepted passed the same check, so no accepted reading carries injected memory; (3) this is the measured reason the product refuses memory on its reads (the "why one engine" paragraph), not a preference. Reported to Meterless as a bug candidate.
