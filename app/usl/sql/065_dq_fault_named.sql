REGISTER DQ fault_named TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
fault_field IS NULL OR fault_field NOT IN ('node_count', 'pathologic_n')
