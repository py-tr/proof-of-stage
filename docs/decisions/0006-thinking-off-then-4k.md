# 0006: Thinking off first, then a 4k budget

**Context.** Super's thinking costs tokens and seconds. Measured on 42 easier extraction reports (a pre-window spike set, declared): thinking off got 26/42 with both fields right at a median of 19 completion tokens; a 4k budget got 30/42 and gave the same answers as unlimited thinking, item for item (`docs/evidence/thinking-budget.md`).

**Decision.** R1 reads with thinking off and may only clear a field (an accepted value that agrees with the registry and is self-consistent under the count rule), never accuse one. Whatever stays open goes to R2 with a 4k budget, then R3 the scan.

**Evidence.** Pre-registered dial test on 30 consistent records through Nightshift: 15 of 28 settled by the thinking-off read alone, 0 of 31 of its closings contradicted by a 4k control, 40% fewer completion tokens than always reading at 4k (`docs/evidence/dial-sample-results.md`). On the contradiction queue R1 never settles a case, by design.

**Cost.** On cases that need R2, the ladder pays for both reads. Case notes keep thinking on: with it off, only 4 of 25 notes passed the note guard.
