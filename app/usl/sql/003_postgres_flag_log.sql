CREATE TABLE IF NOT EXISTS flag_log (
  flag_id TEXT NOT NULL PRIMARY KEY,
  case_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  field TEXT,
  recorded_value TEXT,
  derived_value TEXT,
  quote TEXT,
  reason TEXT,
  severity TEXT,
  model TEXT,
  receipt_id TEXT,
  created_at TEXT NOT NULL
);
