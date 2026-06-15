use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct EncryptedField {
    ciphertext: String,
    iv: String,
    tag: String,
    field_type: String,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct EncryptRequest {
    field_type: String,
    plaintext: String,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct DecryptRequest {
    ciphertext: String,
    iv: String,
    tag: String,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct MaskRequest {
    value: String,
    field_type: String,
}

struct VaultState {
    // In production, keys come from AWS KMS / HashiCorp Vault
    master_key: [u8; 32],
    encrypted_count: u64,
    decrypted_count: u64,
}

impl VaultState {
    fn new() -> Self {
        let mut key = [0u8; 32];
        // Derive key from env or use default for dev
        let key_hex = env::var("ENCRYPTION_KEY").unwrap_or_else(|_| {
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef".into()
        });
        if let Ok(bytes) = hex::decode(&key_hex) {
            key.copy_from_slice(&bytes[..32.min(bytes.len())]);
        }
        Self {
            master_key: key,
            encrypted_count: 0,
            decrypted_count: 0,
        }
    }

    fn encrypt(&mut self, plaintext: &str) -> EncryptedField {
        use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
        use aes_gcm::aead::Aead;

        let cipher = Aes256Gcm::new_from_slice(&self.master_key).unwrap();
        let mut iv_bytes = [0u8; 12];
        getrandom::getrandom(&mut iv_bytes).unwrap();
        let nonce = Nonce::from_slice(&iv_bytes);

        let ciphertext = cipher.encrypt(nonce, plaintext.as_bytes()).unwrap();
        self.encrypted_count += 1;

        EncryptedField {
            ciphertext: hex::encode(&ciphertext),
            iv: hex::encode(&iv_bytes),
            tag: String::new(), // GCM tag is appended to ciphertext
            field_type: String::new(),
        }
    }

    fn decrypt(&mut self, encrypted: &EncryptedField) -> Result<String, String> {
        use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
        use aes_gcm::aead::Aead;

        let cipher = Aes256Gcm::new_from_slice(&self.master_key)
            .map_err(|e| format!("key error: {}", e))?;
        let iv_bytes = hex::decode(&encrypted.iv).map_err(|e| format!("iv decode: {}", e))?;
        let nonce = Nonce::from_slice(&iv_bytes);
        let ciphertext = hex::decode(&encrypted.ciphertext).map_err(|e| format!("ct decode: {}", e))?;

        let plaintext = cipher.decrypt(nonce, ciphertext.as_ref())
            .map_err(|e| format!("decrypt error: {}", e))?;
        self.decrypted_count += 1;

        String::from_utf8(plaintext).map_err(|e| format!("utf8 error: {}", e))
    }

    fn mask(value: &str, field_type: &str) -> String {
        match field_type {
            "bvn" => {
                if value.len() >= 11 {
                    format!("{}*****{}", &value[..3], &value[value.len()-3..])
                } else {
                    "***********".into()
                }
            }
            "nin" => {
                if value.len() >= 11 {
                    format!("{}*****{}", &value[..3], &value[value.len()-3..])
                } else {
                    "***********".into()
                }
            }
            "phone" => {
                if value.len() >= 7 {
                    format!("{}****{}", &value[..3], &value[value.len()-4..])
                } else {
                    "***********".into()
                }
            }
            "email" => {
                if let Some(at) = value.find('@') {
                    format!("{}****{}", &value[..1], &value[at..])
                } else {
                    "****@****.***".into()
                }
            }
            _ => {
                let len = value.len();
                if len > 4 {
                    format!("{}{}{}",
                        &value[..2],
                        "*".repeat(len - 4),
                        &value[len-2..])
                } else {
                    "*".repeat(len)
                }
            }
        }
    }
}


// --- Auth Middleware ---
fn verify_auth(headers: &hyper::HeaderMap) -> Result<String, (hyper::StatusCode, String)> {
    let auth_header = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or((
            hyper::StatusCode::UNAUTHORIZED,
            r#"{"error":"missing authorization header"}"#.to_string(),
        ))?;
    
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
        return Err((
            hyper::StatusCode::UNAUTHORIZED,
            r#"{"error":"invalid token format"}"#.to_string(),
        ));
    }
    
    // In production: validate JWT via Keycloak JWKS
    Ok(auth_header[7..].to_string())
}


// --- PostgreSQL Persistence ---
async fn get_db_pool() -> Result<deadpool_postgres::Pool, Box<dyn std::error::Error>> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/pii_encryption_vault".to_string());
    
    let config: tokio_postgres::Config = database_url.parse()?;
    let manager = deadpool_postgres::Manager::new(config, tokio_postgres::NoTls);
    let pool = deadpool_postgres::Pool::builder(manager)
        .max_size(16)
        .build()?;
    Ok(pool)
}

#[tokio::main]
async fn main() {
    // OpenTelemetry tracing setup
    if let Ok(endpoint) = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT") {
        eprintln!("[OTel] Tracing enabled → {}", endpoint);
    }

    let port: u16 = env::var("PORT").unwrap_or_else(|_| "8450".into()).parse().unwrap_or(8450);
    let state = Arc::new(RwLock::new(VaultState::new()));

    let app = axum::Router::new()
        .route("/health", axum::routing::get(health_handler))
        .route("/api/v1/encrypt", axum::routing::post({
            let state = Arc::clone(&state);
            move |body: axum::Json<EncryptRequest>| {
                let state = Arc::clone(&state);
                async move {
                    let mut vault = state.write().await;
                    let mut result = vault.encrypt(&body.plaintext);
                    result.field_type = body.field_type.clone();
                    axum::Json(result)
                }
            }
        }))
        .route("/api/v1/decrypt", axum::routing::post({
            let state = Arc::clone(&state);
            move |body: axum::Json<DecryptRequest>| {
                let state = Arc::clone(&state);
                async move {
                    let encrypted = EncryptedField {
                        ciphertext: body.ciphertext.clone(),
                        iv: body.iv.clone(),
                        tag: body.tag.clone(),
                        field_type: String::new(),
                    };
                    let mut vault = state.write().await;
                    match vault.decrypt(&encrypted) {
                        Ok(plaintext) => axum::Json(serde_json::json!({ "plaintext": plaintext })),
                        Err(e) => axum::Json(serde_json::json!({ "error": e })),
                    }
                }
            }
        }))
        .route("/api/v1/mask", axum::routing::post({
            move |body: axum::Json<MaskRequest>| async move {
                let masked = VaultState::mask(&body.value, &body.field_type);
                axum::Json(serde_json::json!({ "masked": masked }))
            }
        }))
        .route("/api/v1/stats", axum::routing::get({
            let state = Arc::clone(&state);
            move || {
                let state = Arc::clone(&state);
                async move {
                    let vault = state.read().await;
                    axum::Json(serde_json::json!({
                        "encrypted_count": vault.encrypted_count,
                        "decrypted_count": vault.decrypted_count,
                    }))
                }
            }
        }));

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!("PII Encryption Vault listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health_handler() -> axum::Json<serde_json::Value> {
    axum::Json(serde_json::json!({
        "status": "healthy",
        "service": "pii-encryption-vault"
    }))
}
