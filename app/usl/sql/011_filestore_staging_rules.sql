CREATE LIGHTNING FILESTORE TABLE staging_rules FROM REG_FILES FORMAT CSV OPTIONS (
  path "dffs://stage_audit/staging_rules.csv",
  storage "dffs",
  header "true",
  multiLine "true",
  escape "\""
)
