CREATE TABLE IF NOT EXISTS derived_extraction (
  case_id TEXT NOT NULL,
  method TEXT NOT NULL,
  field TEXT NOT NULL,
  value TEXT,
  quote TEXT,
  quote_start INTEGER,
  quote_end INTEGER,
  model TEXT,
  receipt_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (case_id, method, field)
);
