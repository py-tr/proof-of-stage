ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.parse_block AS
SELECT
  COALESCE(CAST(case_id AS STRING), '') AS case_id,
  COALESCE(CAST(page_no AS INT), 0) AS page_no,
  COALESCE(CAST(block_index AS INT), 0) AS block_index,
  CAST(block_text AS STRING) AS block_text,
  CAST(block_kind AS STRING) AS block_kind,
  CAST(xmin AS DECIMAL(9,6)) AS xmin,
  CAST(ymin AS DECIMAL(9,6)) AS ymin,
  CAST(xmax AS DECIMAL(9,6)) AS xmax,
  CAST(ymax AS DECIMAL(9,6)) AS ymax,
  CAST(model AS STRING) AS model,
  CAST(gdc_file_id AS STRING) AS gdc_file_id
FROM REG_FILES.parse_blocks
