# 0003: The red-team lane is the Markovian chain

**Context.** Testing the guard needs many attacks that learn from earlier verdicts. Sending the whole attack history each step grows the prompt with every step.

**Decision.** The red-team lane runs the vendored Markovian engine unmodified, with Super (through Nightshift) as the generator (`app/engine/adversary.py`). Each step Super sees a fixed excerpt and a ledger of earlier attempts that our code writes from the real guard's verdicts, never the model's own state. The cases, true counts, prompt and scoring are frozen before the first call.

**Evidence.** v2: 1 guard bug in 60 steps, fixed. v3 after guard rounds 5 and 6: 0 wrong accepts in 57 judged steps (`docs/evidence/adversary-chain-results.md`, `docs/evidence/adversary-chain-v3-results.md`). Saved tokens are reported as absolute estimates, history against ledger, with the engine's own estimator.

**Cost.** The ledger is a summary, so the attacker repeats itself (27 of 60 v3 steps repeated an earlier attack). A red team that passes is evidence about these attacks, not proof against all of them.
