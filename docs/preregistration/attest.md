# Pre-registration: attestation census of the stored report values (written 2026-10-25, frozen before the first call)

`python scripts/attest_run.py` refuses to run if `app/engine/attest.py`, `app/providers/envelope_tap.py`, `app/usl/attest_store.py`, `app/engine/rungs.py`, `app/reader/reader.py` or `app/reader/quotes.py` differ from the hashes in `attest.json`.

## Why (disclosed)

A claims audit (2026-10-25) found that the stored report values were first written by early NVIDIA-direct reads with no receipt, that the logs keep only receipt ids and the run-time check result, and that the signed receipt body does not hash the answer. This census re-reads every stored value once through Nightshift and keeps every signed envelope, so the receipts can be checked by anyone. Designed after the labels, the councils and two outside reviews (council 11; Grok); nothing here reads the labels.

## Design

- **Cells (frozen by query, listed in the json):** every `oa_pg.derived_extraction` row with method `nemotron_reader` and field `N` or `NPOS`: **42 cells on 26 cases** (26 N, 16 counts). Reason rows and T are not cells. The stored rows are not touched (first write wins); the originals stay receipt-less.
- **One read per case**, never re-run: the shipped evidence steps (`rungs.climb`: first read Lightning thinking off, deep read Super VL at a 4k budget, scan read where a parsed scan exists), Nightshift with the model pinned in the receipt, signature required, cache refused, a fresh item id per run. Temperature is not sent, as in the shipped reader (Super's answers at temperature 0 were not textually deterministic, logged 2026-10-24), so this measures the product as it ships.
- **Envelopes:** every call runs inside `envelope_tap.capture()`; each envelope ({body, pubkey_b64, sig_b64}), with our sha256 of the request messages and of the raw answer, goes to `docs/evidence/attest/envelopes.jsonl` (committed) and to `oa_pg.attest_receipt`, with the signature checked again by `receipts._signed_receipt` (state, signer fingerprint).
- **Outcome per cell:** `reproduced` (the steps closed the field with a value equal to the stored one under the ladder's own normalisation, `rungs._comparable`), `differs` (closed with another value), `not_re_accepted` (left open), `provider_failure`. Written to `oa_pg.attestation`; a row with a receipt is accepted by the layer only if that receipt is already a `verified` row (checked live before freezing: refused without one).
- **No-model column:** the stored value and quote re-checked under today's guard (`judge_field` / `judge_count`), "accepted" or the reason; guard rounds 5–6 came after the original writes.

## Claim, void, prediction

- **Result sentence (written now, filled after the run):** "[k] of 42 stored report values were reproduced by one signed re-read through Nightshift; [d] differ, [o] were left open, [f] failed; the differing and open cells are listed and go to a person. Every receipt and the signing key are committed." No sentence says the stored values are correct, or that the receipt proves what Nemotron said (the signed body does not cover the answer; the answer hash is ours).
- **Void:** more than 5 of 26 cases fail at the provider. Never re-run, nothing tuned after the run.
- **Prediction (before the run):** about 34–40 of 42 reproduced (the 18 of 18 on the 10 disagreeing records is the precedent; the steps leave some cells open), 0–3 differ, 0 provider failures.
