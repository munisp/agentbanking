# Vault policy for Temporal workflow worker
path "secret/data/temporal/*" {
  capabilities = ["read"]
}

path "secret/data/pos-shell-demo" {
  capabilities = ["read"]
}

path "database/creds/temporal-role" {
  capabilities = ["read"]
}
