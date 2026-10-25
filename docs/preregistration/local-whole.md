# Pre-registration: the local first read on whole reports, no cut (written 2026-10-26, frozen before the first call)

`python scripts/local_whole_run.py run` refuses to run if `app/engine/local_whole.py` or any module it reuses (`local_mode.py`, `local_r1.py`, `rungs.py`, `run_case.py`, `reader.py`, `quotes.py`) differs from the hashes in `local-whole.json`, if the drawn records changed, if the prediction is not written, or if it has run once.

## Why (disclosed)

- **The published local mode** (`docs/preregistration/local-mode.md`, result in `docs/evidence/local-mode-results.md`, which stands) met its bar: 20 of 20 first reads local, 0 disagreements. But it cut 6 of the 20 reports to their node and staging sentences: on this PC's 16 GB GPU, Nightshift loaded the local Lightning lane with a 4,096-token window.
- **After the Nightshift 2026-10-26 release and a restart of the local lane,** probes show local Lightning answering ~13,000-token prompts: lane `nemotron-3-5-lightning-3-2`, model `local-runtime/nemotron-3.5-lightning-30b-a3b`, egress empty, GPU memory rising during the call (`logs/probe-nightshift-update-2026-10-26.txt`). Every report here is far shorter.
- **This test removes only the cut, on 20 new records:** census-2 records the local first read has never seen (local mode's 20 excluded; seed 20261026). So it is not a re-run of the published test.

## Design

- **Unchanged from local mode:**
  - the prompt, the guard on the full report, and the chain (whatever the local first read leaves open goes to the cloud deep read as shipped);
  - the frozen local job checklist: privacy local-only; lanes resolved exactly the local Lightning lane; attempt lane local; a local Nemotron model; model and egress honoured; not truncated;
  - the referee: the census's cloud closings for the same fields.
- **Added:**
  - the records: 20 new census-2 records, never read locally (seed 20261026);
  - 6 of these 20 reports are longer than 7,000 characters (the longest 13,003): under local mode's rule they would have been cut;
  - every report is sent whole;
  - each attempt must be answered by `local-runtime/nemotron-3.5-lightning-30b-a3b`. A Bolt lane exists on this PC and is removed before the run; a Bolt answer fails the checklist.
- **Gate:** one local job of about 13,000 tokens runs first. If it is refused, or not answered by local Lightning, the run is void and nothing else is called.
- Nothing is stored.

## Claim, kill, void

- **Claim:** every first read local by the checklist and answered by local Lightning, every report sent whole, and 0 local first-read closings that differ from the census's cloud closing.
- **Kill:** any first read not local or not local Lightning, or any disagreement.
- **Void:** the gate fails, or more than 6 of 20 provider failures. Never re-run.
- **Report only:** records settled by the local first read; the longest report sent.

## Prediction

In the json, written before the run.
