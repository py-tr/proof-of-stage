# 0004: Nightshift carries every text call; Parse goes direct

**Context.** Every model call should say which model answered, where the data went and whether the answer was cached. Meterless Nightshift returns a signed receipt for each call; NVIDIA direct returns the served model id only.

**Decision.** The ladder (Lightning at R1 since 2026-10-23, Super VL at R2 and R3), the case note and the red team call Nemotron through Nightshift: the model is pinned in the receipt, the Ed25519 signature must verify against a pinned key (`NS_RECEIPT_PUBKEY`), and a cached answer is refused (`app/providers/nightshift.py`). Nemotron Parse reads scan images on NVIDIA direct: Nightshift 1.2.3 has a vision class, but no lane serves Parse. Super VL on page images also goes direct, because 1.2.3 refuses pinned image requests (`no_vision_model`: the vision gate filters the automatic pool before the pin, and every NVIDIA vision row is experimental; the same requests worked on 1.2.1; `logs/capability-retest-2026-10-24.jsonl`). `run --provider nvidia` stays as a fallback. The Ultra case-note measurement ran on NVIDIA direct and is labelled as such. Ultra does answer through Nightshift 1.2.3 with a signed receipt, but its reasoning arrives inside the answer text (`strip_think` removes it).

**Evidence.** 51 rungs in the 25-case batch, all signed by the pinned key; `doctor` makes a signed call and prints the key fingerprint. Before 1.2.3 Nightshift dropped the thinking switch, so the dial could not run through it; 1.2.3 fixed that (README, "Nightshift: what 1.2.1 could not do, and what 1.2.3 fixed").

**Cost.** One more hop and one more dependency. Super VL is gated off by default in 1.2.3 and needs an opt-in.
