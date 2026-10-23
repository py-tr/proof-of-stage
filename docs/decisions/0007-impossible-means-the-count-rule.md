# 0007: "Impossible" means the paraphrased count rule says so

**Context.** Calling a registry record wrong needs a rule anyone can check. Full AJCC staging has exceptions the project cannot encode faithfully, and its text cannot be reproduced.

**Decision.** A record is flagged only when its recorded N and positive-node count cannot both be true under a paraphrased count rule (N0 = none, N1 = 1–3, N2 = 4–9, N3 = 10 or more; micrometastases and isolated tumour cells are their own categories), or N is missing and the count gives it. The rule lives in the Zetaris semantic layer (`stage_check`), so the flag is a query, not a model's opinion. Nemotron's guarded reading of the report then names which field the report contradicts, or hands the case to a person.

**Evidence.** 24 of 1,097 records are impossible under the rule and 1 more is derivable: a queue of 25. The report names a field for 21 of them (8 count, 13 N) and leaves 4 to a person.

**Cost.** The rule cannot see what it paraphrases away (subcategories, edition-specific exceptions), so the page shows the rule and says it is paraphrased. Records that are wrong but still possible under the rule are not flagged.
