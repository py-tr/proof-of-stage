# FEC filings at read level: results (pre-registered, run 2026-10-25)

Pre-registration: `docs/preregistration/fec-read.md` + `fec-read.json` (commit d7ccba0, prediction 0872755, frozen before the first call). Run 20261025T123400, log `logs/fec-read.jsonl`, summary `logs/fec-read-runs.jsonl`. Sample: 12 of the 93 eligible impossible 2018 Senate paper filings (seed 20261025); all 12 PDFs downloaded; Nemotron Parse (v1, NVIDIA direct) on pages 3–6; amounts taken from the Parse text by frozen rules and checked by `app/fec/guard.py`; no other model.

## Result (as pre-registered)

| Measure | Result |
|---|---|
| Filings read cleanly (all four cash-summary lines accepted) | **4 of 12** |
| Verdicts | "the filing itself does not add up" **4**, "not read" **8** (summary page not found in pages 3–6: 2; one or more lines not found or rejected: 6) |
| "The filing contradicts the record on one field" | 0 |
| Parse page failures | 0 (not void) |
| **Claim line** (≥ 5 read cleanly and ≥ 3 name one field) | **not met**: counts only |

Prediction ("5–8 of 12 read cleanly; 2–4 contradict the record on one field; 1–2 do not add up"): did not hold.

## What a look at the four pages showed (after the run; the builder, a lay reader; not pre-registered)

The four "clean" reads were checked against the rendered summary pages (`data/fec/pdf/`, not committed):

- **The extraction misread the amounts.** Three of the four forms are handwritten; the frozen rules took the wrong numbers on most of their lines (for example "0.08", "7.54", "54" where the form shows $500.00, $34,957.54 and $25,042.54), and `app/fec/guard.py` accepted them: its line-label check is too loose (a known weakness noted before the run). So the automated read level does not work on these forms, and the 4 "clean" reads are not clean.
- **But each of the four filings really does not add up, as written by the committee.** Courtland Sykes for Senate (1202879): $500 + $14,133 − $12,752 = $1,881, the form says $1,810.61 (gap $70.39, exactly the database's gap). Eve Reyes-Aguirre Committee (1227521): $2,368 − $1,750.64 = $617.36, the form says $546.49 (gap $70.87, exactly the database's gap). BoyantonForSenate (1231036): beginning $60,000 and receipts $34,957.54, yet subtotal and closing cash $25,042.54, and total disbursements $0.00 under a $25,000 loan repayment. Pat Harris for Senate 2018 (1236339): $82,999.53 + $1,595.26 − $66,931.41 = $17,663.38, the form says $39,542.23.
- So, on these four, the "impossible" database rows are not typing errors: the database copies filings whose own arithmetic is wrong (to the cent on two of them).

## What it means, and what it does not

- The cancer-registry pipeline does not transfer to handwritten FEC forms as built: page finding worked on 10 of 12, but amount extraction did not. Stated as a limit.
- The rule-level finding stands (`fec-rule-results.md`), and on the four filings a person read, the error is in the source document itself. n = 4, one lay reader, after the run; no rate is claimed.
- Not tested: a model reading the amounts (Super VL on the page image, or Super on the Parse text), a stricter label check, typed (e-filed) forms. No re-run.
