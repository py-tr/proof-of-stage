REGISTER DQ receipt_signed TABLE lightning.metastore.registry_audit.attest_audit.receipt AS
signature_state = 'verified' AND signer_fingerprint = '7a6d14e27e1a';
REGISTER DQ receipt_nemotron TABLE lightning.metastore.registry_audit.attest_audit.receipt AS
served_model LIKE 'nvidia/nemotron%' OR served_model LIKE 'local-runtime/nemotron%';
REGISTER DQ receipt_not_cached TABLE lightning.metastore.registry_audit.attest_audit.receipt AS
cache_status IS NULL OR cache_status IN ('miss', 'bypass');
REGISTER DQ attested TABLE lightning.metastore.registry_audit.attest_audit.attestation AS
receipt_signature_state = 'verified' AND receipt_signer_fingerprint = '7a6d14e27e1a';
REGISTER DQ reproduced TABLE lightning.metastore.registry_audit.attest_audit.attestation AS
outcome = 'reproduced'
