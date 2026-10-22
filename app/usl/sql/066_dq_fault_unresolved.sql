REGISTER DQ fault_unresolved TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
fault_field IS NULL OR fault_field <> 'review'
