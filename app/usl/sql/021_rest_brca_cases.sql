CREATE LIGHTNING REST TABLE brca_cases_raw FROM GDC_REST REQUEST(
  endpoint "https://api.gdc.cancer.gov/cases?filters=%7B%22op%22%3A%22in%22%2C%22content%22%3A%7B%22field%22%3A%22project.project_id%22%2C%22value%22%3A%5B%22TCGA-BRCA%22%5D%7D%7D&fields=submitter_id%2Cprimary_site%2Cdiagnoses.ajcc_pathologic_t%2Cdiagnoses.ajcc_pathologic_n%2Cdiagnoses.ajcc_pathologic_stage%2Cdiagnoses.ajcc_staging_system_edition%2Cdiagnoses.pathology_details.lymph_nodes_positive%2Cdiagnoses.pathology_details.lymph_nodes_tested%2Cdiagnoses.year_of_diagnosis&size=2000&format=JSON",
  method "get",
  response_type "json",
  http_encoding "URLENCODED"
) HEADER (
) BODY ()
