# Vault policy for pos-shell Node.js server
# Grants read access to all pos-shell secrets

path "secret/data/pos-shell-demo" {
  capabilities = ["read"]
}

path "secret/data/pos-shell-demo/*" {
  capabilities = ["read"]
}

path "secret/metadata/pos-shell-demo" {
  capabilities = ["list"]
}

path "secret/metadata/pos-shell-demo/*" {
  capabilities = ["list"]
}

# Allow reading dynamic database credentials
path "database/creds/pos-shell-role" {
  capabilities = ["read"]
}

# Allow reading PKI certificates
path "pki/issue/pos-shell" {
  capabilities = ["create", "update"]
}

# Allow reading transit keys for encryption
path "transit/encrypt/pos-shell" {
  capabilities = ["create", "update"]
}

path "transit/decrypt/pos-shell" {
  capabilities = ["create", "update"]
}
