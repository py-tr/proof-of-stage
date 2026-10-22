ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.staging_rule AS
SELECT
  COALESCE(CAST(rule_id AS STRING), '') AS rule_id,
  CAST(site AS STRING) AS site,
  CAST(element AS STRING) AS element,
  CAST(edition AS STRING) AS edition,
  CAST(condition_text AS STRING) AS condition_text,
  CAST(min_value AS STRING) AS min_value,
  CAST(max_value AS STRING) AS max_value,
  CAST(output AS STRING) AS output,
  CAST(cite AS STRING) AS cite
FROM REG_FILES.staging_rules
