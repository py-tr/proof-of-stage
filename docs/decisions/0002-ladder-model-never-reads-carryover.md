# 0002: The ladder's model never reads the carryover

**Context.** The evidence ladder reads one case in rungs (R1 thinking off, R2 a 4k budget, R3 the scan). A later rung that sees the earlier answer can anchor on it, and then two rungs agreeing says nothing.

**Decision.** Our code writes the carryover after every rung (`{case, need, consulted, ledger}`), and the Markovian engine stores it, but a rung's model call gets only the fixed reader prompt and one document (`app/engine/rungs.py`). The carryover decides which fields are still open and which rung runs next; it never reaches the model.

**Evidence.** The chunk log records each rung's `incoming_carryover` next to the call (`logs/markovian-chunks.jsonl`), and the reader's messages are built from the system prompt and the document alone (`read_report` in `app/reader/reader.py`).

**Cost.** A later rung cannot be told what the earlier one got wrong; it simply reads again, which costs tokens. The dial test measures that cost (`docs/evidence/dial-sample-results.md`).
