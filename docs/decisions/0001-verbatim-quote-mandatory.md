# 0001: A value is accepted only with a verbatim quote the code finds in the report

**Context.** A model's reading of a pathology report can be fluent and wrong. A reviewer cannot audit a value that comes with no place in the report.

**Decision.** Every value Super returns (T, N, the positive-node count) must come with one contiguous quote. Code locates the quote in the report (`app/reader/quotes.py`) and then checks that the quote shows the value (`supports_category`, `judge_count` in `app/reader/reader.py`): a stage token or label, a count that passes the count guard (context, fraction floor, labelled total), or the words a category needs. A value that fails any check is rejected with a reason code and goes to a person. The model never writes a value the report does not visibly support.

**Evidence.** Six guard review rounds (`docs/evidence/guard-floor.md`); red-team v3 through Nightshift, 0 wrong accepts in 57 judged attacks (`docs/evidence/adversary-chain-v3-results.md`).

**Cost.** Correct readings with a bad quote are rejected, so some cases go to a person that a looser system would settle. Whether the guard also buys accuracy over Nemotron alone is measured separately (`docs/preregistration/baseline-m0.md`).
