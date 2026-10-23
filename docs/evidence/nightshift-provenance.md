# Do the latest signed runs still read the stored values? (the 10 disagreeing records)

Generated 2026-10-23 20:14 UTC by `python scripts/provenance_ten.py` from the live Zetaris layer and `logs/markovian-chunks.jsonl` (no model call). The records are the 10 that `usl demo` step 12 lists. Stored values are the first ones written (append-only), from earlier NVIDIA-direct runs; the latest ladder runs go through Nightshift with signed receipts.

**18 of 18** stored report values are reproduced by the latest run; those runs have 20 rungs, 20 of them signed Nightshift receipts verified against the pinned key.

| Case | Field | Stored | Latest run | Rung | Model | Receipt | Signature | Match |
|---|---|---|---|---|---|---|---|---|
| TCGA-A7-A26E | N | N1A | N1A | R1 | nvidia/nemotron-3.5-lightning-30b-a3b | rcpt_req_2vfjr0ta | verified | yes |
| TCGA-A7-A26E | count | 1 | 1 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_gyx573fz | verified | yes |
| TCGA-A7-A26H | N | N1A | N1A | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_btaatwv5 | verified | yes |
| TCGA-A7-A26H | count | 1 | 1 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_btaatwv5 | verified | yes |
| TCGA-AO-A03P | N | N1MI | N1MI | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_219oa1xm | verified | yes |
| TCGA-AO-A1KP | N | N1A | N1A | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_mtceoa0m | verified | yes |
| TCGA-AO-A1KP | count | 1 | 1 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_mtceoa0m | verified | yes |
| TCGA-AR-A1AT | N | N0(I+) | N0(I+) | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_1g783swz | verified | yes |
| TCGA-BH-A0BS | N | N1A | N1A | R1 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_ut0xkssw | verified | yes |
| TCGA-BH-A0BS | count | 2 | 2 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_7dm5r1r0 | verified | yes |
| TCGA-BH-A0DD | N | N1A | N1A | R1 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_qy3bzpqa | verified | yes |
| TCGA-BH-A0DD | count | 1 | 1 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_62oijxtu | verified | yes |
| TCGA-E2-A1LI | N | N0 | N0 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_lan44gko | verified | yes |
| TCGA-E2-A1LI | count | 0 | 0 | R1 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_cctsj94v | verified | yes |
| TCGA-E2-A572 | N | N2A | N2A | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_ccc9hb04 | verified | yes |
| TCGA-E2-A572 | count | 8 | 8 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_ccc9hb04 | verified | yes |
| TCGA-EW-A424 | N | N0 | N0 | R2 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_i8ur9t74 | verified | yes |
| TCGA-EW-A424 | count | 0 | 0 | R1 | nvidia/nemotron-3.5-super-vl-120b-a12b | rcpt_req_dnope2v9 | verified | yes |
