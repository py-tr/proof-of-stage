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

## 4. What we do about it

- Calls that need a thinking switch or budget (the reader's two rungs, the red-team generator) go to NVIDIA direct, where both are honoured to the token (`docs/evidence/thinking-budget.md`).
- Nightshift writes the case note, a short prompt that fits its contract: 24 of 24 answers were Super VL with a valid Ed25519 receipt signature, none from cache; median 22.8 s (`logs/notes-batch-2026-10-23.txt`).
- A model id alone does not pin a Nightshift lane, so every call requires the winning model in the signed receipt and rejects a substitute.
- If Nightshift gains a per-request thinking switch, the rungs move back with a one-line change (`provider=` in `app/engine/rungs.py`).
