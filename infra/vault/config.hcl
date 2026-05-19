# ─── 54Link HashiCorp Vault Server Configuration ──────────────────────────────
# Production configuration using Raft integrated storage (no Consul dependency)

ui = true

# ── Storage backend (Raft integrated) ────────────────────────────────────────
storage "raft" {
  path    = "/vault/data"
  node_id = "vault-node-1"

  retry_join {
    leader_api_addr = "http://vault:8200"
  }
}

# ── Listener ──────────────────────────────────────────────────────────────────
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = "true"  # TLS is terminated at nginx in production
  # For direct TLS (no nginx):
  # tls_cert_file = "/vault/certs/vault.crt"
  # tls_key_file  = "/vault/certs/vault.key"
}

# ── Cluster ───────────────────────────────────────────────────────────────────
cluster_addr = "http://vault:8201"
api_addr     = "http://vault:8200"

# ── Telemetry ─────────────────────────────────────────────────────────────────
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = true
}

# ── Audit ─────────────────────────────────────────────────────────────────────
# Audit log is enabled via Vault CLI after initialisation:
# vault audit enable file file_path=/vault/logs/audit.log

# ── Seal (auto-unseal via AWS KMS in production) ──────────────────────────────
# Uncomment and configure for production auto-unseal:
# seal "awskms" {
#   region     = "us-east-1"
#   kms_key_id = "alias/vault-unseal-key"
# }

# ── Misc ──────────────────────────────────────────────────────────────────────
disable_mlock = true   # Required in Docker (no CAP_IPC_LOCK by default)
log_level     = "info"
