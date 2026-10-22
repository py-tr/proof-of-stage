REGISTER DQ report_agrees TABLE lightning.metastore.registry_audit.stage_audit.stage_check AS
(report_t IS NULL OR recorded_t = report_t) AND (report_n IS NULL OR recorded_n = report_n)
