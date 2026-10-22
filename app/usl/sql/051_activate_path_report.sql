ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.path_report AS
SELECT
  COALESCE(CAST(report_id AS STRING), '') AS report_id,
  COALESCE(CAST(case_id AS STRING), '') AS case_id,
  CAST(report_text AS STRING) AS report_text
FROM REG_FILES.path_reports
