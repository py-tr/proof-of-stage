CREATE LIGHTNING FILESTORE TABLE path_reports FROM REG_FILES FORMAT CSV OPTIONS (
  path "dffs://stage_audit/path_reports.csv",
  storage "dffs",
  header "true",
  multiLine "true",
  escape "\""
)
