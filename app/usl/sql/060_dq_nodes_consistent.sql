REGISTER DQ nodes_consistent TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
NOT (
  edition_code IN ('6', '7')
  AND lymph_nodes_positive IS NOT NULL
  AND trim(lymph_nodes_positive) <> ''
  AND recorded_n_main IS NOT NULL
  AND recorded_n_main <> 'NX'
  AND upper(regexp_replace(coalesce(recorded_n, ''), ' ', '')) NOT IN ('N1MI', 'N0(I+)', 'N0(MOL+)')
  AND derived_n_main IS NOT NULL
  AND recorded_n_main <> derived_n_main
)
