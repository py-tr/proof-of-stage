# Meterless: Nightshift versions and the provider contract

Started as text moved verbatim from the README on 2026-10-25; the 2026-10-26 section was added after that release.

## Nightshift: what 1.2.1 could not do, and what 1.2.3 fixed

We integrated Nightshift first and measured where it could not do the job (`docs/evidence/nightshift-limits.md`): on 1.2.1 it replaced the client's thinking switch with the model's default (thinking on), forwarded no `reasoning_budget`, and cut cloud calls at 45 s, so the evidence chain's two text steps and the red-team generator had to go to NVIDIA directly. We reported it to Meterless with the code lines (`providers.js`, `nvidiaThinkingBody`); Meterless confirmed the fix in a private reply. The cloud timeout is already configurable in 1.2.3: the `cloudTtfbMs` setting (5–300 s, 45 s by default) or per request with the `meterless-ttfb-ms` header; it limits the time to the first token, not the whole call. 1.2.3's code already says "a caller that names a kwarg gets exactly that kwarg (2026-10-22: it used to be replaced by the row default)".

Measured on 1.2.3, Super VL pinned, the reader prompt on full reports (`logs/nightshift-123-super-vl-2026-10-23.txt`): thinking off 1.9–8.7 s; a 4k budget 74–92 s and not cut (the limit is time to the first token); every answer Super VL, signed by the pinned key, none cached. Nightshift's usage reports no reasoning-token count, so through Nightshift the budget shows only as completion tokens of about the budget plus the answer (4,174 and 4,215 at 4,000); the to-the-token measurement is the one made directly (`docs/evidence/thinking-budget.md`). One direct read of the same report took 40.7 s, at a different time and load, so we draw no speed comparison.

Still direct: Nemotron Parse on the scan images (no Nightshift lane for Parse); Super VL reading page images (on 1.2.3 pinned image requests are refused with `no_vision_model`, because the vision gate filters the automatic pool before the pin and every NVIDIA vision row is experimental; the same requests worked on 1.2.1; reported to Meterless, `logs/capability-retest-2026-10-24.jsonl`); and the finished red-team run v2, pre-registered on NVIDIA direct because 1.2.1 could not carry its budget (`docs/evidence/adversary-chain-results.md`).

## The 2026-10-26 release: re-checked within hours

All probes are logged in `logs/probe-nightshift-update-2026-10-26.txt`; the regression is in the same folder.

- **Signing key:** unchanged (fingerprint `7a6d14e27e1a`).
- **Pinned calls:** Lightning (thinking off), Super VL (4k budget), Ultra and Bolt E4B were each served exactly as requested, with verified signed receipts.
- **Bolt:** now reachable through Nightshift. Measured earlier on NVIDIA direct, it had no lane then; Lightning keeps the first read by the seat rule.
- **Automatic routing:** `meterless/text` routes again, to the local Lightning lane, with a verified signature (`logs/doctor-2026-10-26.txt`, all 8 doctor checks pass). On 1.2.3 it found no lane, and the 2026-10-26 regression run made before the local lane was started failed this check too.
- **Local window:** after a restart of the local lane, the local Lightning lane's window is 16,384 tokens (`ctx_per_slot` in Nightshift's lane config, excerpt in `logs/nightshift-lanes-2026-10-26.txt`). Before, it was 4,096, which forced cutting long reports. A pre-registered run then read every report whole on this PC: 20 of 20, 0 disagreements (`docs/evidence/local-whole-results.md`).
- **Local thinking:** a local attempt with thinking on ends after roughly 70-90 seconds with an empty response, before a thinking read of a report finishes. Thinking-off reads finish in seconds. There is no setting for this in the config files, so a local deep read stays untested (`docs/evidence/local-deep-results.md`, void).
- **Still refused:** image requests pinned to Super VL ("no configured vision-capable model admits them"). The app says this edition has no Vision duty yet, so scans stay NVIDIA direct.
- **Reasoning is not returned:** with thinking on, Nightshift returns Super's answer without its reasoning (no think span, no reasoning field), also when asked with `include_reasoning` or `reasoning_format` (probes in the log above). Nightshift's own engine code shows why: the reasoning stream is used only as a liveness signal (`engine/js/engine/orchestrator.js`, the `onReasoning` callback records a timestamp; `providers.js`: "Reasoning is liveness, never answer text"). So a check that the model's reasoning contains the accepted quote cannot be run through this build.
- **Scans through Nightshift's own OCR (tried, not installed):** Nightshift reads image attachments of a Jobs API job with its built-in PaddleOCR reader and exposes the result at `/v1/jobs/{id}/ocr`. Our probe attached one scanned page; the job recorded it as eligible, but the OCR failed with `ocr_unavailable: no meterless-ocrd binary` (`logs/probe-ocr-hybrid-2026-10-26.txt`). The reader ships uninstalled on Windows, and this edition shows no install button; its installer is a separate script. We did not install it. Scans stay on Parse v1 + Super VL (NVIDIA direct).
- **A side effect we caught:** with a second local lane (Bolt) on the race row, local jobs resolved two lanes and our own lane check refused them. We removed that lane.

## Meterless Runtime as a provider: where we stand (provider contract v4)

Graded against the levels in Meterless' own "Grade my provider integration" prompt (meterless.ai/engines.html). Run `python -m app.cli doctor` to see each check live.

| Level | What the contract asks | Us | Where |
|---|---|---|---|
| L0 Text | `meterless/*` routing modes on `/v1/chat/completions`, the real bearer token, 401/403 shown as unauthorized | yes on the 2026-10-26 release with the local lane started (`logs/doctor-2026-10-26.txt`: `meterless/text` routed to local Lightning, signature verified); earlier: health reads `/v1/models` (online / unauthorized / offline); `doctor` sends a plain request on `meterless/text`, which returned a string on 1.2.1 (routed to a local Lightning lane); on our 1.2.3 setup it at first found no lane (an opted-in Super VL stays out of automatic routing and no other lane was on Race); in the 2026-10-25 regression `doctor` routed `meterless/text` to the local Lightning lane with a verified signature (`logs/regression-20261025T145759.txt`). The product's calls name their model explicitly (Lightning, Super VL or Ultra) and require it in the signed receipt (on 1.2.1 one explicit request for another model was won by Super VL and refused by that check) | `app/providers/nightshift.py`, `app/cli.py` |
| L1 Discovery | `/v1/models` and `/v1/meterless/classes` (both shapes), unknown `meterless/*` ids kept | yes: `nightshift.discover()`; doctor prints the text class state and confirms Super VL is a cloud lane | `app/providers/nightshift.py` |
| Errors | the server's message first, then its `fix[]`; a 429 retries after 2, 4 and 8 s | yes | `app/providers/nightshift.py` |
| Local-only | local-only work never reaches a cloud provider | yes: Jobs API with `privacy: local-only`, every resolved lane checked | `nightshift.local_job` |
| L2+ | attachments, media, transcription, 3D, Quick Connect | not used (a text-only audit) | |

One deliberate difference: the contract sends `meterless-scope: user` on chat; we send a unique `meterless-scope` per call, so the runtime's memory never mixes one case's report into another's answer (we saw the runtime inject memories into requests early on). Every receipt is checked: the winning model, `egress`, `context_sources` (only `messages`), the cache status and the Ed25519 signature against the pinned key.

