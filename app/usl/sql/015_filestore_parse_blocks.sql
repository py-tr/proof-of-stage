CREATE LIGHTNING FILESTORE TABLE parse_blocks FROM REG_FILES FORMAT CSV OPTIONS (
  path "dffs://stage_audit/parse_blocks.csv",
  storage "dffs",
  header "true",
  multiLine "true",
  escape "\""
)
