ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.flag AS
SELECT
  COALESCE(CAST(flag_id AS STRING), '') AS flag_id,
  COALESCE(CAST(case_id AS STRING), '') AS case_id,
  CAST(rule_id AS STRING) AS rule_id,
  CAST(field AS STRING) AS field,
  CAST(recorded_value AS STRING) AS recorded_value,
  CAST(derived_value AS STRING) AS derived_value,
  CAST(quote AS STRING) AS quote,
  CAST(reason AS STRING) AS reason,
  CAST(severity AS STRING) AS severity,
  CAST(model AS STRING) AS model,
  CAST(receipt_id AS STRING) AS receipt_id,
  CAST(created_at AS STRING) AS created_at
FROM oa_pg.flag_log
