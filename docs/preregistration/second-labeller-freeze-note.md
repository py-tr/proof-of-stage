# Second labeller: freeze note (2026-10-26 00:01 Prague, before any scoring)

- The labels were made by a second lay person (not the builder), named here only as "a second lay labeller", on the builder's PC, in a private browser window with only the blind sheet on screen; the builder explained the sheet's buttons only and gave no help on any case.
- The export was saved as `data/private/second-labeller-export.json` (git-ignored) and frozen byte for byte by `python scripts/second_labeller.py freeze`: `docs/preregistration/second-labeller-labels.json`, sha16 `5ba1405a9ca4b9d4` (`second-labeller-labels.sha16`). 25 of 25 cases labelled, no problems reported.
- Disclosed: the export's `labeller` field reads "the builder (a lay reader, not a pathologist)". That string is hard-coded in the sheet generator (`scripts/make_label_sheet.py`, the first labeller's sheet), not typed by the labeller; the file is left unedited so its hash matches the export.
- This file and the frozen labels are committed before `python scripts/second_labeller.py score` is run.
