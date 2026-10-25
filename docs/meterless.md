# Meterless: Nightshift versions and the provider contract

Moved verbatim from the README on 2026-10-25.

## Nightshift: what 1.2.1 could not do, and what 1.2.3 fixed

We integrated Nightshift first and measured where it could not do the job (`docs/evidence/nightshift-limits.md`): on 1.2.1 it replaced the client's thinking switch with the model's default (thinking on), forwarded no `reasoning_budget`, and cut cloud calls at 45 s, so the evidence chain's two text steps and the red-team generator had to go to NVIDIA directly. We reported it to Meterless with the code lines (`providers.js`, `nvidiaThinkingBody`); Meterless confirmed the fix in a private reply. The cloud timeout is already configurable in 1.2.3: the `cloudTtfbMs` setting (5–300 s, 45 s by default) or per request with the `meterless-ttfb-ms` header; it limits the time to the first token, not the whole call. 1.2.3's code already says "a caller that names a kwarg gets exactly that kwarg (2026-10-22: it used to be replaced by the row default)".

Measured on 1.2.3, Super VL pinned, the reader prompt on full reports (`logs/nightshift-123-super-vl-2026-10-23.txt`): thinking off 1.9–8.7 s; a 4k budget 74–92 s and not cut (the limit is time to the first token); every answer Super VL, signed by the pinned key, none cached. Nightshift's usage reports no reasoning-token count, so through Nightshift the budget shows only as completion tokens of about the budget plus the answer (4,174 and 4,215 at 4,000); the to-the-token measurement is the one made directly (`docs/evidence/thinking-budget.md`). One direct read of the same report took 40.7 s, at a different time and load, so we draw no speed comparison.

Still direct: Nemotron Parse on the scan images (no Nightshift lane for Parse); Super VL reading page images (on 1.2.3 pinned image requests are refused with `no_vision_model`, because the vision gate filters the automatic pool before the pin and every NVIDIA vision row is experimental; the same requests worked on 1.2.1; reported to Meterless, `logs/capability-retest-2026-10-24.jsonl`); and the finished red-team run v2, pre-registered on NVIDIA direct because 1.2.1 could not carry its budget (`docs/evidence/adversary-chain-results.md`).

## Meterless Runtime as a provider: where we stand (provider contract v4)

Graded against the levels in Meterless' own "Grade my provider integration" prompt (meterless.ai/engines.html). Run `python -m app.cli doctor` to see each check live.

| Level | What the contract asks | Us | Where |
|---|---|---|---|
| L0 Text | `meterless/*` routing modes on `/v1/chat/completions`, the real bearer token, 401/403 shown as unauthorized | partly: health reads `/v1/models` (online / unauthorized / offline); `doctor` sends a plain request on `meterless/text`, which returned a string on 1.2.1 (routed to a local Lightning lane); on our 1.2.3 setup it finds no lane, because an opted-in Super VL stays out of automatic routing and no other lane is on Race. The product's calls name the explicit `nvidia/nemotron-3.5-super-vl-120b-a12b` and require it in the signed receipt (on 1.2.1 one explicit request for another model was won by Super VL and refused by that check) | `app/providers/nightshift.py`, `app/cli.py` |
| L1 Discovery | `/v1/models` and `/v1/meterless/classes` (both shapes), unknown `meterless/*` ids kept | yes: `nightshift.discover()`; doctor prints the text class state and confirms Super VL is a cloud lane | `app/providers/nightshift.py` |
| Errors | the server's message first, then its `fix[]`; a 429 retries after 2, 4 and 8 s | yes | `app/providers/nightshift.py` |
| Local-only | local-only work never reaches a cloud provider | yes: Jobs API with `privacy: local-only`, every resolved lane checked | `nightshift.local_job` |
| L2+ | attachments, media, transcription, 3D, Quick Connect | not used (a text-only audit) | |

One deliberate difference: the contract sends `meterless-scope: user` on chat; we send a unique `meterless-scope` per call, so the runtime's memory never mixes one case's report into another's answer (we saw the runtime inject memories into requests early on). Every receipt is checked: the winning model, `egress`, `context_sources` (only `messages`), the cache status and the Ed25519 signature against the pinned key.

