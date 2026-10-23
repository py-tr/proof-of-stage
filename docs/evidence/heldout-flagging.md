# Staircase: held-out result (scored 2026-10-22 ~20:00 Prague; the devB step was stopped by the user's decision to free the NVIDIA key)

Scored by `stair.py score_ho` from cached outputs (0 new calls; 351 held-out calls made earlier). Pre-registered rules: PREREG.md.

| Step | Flags | Correct | Precision (Wilson 95%) | Lift |
|---|---|---|---|---|
| S1–S3 | 10 | 4 | 40.0% [16.8, 68.7] | 9.6× |
| S4–S5 (final gated pipeline) | 4 | 2 | 50.0% [15.0, 85.0] | 12.0× |

- Held-out set: 251 reports, 313 printed fields, 13 discordant (base rate 4.2% [2.4, 7.0]).
- Natural discordances flagged: S1 4/13, S5 2/13 (low recall).
- Pre-registered held-out line (S5 precision ≥ 50% with ≥ 20 flags): **not met; not reachable at this n** (4 flags), as predicted in PREREG.md.
- Not measured: devB (stopped), dev-tier seeded recall at S5.
- Scope: this is the OLD printed-vs-recorded flagging pipeline (Lightning facts → derive1 → gates), not the shipped N-vs-count `fault_field` product. README: an honesty row only.

*Copied from the project's research notes (2026-10-22). Raw call logs and spike scripts stay in those notes and are not part of this repository.*
