# Zetaris demo: the `stage_audit` Unified Semantic Layer

Run 2026-10-23 01:36 UTC with `python -m app.cli usl demo --write` (live Zetaris). LOAD USL: 8 tables (0.53 s). Whole pack: 20.43 s wall-clock.

## What we built
`lightning.metastore.registry_audit.stage_audit`: one Unified Semantic Layer that joins a public registry API, file-store CSVs and our own append-only Postgres results, and names which registry field the verified evidence points to. Data-quality rules run inside Zetaris (`RUN DQ`).

## What data
- NCI GDC REST API, project TCGA-BRCA (open access): cases, recorded stage, node counts (`GDC_REST.brca_cases_raw`, cached).
- File store `REG_FILES`: paraphrased staging rules, pathology report text (TCGA-Reports, MIT) and Nemotron Parse blocks of the original scanned reports.
- Postgres `oa_pg`: the reader's quote-verified values and the review log (INSERT only, append-only).

## How the sources were onboarded (`usl setup` runs these files in order)

- Postgres (our append-only results): `app/usl/sql/002_postgres_derived_extraction.sql`, `app/usl/sql/003_postgres_flag_log.sql`, `app/usl/sql/004_register_derived_extraction.sql`, `app/usl/sql/005_register_flag_log.sql`
- File store REG_FILES (rules, report text, Parse blocks): `app/usl/sql/010_lightning_reg_files.sql`, `app/usl/sql/011_filestore_staging_rules.sql`, `app/usl/sql/012_filestore_path_reports.sql`, `app/usl/sql/015_filestore_parse_blocks.sql`
- NCI GDC REST API (cases, recorded stage, node counts): `app/usl/sql/020_lightning_gdc.sql`, `app/usl/sql/021_rest_brca_cases.sql`, `app/usl/sql/022_cache_brca_cases.sql`

## How to run it (the SQL in order, with output)

### 1. Row count of every USL table (3.98 s)
Why: the layer is live over all three source types.
```sql
SELECT 'tumour_case' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.tumour_case UNION ALL SELECT 'path_report' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.path_report UNION ALL SELECT 'recorded_stage' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.recorded_stage UNION ALL SELECT 'staging_rule' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.staging_rule UNION ALL SELECT 'derived_stage' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.derived_stage UNION ALL SELECT 'stage_check' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.stage_check UNION ALL SELECT 'parse_block' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.parse_block UNION ALL SELECT 'flag' AS usl_table, count(*) AS rows FROM lightning.metastore.registry_audit.stage_audit.flag
```
Output:

| usl_table | rows |
|---|---|
| tumour_case | 1097 |
| path_report | 1034 |
| recorded_stage | 1097 |
| staging_rule | 59 |
| derived_stage | 902 |
| stage_check | 1097 |
| parse_block | 532 |
| flag | 16 |


### 2. Every rule registered on the layer (0.44 s)
Why: our custom rules and the key rules Zetaris generated from the DDL.
```sql
LIST DQ USL lightning.metastore.registry_audit.stage_audit
```
Output:

| name | table | type | expression |
|---|---|---|---|
| case_id | recorded_stage | Primary key constraints |  |
| case_id | recorded_stage | Foreign key constraints |  |
| nodes_within_tested | recorded_stage | Custom Data Quality | lymph_nodes_positive IS NULL OR lymph_nodes_tested IS NULL
O |
| rule_id | staging_rule | Primary key constraints |  |
| case_id,method,field | derived_stage | Primary key constraints |  |
| case_id | derived_stage | Foreign key constraints |  |
| case_id | stage_check | Primary key constraints |  |
| nodes_consistent | stage_check | Custom Data Quality | NOT (
  edition_code IN ('6', '7')
  AND lymph_nodes_positiv |
| stage_derivable_but_missing | stage_check | Custom Data Quality | NOT (
  edition_code IN ('6', '7')
  AND lymph_nodes_positiv |
| report_agrees | stage_check | Custom Data Quality | (report_t IS NULL OR recorded_t IS NULL OR regexp_extract(up |
| edition_supported | stage_check | Custom Data Quality | edition_code IN ('6', '7', '8') |
| edition_matches_year | stage_check | Custom Data Quality | edition_year_class <> 'out_of_window' |
| fault_named | stage_check | Custom Data Quality | fault_field IS NULL OR fault_field NOT IN ('node_count', 'pa |
| fault_unresolved | stage_check | Custom Data Quality | fault_field IS NULL OR fault_field <> 'review' |
| flag_id | flag | Primary key constraints |  |
| case_id | flag | Foreign key constraints |  |
| case_id | tumour_case | Primary key constraints |  |
| report_id | path_report | Primary key constraints |  |
| case_id | path_report | Foreign key constraints |  |
| case_id,page_no,block_index | parse_block | Primary key constraints |  |
| case_id | parse_block | Foreign key constraints |  |


### 3. A plain question to the layer (2.36 s)
Why: how many records in each edition cannot be true as written, and which field the evidence names.
```sql
SELECT edition_code, fault_field, count(*) AS cases FROM lightning.metastore.registry_audit.stage_audit.stage_check WHERE reason_class IN ('n_count_contradiction', 'n_missing_derivable') GROUP BY edition_code, fault_field ORDER BY edition_code, fault_field
```
Output:

| edition_code | fault_field | cases |
|---|---|---|
| 6 | node_count | 4 |
| 6 | pathologic_n | 5 |
| 6 | review | 3 |
| 7 | node_count | 4 |
| 7 | pathologic_n | 8 |
| 7 | review | 1 |


### 4. The cross-source verdict (2.37 s)
Why: one USL table joins the REST registry record, the file-store rules and the Postgres reader output, and names the field the evidence points to.
```sql
SELECT case_id, recorded_n, lymph_nodes_positive, derived_n, report_n, report_nodes_positive, fault_field FROM lightning.metastore.registry_audit.stage_audit.stage_check WHERE fault_field IS NOT NULL ORDER BY fault_field, case_id
```
Output (first 5 of 25):

| case_id | recorded_n | lymph_nodes_positive | derived_n | report_n | report_nodes_positive | fault_field |
|---|---|---|---|---|---|---|
| TCGA-A2-A0CV | N1A | 4.0 | pN2a | N1A | 2 | node_count |
| TCGA-A7-A26E | N1A | 0.0 | pN0 | N1A | 1 | node_count |
| TCGA-A7-A26H | N1A | 0.0 | pN0 | N1A | 1 | node_count |
| TCGA-AO-A1KP | N1 | 0.0 | pN0 | N1A | 1 | node_count |
| TCGA-AQ-A1H2 | N2A | 13.0 | pN3a | N2A | 7 | node_count |


### 5. The basic data-quality rule (source level) (0.99 s)
Why: positive nodes cannot exceed the nodes examined, checked on the recorded values.
```sql
RUN DQ nodes_within_tested TABLE lightning.metastore.registry_audit.stage_audit.recorded_stage
```
Output:

| name | table | type | total_record | valid_record | invalid_record |
|---|---|---|---|---|---|
| nodes_within_tested | recorded_stage | Custom Data Quality | 1097 | 1097 | 0 |


### 6. The contradiction rule (3.96 s)
Why: records whose recorded N and node count cannot both be true.
```sql
RUN DQ nodes_consistent TABLE lightning.metastore.registry_audit.stage_audit.stage_check
```
Output:

| name | table | type | total_record | valid_record | invalid_record |
|---|---|---|---|---|---|
| nodes_consistent | stage_check | Custom Data Quality | 1097 | 1073 | 24 |


### 7. The records the contradiction rule flags (2.47 s)
Why: the review queue, straight from the rule.
```sql
SHOW DQ INVALID RECORD nodes_consistent TABLE lightning.metastore.registry_audit.stage_audit.stage_check
```
Output (first 5 of 24):

| case_id | site_key | edition_code | recorded_t | recorded_n | recorded_stage | recorded_n_main | lymph_nodes_positive | lymph_nodes_tested | derived_n | derived_n_main | report_t | report_n | year_of_diagnosis | edition_year_class | reason_class | report_n_main | report_nodes_positive | fault_field |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TCGA-A7-A26E | breast | 7 | T3 | N1A | Stage IIIA | N1 | 0.0 | 16.0 | pN0 | N0 | T3 | N1A | 2010 | in_window | n_count_contradiction | N1 | 1 | node_count |
| TCGA-D8-A27L | breast | 7 | T1C | N2A | Stage IIIA | N2 | 2.0 | 16.0 | pN1a | N1 | T1C | NX | 2011 | in_window | n_count_contradiction | NX | None | review |
| TCGA-A2-A0CV | breast | 6 | T2 | N1A | Stage IIB | N1 | 4.0 | 18.0 | pN2a | N2 | T2 | N1A | 2005 | in_window | n_count_contradiction | N1 | 2 | node_count |
| TCGA-EW-A424 | breast | 7 | T3 | N1 | Stage IIIA | N1 | 0.0 | 1.0 | pN0 | N0 | T3 | N0 | 2012 | in_window | n_count_contradiction | N0 | 0 | pathologic_n |
| TCGA-A2-A0EW | breast | 6 | T1B | N3A | Stage IIIC | N3 | 26.0 | None | pNX | NX | T1C | N2A | 2008 | in_window | n_count_contradiction | N2 | 4 | review |


### 8. A key rule Zetaris generated from the DDL (1.1 s)
Why: every scanned-report block belongs to a known case.
```sql
RUN DQ case_id TABLE lightning.metastore.registry_audit.stage_audit.parse_block
```
Output:

| name | table | type | total_record | valid_record | invalid_record |
|---|---|---|---|---|---|
| case_id | parse_block | Primary Key Constraint | 532 | 532 | 0 |
| case_id | parse_block | Foreign Key Constraint | 532 | 532 | 0 |


### 9. The composite keys hold (no output rows means no duplicates) (1.7 s)
Why: Zetaris runs a composite-key rule only through its first column, so we check the full keys of derived_stage (case_id, method, field) and parse_block (case_id, page_no, block_index) directly.
```sql
SELECT 'derived_stage' AS usl_table, case_id, count(*) AS n FROM lightning.metastore.registry_audit.stage_audit.derived_stage GROUP BY case_id, method, field HAVING count(*) > 1 UNION ALL SELECT 'parse_block' AS usl_table, case_id, count(*) AS n FROM lightning.metastore.registry_audit.stage_audit.parse_block GROUP BY case_id, page_no, block_index HAVING count(*) > 1
```
Output:

| usl_table | case_id | n |
|---|---|---|


### 10. Evidence on the original scan (0.54 s)
Why: the block Nemotron Parse read, with its box, for the hero case.
```sql
SELECT case_id, page_no, block_text, xmin, ymin, xmax, ymax FROM lightning.metastore.registry_audit.stage_audit.parse_block WHERE case_id = 'TCGA-A2-A0CV' AND block_text LIKE '%2/18%'
```
Output:

| case_id | page_no | block_text | xmin | ymin | xmax | ymax |
|---|---|---|---|---|---|---|
| TCGA-A2-A0CV | 0 | LYMPH NODES: METASTASIS IN TWO OF EIGHTEEN (2/18) EXAMINED L | 0.133867 | 0.631200 | 0.864684 | 0.680000 |


## What was checked
Every number above came from this run; a failed step would be shown, not skipped.

## Cleanup
`python -m app.cli usl teardown --yes` removes the namespace, the two Lightning databases and our two Postgres tables (and nothing else).
