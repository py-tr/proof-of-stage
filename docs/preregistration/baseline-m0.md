# Pre-registration: Nemotron alone (M0) against the product (A0) and the rule (B0) (written 2026-10-23, frozen before the first call and before the labels are frozen)

`python -m app.cli baseline run` refuses to run if `app/engine/baseline.py`, `app/reader/quotes.py` or the prompt differ from the hashes in `baseline-cases.json`. `baseline score` also refuses if the labels file differs from its frozen hash.

## Question

Does the product's verdict (which registry field the report contradicts) beat what Nemotron Super says when it is simply asked, with no guard, no evidence ladder and no semantic layer? If they agree as often, the guard buys provenance (every accepted value has a located quote), not accuracy, and the README says so.

## Design

- **Cases:** the whole review queue: the 25 stage_check records with `reason_class` `n_count_contradiction` or `n_missing_derivable` (ids frozen in `baseline-cases.json`).
- **M0 (Nemotron alone):** one prompt per case, Super VL through Nightshift (pinned in the signed receipt, no cache). The prompt gives what the labeller saw: edition, the registry's recorded N, recorded positive and examined nodes, what the count rule gives, the full report. It asks for `fault` (node_count / pathologic_n / review), the report's count and N, one verbatim quote and a reason. **Two arms:** thinking off, and a 4k thinking budget. No guard runs on the answer; the only check is whether its quote is found in the report.
- **A0 (the product):** `stage_check.fault_field` as stored (Super's guarded readings, the evidence ladder, the USL rule).
- **B0 (the rule alone):** recompute N from the recorded count, i.e. always `pathologic_n`.
- **Ground truth:** the blind labels (`ground-truth-labels.json`): one lay reader (the builder, not a pathologist) read each report with the registry values and no system output. Disclosed: the labeller had seen the system's verdict on TCGA-A2-A0CV, TCGA-A1-A0SN and TCGA-A7-A26E before labelling. Scoring is reported with and without those three.
- The M0 run happens before the labels are frozen; no one looks at M0's answers until the labels are frozen.

## Measures (fixed now)

- For A0, B0, M0-off and M0-4k: agreement with the label over the labelled cases (a case counts when the labeller chose a field; "a person decides" is a label like the others).
- M0: provider failures and unusable answers, counted as misses and listed; quote-not-in-report rate over parsed answers.
- A per-case table of all four against the label.

## Kill and void lines

- **Void arm:** more than 8 of the 25 calls in an arm are provider failures; that arm is reported only per case. Never re-run.
- **"The guard buys provenance, not accuracy":** stated if M0-4k agrees with the labels on at least as many cases as A0.
- Nothing is re-tuned after scoring: no prompt change, no guard change, no relabelling.

## Prediction (before the run)

A0 agrees with the labels more often than M0-4k, M0-4k more often than M0-off, and B0 is lowest of the four apart from cases where the N category really is wrong. M0 quotes are in the report for most parsed answers (it is a copy task). A guess, written down so the result can contradict it.
