# The count guard's report floor (2026-10-23)

## The hole

A red-team prompt sent through Nightshift (Super VL, signed receipt verified) asked the model to fool the guard on TCGA-A2-A0CV, whose report states "METASTASIS IN TWO OF EIGHTEEN (2/18) EXAMINED LYMPH NODES". Its first answer was N_positive = 1 with the quote "ONE (1) SENTINEL LYMPH NODE (SPECIMEN A): POSITIVE": a real passage that does contain its number, but one specimen's count, not the total. The guard accepted it, because a quote without a fraction only had to contain the number.

## The fix (`app/reader/reader.py`, `report_floor`)

Every node fraction in the report ("2/18 lymph nodes", "one of two nodes") counts positive nodes in all or part of the dissection, so the total is at least its first number. An accepted count may not be below the largest of them (`count_below_report`). Fractions of negative nodes ("eight of eight sentinel lymph nodes, free of metastatic carcinoma") and grade scores ("Grade 2/3") are left out.

It is a floor only. We first tried an exact total (the fraction with the most nodes examined, or the sum over specimens): that rejected 2 of the 13 stored counts that a person would accept, because a positive node can be stated without a fraction ("two lymph nodes, one of which contains metastatic carcinoma"; "Total number with metastasis: 7" beside "6/9").

## Result (`python scripts/guard_floor_check.py`)

| Check | Before | After |
|---|---|---|
| The red-team answer (N=1 from specimen A, A0CV scan) | accepted | rejected, `count_below_report` |
| The 13 node counts stored in `derived_stage` | 13 accepted | 13 accepted |
| Tests | 185 pass | 189 pass (4 new: the attack, a negative sentinel 0/1 in a 2/10 report, a positive without a fraction, negative-node and grade fractions) |

The same floor against the registry's own counts (stage_check, 1,097 cases): 532 at or above the floor, 340 reports state no node fraction, 188 have no report or no count, 37 registry counts are below a fraction the report states. Not a result yet: a hand check of 5 of the 37 found 3 clear report–registry disagreements (e.g. "4 of 25 … lymph nodes are positive", registry 0), 1 isolated-tumour-cell case, and 1 false floor (the negative-node phrasing, since fixed).

## Second round: what is a count inside the quote (2026-10-23)

A second red-team review (Grok, reading the code) listed wrong counts the guard still accepted; we replayed each on synthetic text and all were accepted: a size ("Tumor size 14 mm" as 14), the examined count ("Total lymph nodes examined: 18"), a negative-node fraction ("Eight of eight … free of metastatic carcinoma" as 8), a grade score in the same quote as a node fraction ("Nottingham score 8/9" as 8), the wrong number word ("Two lymph nodes, one of which contains metastatic carcinoma" as 2), "No lymphovascular invasion" as zero, a stage code ("pN1a" as 1), a block name ("S14").

Fix (`count_in_span`): a fraction in the quote counts only if it is not a score and not followed by a negative word (then only zero is stated); without a fraction, the count must be the number nearest a positive cue that is not negated, never a number with a unit after it or "examined"/"size" before it; "no" means zero only before "node(s)", "lymph node(s)" or metastasis.

| Check | Result |
|---|---|
| The 14 replayed attacks and true counts beside them (`tests/test_reader.py::test_red_team_counts`) | every wrong count rejected, every true count accepted |
| The same fresh reads of all 25 queue reports (Super, NVIDIA direct, thinking off), judged by the previous and the current guard (`scripts/guard_ab.py`, `logs/guard-ab-2026-10-23.txt`) | 0 verdicts changed: the 15 accepted counts still pass |
| The 13 stored counts; the specimen attack | 13 accepted; still rejected |
| Tests | 216 pass |

## Third round: the N and T quote must show the category (2026-10-23)

A Fable review found that `judge_field` only checked that the quote exists in the report: on the hero case N3a with the quote "breast" was accepted, and through "Try to fool it" that reading would have named the N field. Fix (`supports_category`): the located quote must hold a stage token or label with the same main category ("pN1a", "pT2N1aMX", "N Stage: 1a"), or for N a node count the count guard reads in it that implies the category (2 positive -> N1), or for T a tumour size in its range (the largest of "4.1 x 3.5 x 1.5 cm"), or the words of a category a number cannot show (micrometastasis, isolated tumour cells, "cannot be assessed", "examined: 0", skin or chest wall, in situ).

| Check | Result |
|---|---|
| Attacks and true readings (`tests/test_reader.py::test_the_quote_must_show_the_category`) | N3a/"breast", T4d/a node sentence, N2a/"pT2N1aMX" rejected; true readings accepted |
| The 36 stored T/N rows | 35 still accepted; 1 now rejected: T1C quoting "Stage: 1c" (the form reads "Grade: 2. Stage: 1c N Stage: …", no T label in the quote; fail-closed) |
| Fresh reads of the 25 queue reports, judged by the previous and current guard (`logs/guard-ab-nt-2026-10-23.txt`) | 4 verdicts changed: 3 were model errors the old guard accepted (N1a quoting "4 of 13" and "4/8 positive", which are N2; T2 quoting "1.2 cm", which is T1), 1 the same "Stage: 1c" (fail-closed). A fifth, "1.2-CM", was our size pattern's fault and is fixed |

Known limit (N): a quote of one specimen ("(1/1)") supports N1 even when the total makes it N2, the same per-specimen limit as the count.

Known limits: a per-specimen count when no fraction states the total (the floor is the largest fraction, by design); a count above every stated fraction if it is the number nearest a positive cue; a node fraction more than 60 characters from the word "node" is not in the floor.
