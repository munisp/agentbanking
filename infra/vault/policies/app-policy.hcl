# ─── 54Link Application Vault Policy ─────────────────────────────────────────
# Grants the application read access to its secrets

# Application secrets
path "secret/data/54link/app/*" {
  capabilities = ["read", "list"]
}

# Database credentials (dynamic secrets)
path "database/creds/54link-app" {
  capabilities = ["read"]
}

# PKI certificates
path "pki/issue/54link-app" {
  capabilities = ["create", "update"]
}

# Transit encryption (for PII fields)
path "transit/encrypt/54link-pii" {
  capabilities = ["create", "update"]
}

path "transit/decrypt/54link-pii" {
  capabilities = ["create", "update"]
}

# Token self-renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}
