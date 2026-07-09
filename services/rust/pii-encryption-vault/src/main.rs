
use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::signal;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
use tokio::signal;
struct EncryptedField {
use tokio::signal;
    ciphertext: String,
use tokio::signal;
    iv: String,
use tokio::signal;
    tag: String,
use tokio::signal;
    field_type: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
use tokio::signal;
struct EncryptRequest {
use tokio::signal;
    field_type: String,
use tokio::signal;
    plaintext: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
use tokio::signal;
struct DecryptRequest {
use tokio::signal;
    ciphertext: String,
use tokio::signal;
    iv: String,
use tokio::signal;
    tag: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
use tokio::signal;
struct MaskRequest {
use tokio::signal;
    value: String,
use tokio::signal;
    field_type: String,
use tokio::signal;
}
use tokio::signal;
struct VaultState {
use tokio::signal;
    // In production, keys come from AWS KMS / HashiCorp Vault
use tokio::signal;
    master_key: [u8; 32],
use tokio::signal;
    encrypted_count: u64,
use tokio::signal;
    decrypted_count: u64,
use tokio::signal;
}
use tokio::signal;
impl VaultState {
use tokio::signal;
    fn new() -> Self {
use tokio::signal;
        let mut key = [0u8; 32];
use tokio::signal;
        // Derive key from env or use default for dev
use tokio::signal;
        let key_hex = env::var("ENCRYPTION_KEY").unwrap_or_else(|_| {
use tokio::signal;
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef".into()
use tokio::signal;
        });
use tokio::signal;
        if let Ok(bytes) = hex::decode(&key_hex) {
use tokio::signal;
            key.copy_from_slice(&bytes[..32.min(bytes.len())]);
use tokio::signal;
        }
use tokio::signal;
        Self {
use tokio::signal;
            master_key: key,
use tokio::signal;
            encrypted_count: 0,
use tokio::signal;
            decrypted_count: 0,
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    fn encrypt(&mut self, plaintext: &str) -> EncryptedField {
use tokio::signal;
        use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use tokio::signal;
        use aes_gcm::aead::Aead;
use tokio::signal;
        let cipher = Aes256Gcm::new_from_slice(&self.master_key).unwrap();
use tokio::signal;
        let mut iv_bytes = [0u8; 12];
use tokio::signal;
        getrandom::getrandom(&mut iv_bytes).unwrap();
use tokio::signal;
        let nonce = Nonce::from_slice(&iv_bytes);
use tokio::signal;
        let ciphertext = cipher.encrypt(nonce, plaintext.as_bytes()).unwrap();
use tokio::signal;
        self.encrypted_count += 1;
use tokio::signal;
        EncryptedField {
use tokio::signal;
            ciphertext: hex::encode(&ciphertext),
use tokio::signal;
            iv: hex::encode(&iv_bytes),
use tokio::signal;
            tag: String::new(), // GCM tag is appended to ciphertext
use tokio::signal;
            field_type: String::new(),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    fn decrypt(&mut self, encrypted: &EncryptedField) -> Result<String, String> {
use tokio::signal;
        use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use tokio::signal;
        use aes_gcm::aead::Aead;
use tokio::signal;
        let cipher = Aes256Gcm::new_from_slice(&self.master_key)
use tokio::signal;
            .map_err(|e| format!("key error: {}", e))?;
use tokio::signal;
        let iv_bytes = hex::decode(&encrypted.iv).map_err(|e| format!("iv decode: {}", e))?;
use tokio::signal;
        let nonce = Nonce::from_slice(&iv_bytes);
use tokio::signal;
        let ciphertext = hex::decode(&encrypted.ciphertext).map_err(|e| format!("ct decode: {}", e))?;
use tokio::signal;
        let plaintext = cipher.decrypt(nonce, ciphertext.as_ref())
use tokio::signal;
            .map_err(|e| format!("decrypt error: {}", e))?;
use tokio::signal;
        self.decrypted_count += 1;
use tokio::signal;
        String::from_utf8(plaintext).map_err(|e| format!("utf8 error: {}", e))
use tokio::signal;
    }
use tokio::signal;
    fn mask(value: &str, field_type: &str) -> String {
use tokio::signal;
        match field_type {
use tokio::signal;
            "bvn" => {
use tokio::signal;
                if value.len() >= 11 {
use tokio::signal;
                    format!("{}*****{}", &value[..3], &value[value.len()-3..])
use tokio::signal;
                } else {
use tokio::signal;
                    "***********".into()
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
            "nin" => {
use tokio::signal;
                if value.len() >= 11 {
use tokio::signal;
                    format!("{}*****{}", &value[..3], &value[value.len()-3..])
use tokio::signal;
                } else {
use tokio::signal;
                    "***********".into()
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
            "phone" => {
use tokio::signal;
                if value.len() >= 7 {
use tokio::signal;
                    format!("{}****{}", &value[..3], &value[value.len()-4..])
use tokio::signal;
                } else {
use tokio::signal;
                    "***********".into()
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
            "email" => {
use tokio::signal;
                if let Some(at) = value.find('@') {
use tokio::signal;
                    format!("{}****{}", &value[..1], &value[at..])
use tokio::signal;
                } else {
use tokio::signal;
                    "****@****.***".into()
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
            _ => {
use tokio::signal;
                let len = value.len();
use tokio::signal;
                if len > 4 {
use tokio::signal;
                    format!("{}{}{}",
use tokio::signal;
                        &value[..2],
use tokio::signal;
                        "*".repeat(len - 4),
use tokio::signal;
                        &value[len-2..])
use tokio::signal;
                } else {
use tokio::signal;
                    "*".repeat(len)
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// --- Auth Middleware ---
use tokio::signal;
fn verify_auth(headers: &hyper::HeaderMap) -> Result<String, (hyper::StatusCode, String)> {
use tokio::signal;
    let auth_header = headers
use tokio::signal;
        .get("authorization")
use tokio::signal;
        .and_then(|v| v.to_str().ok())
use tokio::signal;
        .ok_or((
use tokio::signal;
            hyper::StatusCode::UNAUTHORIZED,
use tokio::signal;
            r#"{"error":"missing authorization header"}"#.to_string(),
use tokio::signal;
        ))?;
use tokio::signal;
    
use tokio::signal;
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
use tokio::signal;
        return Err((
use tokio::signal;
            hyper::StatusCode::UNAUTHORIZED,
use tokio::signal;
            r#"{"error":"invalid token format"}"#.to_string(),
use tokio::signal;
        ));
use tokio::signal;
    }
use tokio::signal;
    
use tokio::signal;
    // In production: validate JWT via Keycloak JWKS
use tokio::signal;
    Ok(auth_header[7..].to_string())
use tokio::signal;
}
use tokio::signal;
// --- PostgreSQL Persistence ---
use tokio::signal;
async fn get_db_pool() -> Result<deadpool_postgres::Pool, Box<dyn std::error::Error>> {
use tokio::signal;
    let database_url = std::env::var("DATABASE_URL")
use tokio::signal;
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/pii_encryption_vault".to_string());
use tokio::signal;
    
use tokio::signal;
    let config: tokio_postgres::Config = database_url.parse()?;
use tokio::signal;
    let manager = deadpool_postgres::Manager::new(config, tokio_postgres::NoTls);
use tokio::signal;
    let pool = deadpool_postgres::Pool::builder(manager)
use tokio::signal;
        .max_size(16)
use tokio::signal;
        .build()?;
use tokio::signal;
    Ok(pool)
use tokio::signal;
}
use tokio::signal;
#[tokio::main]
use tokio::signal;
async fn main() {
use tokio::signal;
    let port: u16 = env::var("PORT").unwrap_or_else(|_| "8450".into()).parse().unwrap_or(8450);
use tokio::signal;
    let state = Arc::new(RwLock::new(VaultState::new()));
use tokio::signal;
    let app = axum::Router::new()
use tokio::signal;
        .route("/health", axum::routing::get(health_handler))
use tokio::signal;
        .route("/api/v1/encrypt", axum::routing::post({
use tokio::signal;
            let state = Arc::clone(&state);
use tokio::signal;
            move |body: axum::Json<EncryptRequest>| {
use tokio::signal;
                let state = Arc::clone(&state);
use tokio::signal;
                async move {
use tokio::signal;
                    let mut vault = state.write().await;
use tokio::signal;
                    let mut result = vault.encrypt(&body.plaintext);
use tokio::signal;
                    result.field_type = body.field_type.clone();
use tokio::signal;
                    axum::Json(result)
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/decrypt", axum::routing::post({
use tokio::signal;
            let state = Arc::clone(&state);
use tokio::signal;
            move |body: axum::Json<DecryptRequest>| {
use tokio::signal;
                let state = Arc::clone(&state);
use tokio::signal;
                async move {
use tokio::signal;
                    let encrypted = EncryptedField {
use tokio::signal;
                        ciphertext: body.ciphertext.clone(),
use tokio::signal;
                        iv: body.iv.clone(),
use tokio::signal;
                        tag: body.tag.clone(),
use tokio::signal;
                        field_type: String::new(),
use tokio::signal;
                    };
use tokio::signal;
                    let mut vault = state.write().await;
use tokio::signal;
                    match vault.decrypt(&encrypted) {
use tokio::signal;
                        Ok(plaintext) => axum::Json(serde_json::json!({ "plaintext": plaintext })),
use tokio::signal;
                        Err(e) => axum::Json(serde_json::json!({ "error": e })),
use tokio::signal;
                    }
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/mask", axum::routing::post({
use tokio::signal;
            move |body: axum::Json<MaskRequest>| async move {
use tokio::signal;
                let masked = VaultState::mask(&body.value, &body.field_type);
use tokio::signal;
                axum::Json(serde_json::json!({ "masked": masked }))
use tokio::signal;
            }
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/stats", axum::routing::get({
use tokio::signal;
            let state = Arc::clone(&state);
use tokio::signal;
            move || {
use tokio::signal;
                let state = Arc::clone(&state);
use tokio::signal;
                async move {
use tokio::signal;
                    let vault = state.read().await;
use tokio::signal;
                    axum::Json(serde_json::json!({
use tokio::signal;
                        "encrypted_count": vault.encrypted_count,
use tokio::signal;
                        "decrypted_count": vault.decrypted_count,
use tokio::signal;
                    }))
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }));
use tokio::signal;
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
use tokio::signal;
    println!("PII Encryption Vault listening on {}", addr);
use tokio::signal;
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
use tokio::signal;
    axum::serve(listener, app).await.unwrap();
use tokio::signal;
}
use tokio::signal;
async fn health_handler() -> axum::Json<serde_json::Value> {
use tokio::signal;
    axum::Json(serde_json::json!({
use tokio::signal;
        "status": "healthy",
use tokio::signal;
        "service": "pii-encryption-vault"
use tokio::signal;
    }))
use tokio::signal;
