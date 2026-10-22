COMPILE USL stage_audit DEPLOY NAMESPACE lightning.metastore.registry_audit DDL
CREATE TABLE tumour_case (
  case_id varchar(64) NOT NULL PRIMARY KEY,
  primary_site varchar(128),
  site_key varchar(32),
  year_of_diagnosis varchar(16)
);
CREATE TABLE path_report (
  report_id varchar(64) NOT NULL PRIMARY KEY,
  case_id varchar(64) NOT NULL,
  report_text varchar(60000),
  FOREIGN KEY (case_id) REFERENCES tumour_case(case_id)
);
CREATE TABLE recorded_stage (
  case_id varchar(64) NOT NULL PRIMARY KEY,
  site_key varchar(32),
  pathologic_t varchar(64),
  pathologic_n varchar(64),
  pathologic_stage varchar(64),
  edition varchar(32),
  edition_code varchar(8),
  lymph_nodes_positive varchar(32),
  lymph_nodes_tested varchar(32),
  year_of_diagnosis varchar(16),
  n_main varchar(8),
  FOREIGN KEY (case_id) REFERENCES tumour_case(case_id)
);
CREATE TABLE staging_rule (
  rule_id varchar(32) NOT NULL PRIMARY KEY,
  site varchar(32),
  element varchar(8),
  edition varchar(32),
  condition_text varchar(800),
  min_value varchar(32),
  max_value varchar(32),
  output varchar(64),
  cite varchar(200)
);
CREATE TABLE derived_stage (
  case_id varchar(64) NOT NULL,
  method varchar(64) NOT NULL,
  field varchar(32) NOT NULL,
  value varchar(256),
  quote varchar(8000),
  quote_start int,
  quote_end int,
  model varchar(256),
  receipt_id varchar(256),
  created_at varchar(40),
  PRIMARY KEY (case_id, method, field),
  FOREIGN KEY (case_id) REFERENCES tumour_case(case_id)
);
CREATE TABLE stage_check (
  case_id varchar(64) NOT NULL PRIMARY KEY,
  site_key varchar(32),
  edition_code varchar(8),
  recorded_t varchar(64),
  recorded_n varchar(64),
  recorded_stage varchar(64),
  recorded_n_main varchar(8),
  lymph_nodes_positive varchar(32),
  lymph_nodes_tested varchar(32),
  derived_n varchar(64),
  derived_n_main varchar(8),
  report_t varchar(64),
  report_n varchar(64),
  year_of_diagnosis varchar(8),
  edition_year_class varchar(16),
  reason_class varchar(32)
);
CREATE TABLE flag (
  flag_id varchar(64) NOT NULL PRIMARY KEY,
  case_id varchar(64) NOT NULL,
  rule_id varchar(64),
  field varchar(32),
  recorded_value varchar(256),
  derived_value varchar(256),
  quote varchar(8000),
  reason varchar(2000),
  severity varchar(32),
  model varchar(256),
  receipt_id varchar(256),
  created_at varchar(40),
  FOREIGN KEY (case_id) REFERENCES tumour_case(case_id)
)
