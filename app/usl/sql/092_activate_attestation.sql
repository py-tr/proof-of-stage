ACTIVATE USL TABLE lightning.metastore.registry_audit.attest_audit.attestation AS
SELECT
  COALESCE(CAST(a.attest_id AS STRING), '') AS attest_id,
  CAST(a.run AS STRING) AS run_tag,
  CAST(a.case_id AS STRING) AS case_id,
  CAST(a.field AS STRING) AS field,
  CAST(a.stored_value AS STRING) AS stored_value,
  CAST(a.signed_value AS STRING) AS signed_value,
  CAST(a.outcome AS STRING) AS outcome,
  CAST(a.receipt_id AS STRING) AS receipt_id,
  CAST(r.signature_state AS STRING) AS receipt_signature_state,
  CAST(r.signer_fingerprint AS STRING) AS receipt_signer_fingerprint,
  CAST(a.created_at AS STRING) AS created_at
FROM oa_pg.attestation a
LEFT JOIN oa_pg.attest_receipt r ON a.receipt_id = r.receipt_id
