REGISTER DQ nodes_within_tested TABLE lightning.metastore.registry_audit.stage_audit.recorded_stage AS
lymph_nodes_positive IS NULL OR lymph_nodes_tested IS NULL
OR trim(lymph_nodes_positive) = '' OR trim(lymph_nodes_tested) = ''
OR CAST(lymph_nodes_positive AS DOUBLE) <= CAST(lymph_nodes_tested AS DOUBLE)
