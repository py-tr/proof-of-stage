ACTIVATE USL TABLE lightning.metastore.registry_audit.stage_audit.tumour_case AS
SELECT
  COALESCE(case_id, '') AS case_id,
  MAX(primary_site) AS primary_site,
  MAX(site_key) AS site_key,
  MAX(year_of_diagnosis) AS year_of_diagnosis
FROM (
  SELECT
    COALESCE(CAST(hit.submitter_id AS STRING), '') AS case_id,
    CAST(hit.primary_site AS STRING) AS primary_site,
    CASE
      WHEN lower(CAST(hit.primary_site AS STRING)) LIKE '%breast%' THEN 'breast'
      WHEN lower(CAST(hit.primary_site AS STRING)) LIKE '%colon%'
        OR lower(CAST(hit.primary_site AS STRING)) LIKE '%rectum%'
        OR lower(CAST(hit.primary_site AS STRING)) LIKE '%colorectal%' THEN 'colon'
      ELSE lower(CAST(hit.primary_site AS STRING))
    END AS site_key,
    CAST(diagnosis.year_of_diagnosis AS STRING) AS year_of_diagnosis
  FROM GDC_REST.brca_cases_raw
  LATERAL VIEW explode(data.hits) AS hit
  LATERAL VIEW explode(hit.diagnoses) AS diagnosis
) flat
GROUP BY case_id
