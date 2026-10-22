ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
SELECT
  scored.case_id AS case_id,
  scored.site_key AS site_key,
  scored.edition_code AS edition_code,
  scored.recorded_t AS recorded_t,
  scored.recorded_n AS recorded_n,
  scored.recorded_stage AS recorded_stage,
  scored.recorded_n_main AS recorded_n_main,
  scored.lymph_nodes_positive AS lymph_nodes_positive,
  scored.lymph_nodes_tested AS lymph_nodes_tested,
  scored.derived_n AS derived_n,
  scored.derived_n_main AS derived_n_main,
  scored.report_t AS report_t,
  scored.report_n AS report_n,
  scored.year_of_diagnosis AS year_of_diagnosis,
  CASE
    WHEN scored.edition_code IS NULL OR trim(scored.edition_code) = ''
      OR scored.year_of_diagnosis IS NULL OR trim(scored.year_of_diagnosis) = '' THEN 'unknown'
    WHEN scored.edition_code = '5' AND CAST(scored.year_of_diagnosis AS INT) BETWEEN 1997 AND 2003 THEN 'in_window'
    WHEN scored.edition_code = '6' AND CAST(scored.year_of_diagnosis AS INT) BETWEEN 2002 AND 2010 THEN 'in_window'
    WHEN scored.edition_code = '7' AND CAST(scored.year_of_diagnosis AS INT) BETWEEN 2009 AND 2018 THEN 'in_window'
    WHEN scored.edition_code = '8' AND CAST(scored.year_of_diagnosis AS INT) >= 2017 THEN 'in_window'
    WHEN scored.edition_code IN ('5', '6', '7', '8') THEN 'out_of_window'
    ELSE 'unknown'
  END AS edition_year_class,
  CASE
    WHEN scored.lymph_nodes_positive IS NULL OR trim(scored.lymph_nodes_positive) = '' THEN 'count_missing'
    WHEN scored.edition_code IN ('6', '7')
     AND (scored.recorded_n_main IS NULL OR scored.recorded_n_main = 'NX') THEN 'n_missing_derivable'
    WHEN scored.edition_code IN ('6', '7')
     AND upper(regexp_replace(coalesce(scored.recorded_n, ''), ' ', '')) IN ('N1MI', 'N0(I+)', 'N0(MOL+)') THEN 'n_ambiguous_micromet'
    WHEN scored.edition_code IN ('6', '7')
     AND scored.recorded_n_main IS NOT NULL
     AND scored.recorded_n_main <> 'NX'
     AND scored.derived_n_main IS NOT NULL
     AND scored.recorded_n_main <> scored.derived_n_main THEN 'n_count_contradiction'
    ELSE 'consistent'
  END AS reason_class
FROM (
SELECT
  COALESCE(rec.case_id, '') AS case_id,
  rec.site_key AS site_key,
  rec.edition_code AS edition_code,
  rec.pathologic_t AS recorded_t,
  rec.pathologic_n AS recorded_n,
  rec.pathologic_stage AS recorded_stage,
  rec.n_main AS recorded_n_main,
  rec.lymph_nodes_positive AS lymph_nodes_positive,
  rec.lymph_nodes_tested AS lymph_nodes_tested,
  sql_n.value AS derived_n,
  CASE
    WHEN sql_n.value IS NULL OR trim(sql_n.value) = '' THEN NULL
    WHEN regexp_extract(upper(trim(sql_n.value)), 'N[0-9X]', 0) = '' THEN NULL
    ELSE regexp_extract(upper(trim(sql_n.value)), 'N[0-9X]', 0)
  END AS derived_n_main,
  rep_t.value AS report_t,
  rep_n.value AS report_n,
  tc.year_of_diagnosis AS year_of_diagnosis
FROM lightning.metastore.registry_audit.stage_audit.recorded_stage rec
LEFT JOIN lightning.metastore.registry_audit.stage_audit.tumour_case tc
  ON tc.case_id = rec.case_id
LEFT JOIN lightning.metastore.registry_audit.stage_audit.derived_stage sql_n
  ON sql_n.case_id = rec.case_id
 AND sql_n.method = 'sql_node_count'
 AND sql_n.field = 'N'
LEFT JOIN (
  SELECT
    case_id,
    MAX(
      CASE
        WHEN value IS NULL OR trim(value) = '' THEN NULL
        WHEN upper(trim(value)) LIKE 'YPT%' THEN substring(upper(trim(value)), 3)
        WHEN upper(trim(value)) LIKE 'YPN%' THEN substring(upper(trim(value)), 3)
        WHEN upper(trim(value)) LIKE 'PT%' THEN substring(upper(trim(value)), 2)
        WHEN upper(trim(value)) LIKE 'PN%' THEN substring(upper(trim(value)), 2)
        ELSE upper(trim(value))
      END
    ) AS value
  FROM lightning.metastore.registry_audit.stage_audit.derived_stage
  WHERE method <> 'sql_node_count' AND field = 'T'
  GROUP BY case_id
) rep_t
  ON rep_t.case_id = rec.case_id
LEFT JOIN (
  SELECT
    case_id,
    MAX(
      CASE
        WHEN value IS NULL OR trim(value) = '' THEN NULL
        WHEN upper(trim(value)) LIKE 'YPT%' THEN substring(upper(trim(value)), 3)
        WHEN upper(trim(value)) LIKE 'YPN%' THEN substring(upper(trim(value)), 3)
        WHEN upper(trim(value)) LIKE 'PT%' THEN substring(upper(trim(value)), 2)
        WHEN upper(trim(value)) LIKE 'PN%' THEN substring(upper(trim(value)), 2)
        ELSE upper(trim(value))
      END
    ) AS value
  FROM lightning.metastore.registry_audit.stage_audit.derived_stage
  WHERE method <> 'sql_node_count' AND field = 'N'
  GROUP BY case_id
) rep_n
  ON rep_n.case_id = rec.case_id
) scored
