# Architecture

How one record is checked, from the sources to a person's decision. Every arrow that touches a model goes through Meterless Nightshift with a signed receipt, except Nemotron Parse on the scanned pages (NVIDIA direct; Nightshift has no Parse lane). The readers share one state, the Zetaris layer, and three loops run around it: the evidence chain, the red-team loop, and the second reader.

```mermaid
flowchart LR
  subgraph Sources["Three live sources"]
    GDC["NCI GDC REST API<br/>recorded stage, node counts"]
    FS["File store<br/>paraphrased rules, report text, Parse blocks"]
    PG["Postgres (append-only)<br/>readings, decisions, receipts"]
  end

  subgraph USL["Zetaris semantic layer: stage_audit"]
    SC["stage_check<br/>count rule, fault_field,<br/>positive_nodes_checked"]
    DQ["DQ rules<br/>nodes_consistent: 24 invalid<br/>nodes_within_tested: 0 invalid"]
  end

  subgraph Chain["Evidence chain on the Meterless Markovian engine (per case)"]
    F1["First read<br/>Nemotron Lightning, thinking off<br/>may only close a field that agrees"]
    F2["Deep read<br/>Nemotron Super VL, 4k budget"]
    F3["Scan read<br/>Nemotron Parse + Super VL"]
  end

  G["Quote check (code)<br/>quote in the report AND shows the value"]
  U["Second reader<br/>Nemotron Ultra, can only object<br/>with a checked quote"]
  RT["Red-team loop<br/>Super on the Markovian engine<br/>attacks the quote check: 0 of 57"]
  P["Case page, /how, /receipts<br/>verdict, quote, receipt, scan box"]
  H["A person decides<br/>a new row, never an edit"]
  AT["Second USL attest_audit<br/>receipts + re-reads, 5 DQ rules"]

  GDC --> USL
  FS --> USL
  PG --> USL
  SC --> DQ
  DQ -- "the review queue" --> F1
  F1 -- "still open (code-written note)" --> F2
  F2 -- "still open" --> F3
  F1 --> G
  F2 --> G
  F3 --> G
  G -- "accepted values (first write wins)" --> PG
  RT -- "attacks" --> G
  U -- "objection shown to the person" --> P
  SC --> P
  P --> H
  H -- "decision row" --> PG
  PG --> AT
```

- **The rule finds the record** (SQL in the layer, no model): the recorded N category and the record's own node count cannot both be true.
- **Nemotron may only quote**: each step reads one document and never the carryover. The Markovian engine carries a code-written note of which fields are still open, picks the next step, and stops when nothing is open. Lightning reads first with thinking off, Super VL with a thinking budget reads what stays open, then Parse plus Super VL on the original scan.
- **The quote check decides what counts**: a value is accepted only if its verbatim quote is in the document and shows that value.
- **The layer names the field** (`stage_check.fault_field`) and serves the three answers to "how many patients are node-positive?" (`usl demo` step 11).
- **A person decides**: each decision is a new append-only row, and the layer's answer includes it.
- **The second reader** (Nemotron Ultra, shipped, read-only): it can only object, with a quote the check verifies, and the objection is shown to the person; served from its logged run.
- **The red-team loop**: Super, on the same Markovian engine, attacks the quote check with a code-written ledger of its earlier attempts (0 wrong accepts in 57 judged attacks; 27 of 60 steps repeated an earlier attack despite the ledger).
- **Trust you can check**: every stored value was re-read once with a signed receipt; the receipts and re-reads are a second USL (`attest_audit`) with 5 DQ rules, and `/receipts` checks every signature in the browser.
- **An agent reading the layer**: given its own Zetaris account that can read only the checked values, an agent answered from them (probe 5); Zetaris refused that account everything else.
- Measurements: `docs/results.md` and `docs/evidence/`.
