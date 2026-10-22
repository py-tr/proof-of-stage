ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.derived_stage AS
SELECT
  COALESCE(counted.case_id, '') AS case_id,
  'sql_node_count' AS method,
  'N' AS field,
  counted.value AS value,
  CAST(NULL AS STRING) AS quote,
  CAST(NULL AS INT) AS quote_start,
  CAST(NULL AS INT) AS quote_end,
  CAST(NULL AS STRING) AS model,
  CAST(NULL AS STRING) AS receipt_id,
  CAST(NULL AS STRING) AS created_at
FROM (
  SELECT case_id, MIN(output) AS value
  FROM (
    SELECT rec.case_id AS case_id, rule.output AS output
    FROM lightning.metastore.registry_audit.stage_audit.recorded_stage rec
    JOIN lightning.metastore.registry_audit.stage_audit.staging_rule rule
      ON rule.site = rec.site_key
     AND rule.element = 'N'
     AND rule.min_value IS NOT NULL
     AND trim(rule.min_value) <> ''
     AND rule.output IS NOT NULL
     AND trim(rule.output) <> ''
     AND rule.output NOT IN ('UNRESOLVED', 'flag', 'suffix/prefix', 'not staged')
     AND rec.lymph_nodes_positive IS NOT NULL
     AND trim(rec.lymph_nodes_positive) <> ''
     AND rec.lymph_nodes_tested IS NOT NULL
     AND trim(rec.lymph_nodes_tested) <> ''
     AND CAST(rec.lymph_nodes_tested AS DOUBLE) > 0
     AND CAST(rec.lymph_nodes_positive AS DOUBLE) >= CAST(rule.min_value AS DOUBLE)
     AND (
       rule.max_value IS NULL
       OR trim(rule.max_value) = ''
       OR CAST(rec.lymph_nodes_positive AS DOUBLE) <= CAST(rule.max_value AS DOUBLE)
     )
     AND rec.edition_code IS NOT NULL
     AND instr(concat(',', rule.edition, ','), concat(',', rec.edition_code, ',')) > 0
    UNION ALL
    SELECT rec.case_id AS case_id, rule.output AS output
    FROM lightning.metastore.registry_audit.stage_audit.recorded_stage rec
    JOIN lightning.metastore.registry_audit.stage_audit.staging_rule rule
      ON rule.rule_id IN ('BN1', 'CN1')
     AND rule.site = rec.site_key
     AND rec.edition_code IS NOT NULL
     AND instr(concat(',', rule.edition, ','), concat(',', rec.edition_code, ',')) > 0
     AND (
       rec.lymph_nodes_tested IS NULL
       OR trim(rec.lymph_nodes_tested) = ''
       OR CAST(rec.lymph_nodes_tested AS DOUBLE) = 0
     )
  ) matched
  GROUP BY case_id
) counted
UNION ALL
SELECT
  COALESCE(CAST(case_id AS STRING), '') AS case_id,
  COALESCE(CAST(method AS STRING), '') AS method,
  COALESCE(CAST(field AS STRING), '') AS field,
  CAST(value AS STRING) AS value,
  CAST(quote AS STRING) AS quote,
  CAST(quote_start AS INT) AS quote_start,
  CAST(quote_end AS INT) AS quote_end,
  CAST(model AS STRING) AS model,
  CAST(receipt_id AS STRING) AS receipt_id,
  CAST(created_at AS STRING) AS created_at
FROM oa_pg.derived_extraction
WHERE COALESCE(CAST(method AS STRING), '') <> 'sql_node_count'
