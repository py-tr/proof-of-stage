# 0008: One Meterless engine, Markovian; no memory on a read

**Context.** Meterless offers four engines (H-MEM, Markovian, World Model, Scout Intent); the requirement is at least one in a working feature, and Meterless confirmed on 2026-10-24 that the unmodified reference implementation counts when it runs a real feature and is shown. Each engine we add is code a judge must be able to check, and each one that touches a reading can change what the model sees.

**Decision.** One engine, Markovian, used twice: the evidence ladder (one chain per case, each rung a chunk, the carryover written by our code and never read by the model, ADR 0002) and the red-team chain (ADR 0003). No memory on a read: every Nightshift call has its own scope, and a receipt showing anything but the messages in its context is refused. World Model would duplicate the semantic layer's append-only ledger (the layer already keeps every value, quote and receipt); Scout Intent ships no reference implementation; H-MEM recall would put earlier cases into a reading, which is the one thing the guard is built to exclude.

**Evidence.** Markovian reference vendored unchanged, conformance 8/8 (`vendor/meterless-markovian`, `tests/test_markovian.py`); 18 of 18 stored values reproduced by signed rungs (`docs/evidence/nightshift-provenance.md`). The one time memory reached a reading it was our own scope reuse, caught by this refusal and published (`docs/evidence/nightshift-limits.md` §8).

**Cost.** No cross-case learning: the system does not get better at a report type by remembering past ones, and the Lightning first rung reads each report cold. Engine count is not a score in the official rules, so we take the narrower, checkable path.
