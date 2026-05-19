# ─── 54Link Vault Agent Configuration ────────────────────────────────────────
# Vault Agent auto-renews tokens and writes secrets to env files

vault {
  address = "http://vault:8200"
}

auto_auth {
  method "token_file" {
    config = {
      token_file_path = "/vault/config/.vault-token"
    }
  }

  sink "file" {
    config = {
      path = "/vault/config/.vault-token-renewed"
    }
  }
}

# ── Template: generate .env file for the app ─────────────────────────────────
template {
  source      = "/vault/config/templates/app.env.tpl"
  destination = "/vault/secrets/app.env"
  perms       = "0640"
  command     = "kill -HUP $(cat /var/run/app.pid) 2>/dev/null || true"
}

# ── Cache ─────────────────────────────────────────────────────────────────────
cache {
  use_auto_auth_token = true
}

listener "tcp" {
  address     = "127.0.0.1:8007"
  tls_disable = true
}
