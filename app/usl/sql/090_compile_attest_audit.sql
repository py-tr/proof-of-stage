COMPILE USL attest_audit DEPLOY NAMESPACE lightning.metastore.registry_audit DDL
CREATE TABLE receipt (
  receipt_id varchar(64) NOT NULL PRIMARY KEY,
  item_id varchar(256),
  served_model varchar(256),
  route_kind varchar(32),
  signer_fingerprint varchar(32),
  signature_state varchar(32),
  cache_status varchar(32),
  created_at varchar(40)
);
CREATE TABLE attestation (
  attest_id varchar(128) NOT NULL PRIMARY KEY,
  run_tag varchar(32),
  case_id varchar(64),
  field varchar(16),
  stored_value varchar(64),
  signed_value varchar(64),
  outcome varchar(32),
  receipt_id varchar(64),
  receipt_signature_state varchar(32),
  receipt_signer_fingerprint varchar(32),
  created_at varchar(40)
)
