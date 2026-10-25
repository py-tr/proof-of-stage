ACTIVATE USL TABLE lightning.metastore.registry_audit.attest_audit.receipt AS
SELECT
  COALESCE(CAST(receipt_id AS STRING), '') AS receipt_id,
  CAST(item_id AS STRING) AS item_id,
  CAST(served_model AS STRING) AS served_model,
  CAST(route_kind AS STRING) AS route_kind,
  CAST(signer_fingerprint AS STRING) AS signer_fingerprint,
  CAST(signature_state AS STRING) AS signature_state,
  CAST(cache_status AS STRING) AS cache_status,
  CAST(created_at AS STRING) AS created_at
FROM oa_pg.attest_receipt
