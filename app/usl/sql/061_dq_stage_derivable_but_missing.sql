REGISTER DQ stage_derivable_but_missing TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
NOT (
  edition_code IN ('6', '7')
  AND lymph_nodes_positive IS NOT NULL
  AND trim(lymph_nodes_positive) <> ''
  AND (recorded_n_main IS NULL OR recorded_n_main = 'NX')
)
