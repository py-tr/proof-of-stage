# Attestation census: every stored report value re-read once with a signed receipt (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/attest.md` + `attest.json` (commit e1bc7ee, frozen before the first call). Run 20261025T123148, log `logs/attest.jsonl`, summary `logs/attest-runs.jsonl`. Bundle: `docs/evidence/attest/envelopes.jsonl` (57 signed Nightshift envelopes as received, with our sha256 of the request messages and of the raw answer) and `docs/evidence/attest/pubkey.json` (the public key, fingerprint 7a6d14e27e1a).

## Result

| Measure | Result |
|---|---|
| Stored report values (N category and positive-node count, method nemotron_reader), 26 cases | **42** |
| Reproduced by one signed re-read through Nightshift (same value under the ladder's normalisation) | **42 of 42** |
| Differs / left open / provider failure | 0 / 0 / 0 (not void) |
| Stored quotes re-checked under today's guard (no model) | 42 of 42 accepted |
| Signed receipts captured, signature verified again from the envelope | 57 of 57 (one key, 7a6d14e27e1a) |
| Rows in Zetaris | `oa_pg.attest_receipt` 57, `oa_pg.attestation` 42 (outcome `reproduced`); every attestation row passed the write-time rule (inserted only because its receipt was already a `verified` row) |
| Offline check: `python -m app.verify` | **PASS**: 57 of 57 signatures, 42 outcome rows consistent, 42 of 42 quotes found in the report text on this machine |

Prediction ("about 34–40 of 42 reproduced; 0–3 differ; 0 failures"): exceeded (42).

## What it means, and what it does not

- Every stored report value in the layer has now been read again by the shipped evidence steps through Nightshift, and each re-read carries a receipt whose signature anyone can check offline with the committed key and `python -m app.verify` (change one byte of an envelope and it fails; tests in `tests/test_verify.py`).
- The originals stay as first written (NVIDIA-direct, no receipt); the receipt belongs to the re-read.
- "Reproduced" is not "correct": it means one more read gave the same value. The blind labels still leave TCGA-BH-A0BS and TCGA-E2-A1LI to a person, and Ultra's second reader objects to E2-A1LI.
- The signed body covers the call (model, route, cache, prompt size), not the answer text; the answer hash next to it is ours. The key is the one this Nightshift install presented; Meterless publishes none.
