# Architecture

How one record is checked, from the sources to a person's decision. Every arrow that touches a model goes through Meterless Nightshift with a signed receipt, except Nemotron Parse on the scanned pages (NVIDIA direct; Nightshift has no Parse lane).

```mermaid
flowchart LR
  subgraph Sources["Three live sources"]
    GDC["NCI GDC REST API<br/>recorded stage, node counts"]
    FS["File store<br/>paraphrased rules, report text, Parse blocks"]
    PG["Postgres (append-only)<br/>readings, decisions"]
  end

  subgraph USL["Zetaris semantic layer: stage_audit"]
    SC["stage_check<br/>count rule, fault_field,<br/>positive_nodes_checked"]
    DQ["DQ rules<br/>nodes_consistent: 24 invalid<br/>nodes_within_tested: 0 invalid"]
  end

  subgraph Ladder["Markovian evidence ladder (per case)"]
    R1["R1 Lightning<br/>thinking off"]
    R2["R2 Super VL<br/>4k budget"]
    R3["R3 Parse + Super VL<br/>the original scan"]
  end

  G["The guard (code)<br/>quote in the report AND shows the value"]
  P["Case page + /how<br/>verdict, quote, receipt, scan box"]
  H["A person decides<br/>a new flag row"]

  GDC --> USL
  FS --> USL
  PG --> USL
  SC --> DQ
  DQ -- "the review queue" --> R1
  R1 -- "still open" --> R2
  R2 -- "still open" --> R3
  R1 --> G
  R2 --> G
  R3 --> G
  G -- "accepted values (first write wins)" --> PG
  SC --> P
  P --> H
  H -- "flag (human_review)" --> PG
```

- **The rule finds the record** (SQL in the layer, no model): the recorded N category and the record's own node count cannot both be true.
- **Nemotron may only quote**: each rung reads one document and never the carryover; Lightning first, Super VL with a thinking budget for what stays open, Parse plus Super VL on the original scan.
- **The guard decides what counts**: a value is accepted only if its verbatim quote is in the document and shows that value.
- **The layer names the field** (`stage_check.fault_field`) and serves the three answers to "how many patients are node-positive?" (`usl demo` step 11).
- **A person decides**: each decision is a new append-only row, and the layer's answer includes it.
- **Off the critical path:** the red-team chain (Super as a Markovian attacker against the guard), the case note (Super, cited facts only), the pre-registered measurements in `docs/evidence/`.
