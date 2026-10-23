REGISTER DQ edition_supported TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
coalesce(edition_code, '') IN ('6', '7', '8')
