# Held-out flagging result (a pre-window spike, declared in `metadata.json`; scored 2026-10-22 ~18:00 UTC; the devB step was stopped early to free the API key)

Scored by `stair.py score_ho` from cached outputs (0 new calls; 351 held-out calls made earlier, in the spike). Pre-registered rules: PREREG.md.

| Step | Flags | Correct | Precision (Wilson 95%) | Lift |
|---|---|---|---|---|
| S1–S3 | 10 | 4 | 40.0% [16.8, 68.7] | 9.6× |
| S4–S5 (final gated pipeline) | 4 | 2 | 50.0% [15.0, 85.0] | 12.0× |

- Held-out set: 251 reports, 313 printed fields, 13 discordant (base rate 4.2% [2.4, 7.0]).
- Natural discordances flagged: S1 4/13, S5 2/13 (low recall).
- Pre-registered held-out line (S5 precision ≥ 50% with ≥ 20 flags): **not met; not reachable at this n** (4 flags), as predicted in PREREG.md.
- Not measured: devB (stopped), dev-tier seeded recall at S5.
- Scope: this is the OLD printed-vs-recorded flagging pipeline (Lightning facts → derive1 → gates), not the shipped N-vs-count `fault_field` product. README: an honesty row only.

*Written up on 2026-10-22 from the spike's notes (a pre-window spike, declared in `metadata.json`). The spike scripts and raw call logs are not committed.*
