CREATE TABLE IF NOT EXISTS attest_receipt (
  receipt_id TEXT NOT NULL PRIMARY KEY,
  item_id TEXT,
  served_model TEXT,
  route_kind TEXT,
  signer_fingerprint TEXT,
  signature_state TEXT,
  cache_status TEXT,
  prompt_chars INTEGER,
  messages_sha256 TEXT,
  answer_sha256 TEXT,
  envelope_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attestation (
  attest_id TEXT NOT NULL PRIMARY KEY,
  run TEXT NOT NULL,
  case_id TEXT NOT NULL,
  field TEXT NOT NULL,
  stored_value TEXT,
  stored_quote TEXT,
  stored_quote_rechecked TEXT,
  signed_value TEXT,
  signed_quote TEXT,
  outcome TEXT NOT NULL,
  receipt_id TEXT,
  created_at TEXT NOT NULL
);
