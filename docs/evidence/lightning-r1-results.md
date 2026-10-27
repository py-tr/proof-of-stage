# Lightning as the cheap rung: results (pre-registered, run 2026-10-23)

Pre-registration: `docs/preregistration/lightning-r1.md` + `lightning-cases.json` (commit f5b3f3c, frozen before the first call; the run checked the code hashes at start). Logs: `logs/lightning-r1.jsonl` (one row per record), `logs/lightning-r1-runs.jsonl` (the summary), `logs/lightning-r1-2026-10-23.txt`. Run 2026-10-23 17:26 UTC, after the M0 baseline finished.

## Validity

28 of 28 records read, one after another, through Nightshift: every answer `nvidia/nemotron-3.5-lightning-30b-a3b` (cloud) in the receipt, signature verified against the pinned key (28 of 28), none cached. 0 provider failures. **Not void.**

## Result

| Measure | Lightning R1 | Super R1 (dial run, same records) |
|---|---|---|
| Records settled (N and the count both closed) | **18 of 28** | 15 of 28 |
| Fields closed | **38** | 31 |
| The always-4k Super control on those closings | **33 agree, 0 disagree, 5 unconfirmed** | 30 agree, 0 disagree, 1 unconfirmed |
| Completion tokens (sum) | 7,753 | 4,703 |
| Seconds (sum) | **114** | 436 |

Kill lines: unsafe (the control contradicts more than 10% of the closings) **not hit** (0 of 38); not worth it (settles fewer than Super's 15) **not hit** (18). By the pre-registered rule, **Lightning replaces Super at R1.**

The 5 unconfirmed closings, checked one by one (the control did not accept a value, so it can neither confirm nor contradict):
- TCGA-A2-A04X (count 0): the control read 0 too, but its quote failed the guard (`quote_not_in_report`); Super's R1 closed the same values.
- TCGA-A2-A0EV (N0, count 0): the control read N0 but its quote was rejected (`quote_does_not_support`) and it abstained on the count; neither Super rung closed this record.
- TCGA-E2-A1B1 (N1A, count 1): the control's answer was not JSON; the ladder's 4k rung later closed the count at the same value, 1.

Lightning's own rejections (14 fields): 6 `count_not_in_quote`, 4 `answer_not_json`, 3 `quote_does_not_support`, 1 `quote_not_in_report`. Each goes up the ladder to the 4k rung, as with Super.

Prediction (before the run): "Lightning is safe (0 or 1 disagreement) but settles fewer records than Super." **Half held**: safe (0 disagreements), but it settled **more**, not fewer.

## What it means, and what it does not

- On records whose registry fields agree, the 30B model with 3B active parameters clears more fields than Super VL at the first rung, (in the seconds of this run; a controlled same-session re-run showed it is not faster, `docs/evidence/r1-timing-results.md`), and no clearing was contradicted by a 4k Super read. It writes more completion tokens than Super with thinking off (7,753 against 4,703); we measured tokens and seconds, not compute.
- 5 of Lightning's 38 closings rest on R1 alone (the referee could not check them), against 1 of Super's 31. None was contradicted, but "unconfirmed" is not "confirmed".
- The two R1s were judged by different guard versions: Super's R1 in the dial run (finished 14:07 UTC) before guard round 6 (commit de27174, 15:01 UTC), Lightning's after it (17:26 UTC). Round 6 tightened the count guard, so if anything it made Lightning's closings harder to earn (an inference, not measured). Seconds were measured hours apart on a load-sensitive endpoint, so "a quarter of the time" is indicative, not a controlled comparison; the tokens are the fairer cost measure. (Correction 2026-10-24: the controlled re-run, `docs/evidence/r1-timing-results.md`, found Lightning not faster, median 2.17 s against 1.92 s per read, so "a quarter of the time" does not hold. The comment in `app/engine/rungs.py` that repeats it is in a hash-frozen file and is left as it is; this line corrects it.)
- n = 28 consistent records drawn for the dial test; the review queue's contradiction cases are not affected (R1 may only clear a field that agrees with the registry, so on the queue it never settles a case).
