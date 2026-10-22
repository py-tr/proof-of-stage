ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.recorded_stage AS
SELECT
  COALESCE(ranked.case_id, '') AS case_id,
  ranked.site_key AS site_key,
  ranked.pathologic_t AS pathologic_t,
  ranked.pathologic_n AS pathologic_n,
  ranked.pathologic_stage AS pathologic_stage,
  ranked.edition AS edition,
  ranked.edition_code AS edition_code,
  nodes.lymph_nodes_positive AS lymph_nodes_positive,
  nodes.lymph_nodes_tested AS lymph_nodes_tested,
  ranked.year_of_diagnosis AS year_of_diagnosis,
  CASE
    WHEN ranked.pathologic_n IS NULL OR regexp_extract(ranked.pathologic_n, 'N[0-9X]', 0) = '' THEN NULL
    ELSE regexp_extract(ranked.pathologic_n, 'N[0-9X]', 0)
  END AS n_main
FROM (
  SELECT
    case_id,
    site_key,
    pathologic_t,
    pathologic_n,
    pathologic_stage,
    edition,
    edition_code,
    year_of_diagnosis,
    ROW_NUMBER() OVER (
      PARTITION BY case_id
      ORDER BY
        CASE WHEN pathologic_t IS NULL THEN 1 ELSE 0 END,
        CASE WHEN pathologic_n IS NULL THEN 1 ELSE 0 END,
        CASE WHEN edition_code IS NULL THEN 1 ELSE 0 END,
        year_of_diagnosis DESC
    ) AS rn
  FROM (
    SELECT
      COALESCE(CAST(hit.submitter_id AS STRING), '') AS case_id,
      CASE
        WHEN lower(CAST(hit.primary_site AS STRING)) LIKE '%breast%' THEN 'breast'
        WHEN lower(CAST(hit.primary_site AS STRING)) LIKE '%colon%'
          OR lower(CAST(hit.primary_site AS STRING)) LIKE '%rectum%'
          OR lower(CAST(hit.primary_site AS STRING)) LIKE '%colorectal%' THEN 'colon'
        ELSE lower(CAST(hit.primary_site AS STRING))
      END AS site_key,
      CASE
        WHEN diagnosis.ajcc_pathologic_t IS NULL
          OR trim(CAST(diagnosis.ajcc_pathologic_t AS STRING)) = '' THEN NULL
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))) LIKE 'YPT%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))), 3)
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))) LIKE 'YPN%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))), 3)
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))) LIKE 'PT%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))), 2)
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))) LIKE 'PN%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING))), 2)
        ELSE upper(trim(CAST(diagnosis.ajcc_pathologic_t AS STRING)))
      END AS pathologic_t,
      CASE
        WHEN diagnosis.ajcc_pathologic_n IS NULL
          OR trim(CAST(diagnosis.ajcc_pathologic_n AS STRING)) = '' THEN NULL
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))) LIKE 'YPT%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))), 3)
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))) LIKE 'YPN%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))), 3)
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))) LIKE 'PT%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))), 2)
        WHEN upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))) LIKE 'PN%'
          THEN substring(upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING))), 2)
        ELSE upper(trim(CAST(diagnosis.ajcc_pathologic_n AS STRING)))
      END AS pathologic_n,
      CAST(diagnosis.ajcc_pathologic_stage AS STRING) AS pathologic_stage,
      CAST(diagnosis.ajcc_staging_system_edition AS STRING) AS edition,
      CASE
        WHEN upper(CAST(diagnosis.ajcc_staging_system_edition AS STRING)) LIKE '%8%' THEN '8'
        WHEN upper(CAST(diagnosis.ajcc_staging_system_edition AS STRING)) LIKE '%7%' THEN '7'
        WHEN upper(CAST(diagnosis.ajcc_staging_system_edition AS STRING)) LIKE '%6%' THEN '6'
        WHEN upper(CAST(diagnosis.ajcc_staging_system_edition AS STRING)) LIKE '%5%' THEN '5'
        ELSE NULL
      END AS edition_code,
      CAST(diagnosis.year_of_diagnosis AS STRING) AS year_of_diagnosis
    FROM GDC_REST.brca_cases_raw
    LATERAL VIEW explode(data.hits) AS hit
    LATERAL VIEW explode(hit.diagnoses) AS diagnosis
  ) diagnoses
) ranked
LEFT JOIN (
  SELECT
    COALESCE(CAST(hit.submitter_id AS STRING), '') AS case_id,
    CAST(MAX(CAST(pd.lymph_nodes_positive AS DOUBLE)) AS STRING) AS lymph_nodes_positive,
    CAST(MAX(CAST(pd.lymph_nodes_tested AS DOUBLE)) AS STRING) AS lymph_nodes_tested
  FROM GDC_REST.brca_cases_raw
  LATERAL VIEW explode(data.hits) AS hit
  LATERAL VIEW explode(hit.diagnoses) AS diagnosis
  LATERAL VIEW OUTER explode(diagnosis.pathology_details) AS pd
  GROUP BY COALESCE(CAST(hit.submitter_id AS STRING), '')
) nodes
  ON nodes.case_id = ranked.case_id
WHERE ranked.rn = 1
