//! Cryptographic Audit Chain Service
use tokio::signal;
//!
use tokio::signal;
//! Provides tamper-proof audit logging using SHA-256 hash chains.
use tokio::signal;
//! Each audit entry includes the hash of the previous entry, making it
use tokio::signal;
//! computationally infeasible for insiders to modify or delete log entries
use tokio::signal;
//! without detection.
use tokio::signal;
//!
use tokio::signal;
//! All state persisted to PostgreSQL — zero in-memory mutable state.
use tokio::signal;
//!
use tokio::signal;
//! Features:
use tokio::signal;
//! - Hash-chain integrity (each entry references previous hash)
use tokio::signal;
//! - Real-time SIEM forwarding (Splunk/ELK compatible)
use tokio::signal;
//! - Chain verification endpoint (detect tampering)
use tokio::signal;
//! - Privileged action flagging (insider threat patterns)
use tokio::signal;

use actix_web::{web, App, HttpServer, HttpResponse};
use chrono::{Utc, Timelike};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use uuid::Uuid;
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};
use tokio::signal;
#[derive(Debug, Clone, Serialize, Deserialize)]
use tokio::signal;
pub struct AuditEntry {
use tokio::signal;
    pub id: String,
use tokio::signal;
    pub sequence: i64,
use tokio::signal;
    pub timestamp: String,
use tokio::signal;
    pub agent_id: i64,
use tokio::signal;
    pub agent_code: String,
use tokio::signal;
    pub action: String,
use tokio::signal;
    pub resource: String,
use tokio::signal;
    pub resource_id: String,
use tokio::signal;
    pub ip_address: String,
use tokio::signal;
    pub user_agent: String,
use tokio::signal;
    pub metadata: serde_json::Value,
use tokio::signal;
    pub risk_score: i32, // 0-100
use tokio::signal;
    pub previous_hash: String,
use tokio::signal;
    pub entry_hash: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Debug, Clone, Serialize, Deserialize)]
use tokio::signal;
pub struct AuditRequest {
use tokio::signal;
    pub agent_id: i64,
use tokio::signal;
    pub agent_code: String,
use tokio::signal;
    pub action: String,
use tokio::signal;
    pub resource: String,
use tokio::signal;
    pub resource_id: String,
use tokio::signal;
    pub ip_address: Option<String>,
use tokio::signal;
    pub user_agent: Option<String>,
use tokio::signal;
    pub metadata: Option<serde_json::Value>,
use tokio::signal;
}
use tokio::signal;
#[derive(Debug, Clone, Serialize, Deserialize)]
use tokio::signal;
pub struct VerifyResponse {
use tokio::signal;
    pub valid: bool,
use tokio::signal;
    pub total_entries: i64,
use tokio::signal;
    pub checked_entries: i64,
use tokio::signal;
    pub first_invalid_at: Option<i64>,
use tokio::signal;
    pub message: String,
use tokio::signal;
}
use tokio::signal;
struct AppState {
use tokio::signal;
    pool: PgPool,
use tokio::signal;
    siem_endpoint: Option<String>,
use tokio::signal;
}
use tokio::signal;
/// Calculate SHA-256 hash of an audit entry (excluding entry_hash field)
use tokio::signal;
fn calculate_entry_hash(entry: &AuditEntry) -> String {
use tokio::signal;
    let mut hasher = Sha256::new();
use tokio::signal;
    hasher.update(entry.sequence.to_string().as_bytes());
use tokio::signal;
    hasher.update(entry.timestamp.as_bytes());
use tokio::signal;
    hasher.update(entry.agent_id.to_string().as_bytes());
use tokio::signal;
    hasher.update(entry.agent_code.as_bytes());
use tokio::signal;
    hasher.update(entry.action.as_bytes());
use tokio::signal;
    hasher.update(entry.resource.as_bytes());
use tokio::signal;
    hasher.update(entry.resource_id.as_bytes());
use tokio::signal;
    hasher.update(entry.ip_address.as_bytes());
use tokio::signal;
    hasher.update(entry.previous_hash.as_bytes());
use tokio::signal;
    hasher.update(serde_json::to_string(&entry.metadata).unwrap_or_default().as_bytes());
use tokio::signal;
    hex::encode(hasher.finalize())
use tokio::signal;
}
use tokio::signal;
/// Calculate risk score based on action patterns
use tokio::signal;
fn calculate_risk_score(action: &str, metadata: &serde_json::Value) -> i32 {
use tokio::signal;
    let mut score: i32 = 0;
use tokio::signal;
    // High-risk actions
use tokio::signal;
    match action {
use tokio::signal;
        "REVERSAL_APPROVED" | "REVERSAL_REQUESTED" => score += 40,
use tokio::signal;
        "FLOAT_ADJUSTMENT" | "FEE_OVERRIDE" => score += 50,
use tokio::signal;
        "ACCOUNT_PRIVILEGE_CHANGE" | "AGENT_DEACTIVATED" => score += 60,
use tokio::signal;
        "SYSTEM_CONFIG_CHANGE" => score += 70,
use tokio::signal;
        "BREAK_GLASS_ACCESS" => score += 90,
use tokio::signal;
        "LOAN_DISBURSED" | "COMMISSION_PAYOUT" => score += 30,
use tokio::signal;
        _ => score += 10,
use tokio::signal;
    }
use tokio::signal;
    // Amount-based risk
use tokio::signal;
    if let Some(amount) = metadata.get("amount").and_then(|a| a.as_f64()) {
use tokio::signal;
        if amount > 5_000_000.0 { score += 30; }
use tokio::signal;
        else if amount > 1_000_000.0 { score += 20; }
use tokio::signal;
        else if amount > 500_000.0 { score += 10; }
use tokio::signal;
    }
use tokio::signal;
    // Off-hours risk (UTC 22:00 - 06:00)
use tokio::signal;
    let hour = Utc::now().hour();
use tokio::signal;
    if hour >= 22 || hour < 6 {
use tokio::signal;
        score += 15;
use tokio::signal;
    }
use tokio::signal;
    score.min(100)
use tokio::signal;
}
use tokio::signal;
/// Initialize the audit_chain table in PostgreSQL
use tokio::signal;
async fn init_db(pool: &PgPool) {
use tokio::signal;
    sqlx::query(r#"
use tokio::signal;
        CREATE TABLE IF NOT EXISTS audit_chain (
use tokio::signal;
            id           VARCHAR(64) PRIMARY KEY,
use tokio::signal;
            sequence     BIGSERIAL NOT NULL UNIQUE,
use tokio::signal;
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
use tokio::signal;
            agent_id     BIGINT NOT NULL,
use tokio::signal;
            agent_code   VARCHAR(64) NOT NULL,
use tokio::signal;
            action       VARCHAR(128) NOT NULL,
use tokio::signal;
            resource     VARCHAR(128) NOT NULL,
use tokio::signal;
            resource_id  VARCHAR(128) NOT NULL,
use tokio::signal;
            ip_address   VARCHAR(64) NOT NULL DEFAULT 'unknown',
use tokio::signal;
            user_agent   TEXT NOT NULL DEFAULT 'unknown',
use tokio::signal;
            metadata     JSONB NOT NULL DEFAULT '{}',
use tokio::signal;
            risk_score   INT NOT NULL DEFAULT 0,
use tokio::signal;
            previous_hash VARCHAR(128) NOT NULL,
use tokio::signal;
            entry_hash   VARCHAR(128) NOT NULL
use tokio::signal;
        );
use tokio::signal;
        CREATE INDEX IF NOT EXISTS idx_audit_chain_agent_id ON audit_chain (agent_id);
use tokio::signal;
        CREATE INDEX IF NOT EXISTS idx_audit_chain_risk_score ON audit_chain (risk_score);
use tokio::signal;
        CREATE INDEX IF NOT EXISTS idx_audit_chain_sequence ON audit_chain (sequence);
use tokio::signal;
        CREATE INDEX IF NOT EXISTS idx_audit_chain_action ON audit_chain (action);
use tokio::signal;
    "#)
use tokio::signal;
    .execute(pool)
use tokio::signal;
    .await
use tokio::signal;
    .expect("Failed to create audit_chain table");
use tokio::signal;
    println!("PostgreSQL connected — audit_chain table ready");
use tokio::signal;
}
use tokio::signal;
/// Append a new audit entry to the hash chain (persisted in PostgreSQL)
use tokio::signal;
async fn append_entry(
use tokio::signal;
    data: web::Data<AppState>,
use tokio::signal;
    body: web::Json<AuditRequest>,
use tokio::signal;
) -> HttpResponse {
use tokio::signal;
    let pool = &data.pool;
use tokio::signal;
    // Get the last entry's hash from PostgreSQL for chain linkage
use tokio::signal;
    let previous_hash: String = sqlx::query_scalar(
use tokio::signal;
        "SELECT entry_hash FROM audit_chain ORDER BY sequence DESC LIMIT 1"
use tokio::signal;
    )
use tokio::signal;
    .fetch_optional(pool)
use tokio::signal;
    .await
use tokio::signal;
    .unwrap_or(None)
use tokio::signal;
    .unwrap_or_else(|| "GENESIS".to_string());
use tokio::signal;
    // Get next sequence
use tokio::signal;
    let next_sequence: i64 = sqlx::query_scalar(
use tokio::signal;
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_chain"
use tokio::signal;
    )
use tokio::signal;
    .fetch_one(pool)
use tokio::signal;
    .await
use tokio::signal;
    .unwrap_or(1);
use tokio::signal;
    let metadata = body.metadata.clone().unwrap_or(serde_json::json!({}));
use tokio::signal;
    let risk_score = calculate_risk_score(&body.action, &metadata);
use tokio::signal;
    let mut entry = AuditEntry {
use tokio::signal;
        id: Uuid::new_v4().to_string(),
use tokio::signal;
        sequence: next_sequence,
use tokio::signal;
        timestamp: Utc::now().to_rfc3339(),
use tokio::signal;
        agent_id: body.agent_id,
use tokio::signal;
        agent_code: body.agent_code.clone(),
use tokio::signal;
        action: body.action.clone(),
use tokio::signal;
        resource: body.resource.clone(),
use tokio::signal;
        resource_id: body.resource_id.clone(),
use tokio::signal;
        ip_address: body.ip_address.clone().unwrap_or_else(|| "unknown".to_string()),
use tokio::signal;
        user_agent: body.user_agent.clone().unwrap_or_else(|| "unknown".to_string()),
use tokio::signal;
        metadata: metadata.clone(),
use tokio::signal;
        risk_score,
use tokio::signal;
        previous_hash,
use tokio::signal;
        entry_hash: String::new(),
use tokio::signal;
    };
use tokio::signal;
    entry.entry_hash = calculate_entry_hash(&entry);
use tokio::signal;
    // Persist to PostgreSQL
use tokio::signal;
    let result = sqlx::query(r#"
use tokio::signal;
        INSERT INTO audit_chain (id, sequence, timestamp, agent_id, agent_code, action, resource, resource_id, ip_address, user_agent, metadata, risk_score, previous_hash, entry_hash)
use tokio::signal;
        VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
use tokio::signal;
    "#)
use tokio::signal;
    .bind(&entry.id)
use tokio::signal;
    .bind(entry.sequence)
use tokio::signal;
    .bind(&entry.timestamp)
use tokio::signal;
    .bind(entry.agent_id)
use tokio::signal;
    .bind(&entry.agent_code)
use tokio::signal;
    .bind(&entry.action)
use tokio::signal;
    .bind(&entry.resource)
use tokio::signal;
    .bind(&entry.resource_id)
use tokio::signal;
    .bind(&entry.ip_address)
use tokio::signal;
    .bind(&entry.user_agent)
use tokio::signal;
    .bind(&entry.metadata)
use tokio::signal;
    .bind(entry.risk_score)
use tokio::signal;
    .bind(&entry.previous_hash)
use tokio::signal;
    .bind(&entry.entry_hash)
use tokio::signal;
    .execute(pool)
use tokio::signal;
    .await;
use tokio::signal;
    if let Err(e) = result {
use tokio::signal;
        return HttpResponse::InternalServerError().json(serde_json::json!({
use tokio::signal;
            "error": format!("Failed to persist audit entry: {}", e)
use tokio::signal;
        }));
use tokio::signal;
    }
use tokio::signal;
    // Forward to SIEM if configured
use tokio::signal;
    if let Some(ref siem_url) = data.siem_endpoint {
use tokio::signal;
        let siem_url = siem_url.clone();
use tokio::signal;
        let entry_clone = entry.clone();
use tokio::signal;
        tokio::spawn(async move {
use tokio::signal;
            let _ = reqwest::Client::new()
use tokio::signal;
                .post(&siem_url)
use tokio::signal;
                .json(&entry_clone)
use tokio::signal;
                .send()
use tokio::signal;
                .await;
use tokio::signal;
        });
use tokio::signal;
    }
use tokio::signal;
    // Alert on high-risk entries via Dapr pub/sub
use tokio::signal;
    if risk_score >= 70 {
use tokio::signal;
        let entry_clone = entry.clone();
use tokio::signal;
        tokio::spawn(async move {
use tokio::signal;
            let _ = reqwest::Client::new()
use tokio::signal;
                .post("http://localhost:3500/v1.0/publish/pubsub/insider.threat.high-risk-action")
use tokio::signal;
                .json(&serde_json::json!({
use tokio::signal;
                    "entryId": entry_clone.id,
use tokio::signal;
                    "agentCode": entry_clone.agent_code,
use tokio::signal;
                    "action": entry_clone.action,
use tokio::signal;
                    "riskScore": entry_clone.risk_score,
use tokio::signal;
                    "timestamp": entry_clone.timestamp,
use tokio::signal;
                }))
use tokio::signal;
                .send()
use tokio::signal;
                .await;
use tokio::signal;
        });
use tokio::signal;
    }
use tokio::signal;
    HttpResponse::Ok().json(serde_json::json!({
use tokio::signal;
        "id": entry.id,
use tokio::signal;
        "sequence": entry.sequence,
use tokio::signal;
        "entryHash": entry.entry_hash,
use tokio::signal;
        "riskScore": entry.risk_score,
use tokio::signal;
    }))
use tokio::signal;
}
use tokio::signal;
/// Verify the integrity of the hash chain (reads from PostgreSQL)
use tokio::signal;
async fn verify_chain(data: web::Data<AppState>) -> HttpResponse {
use tokio::signal;
    let pool = &data.pool;
use tokio::signal;
    let rows = sqlx::query(
use tokio::signal;
        "SELECT id, sequence, timestamp::text, agent_id, agent_code, action, resource, resource_id, ip_address, user_agent, metadata, risk_score, previous_hash, entry_hash FROM audit_chain ORDER BY sequence ASC"
use tokio::signal;
    )
use tokio::signal;
    .fetch_all(pool)
use tokio::signal;
    .await;
use tokio::signal;
    let rows = match rows {
use tokio::signal;
        Ok(r) => r,
use tokio::signal;
        Err(e) => {
use tokio::signal;
            return HttpResponse::InternalServerError().json(serde_json::json!({
use tokio::signal;
                "error": format!("Database error: {}", e)
use tokio::signal;
            }));
use tokio::signal;
        }
use tokio::signal;
    };
use tokio::signal;
    if rows.is_empty() {
use tokio::signal;
        return HttpResponse::Ok().json(VerifyResponse {
use tokio::signal;
            valid: true,
use tokio::signal;
            total_entries: 0,
use tokio::signal;
            checked_entries: 0,
use tokio::signal;
            first_invalid_at: None,
use tokio::signal;
            message: "Chain is empty".to_string(),
use tokio::signal;
        });
use tokio::signal;
    }
use tokio::signal;
    let mut first_invalid: Option<i64> = None;
use tokio::signal;
    let mut prev_hash = String::new();
use tokio::signal;
    for (i, row) in rows.iter().enumerate() {
use tokio::signal;
        let entry = AuditEntry {
use tokio::signal;
            id: row.get("id"),
use tokio::signal;
            sequence: row.get("sequence"),
use tokio::signal;
            timestamp: row.get("timestamp"),
use tokio::signal;
            agent_id: row.get("agent_id"),
use tokio::signal;
            agent_code: row.get("agent_code"),
use tokio::signal;
            action: row.get("action"),
use tokio::signal;
            resource: row.get("resource"),
use tokio::signal;
            resource_id: row.get("resource_id"),
use tokio::signal;
            ip_address: row.get("ip_address"),
use tokio::signal;
            user_agent: row.get("user_agent"),
use tokio::signal;
            metadata: row.get("metadata"),
use tokio::signal;
            risk_score: row.get("risk_score"),
use tokio::signal;
            previous_hash: row.get("previous_hash"),
use tokio::signal;
            entry_hash: row.get("entry_hash"),
use tokio::signal;
        };
use tokio::signal;
        // Verify hash
use tokio::signal;
        let expected_hash = calculate_entry_hash(&entry);
use tokio::signal;
        if expected_hash != entry.entry_hash {
use tokio::signal;
            first_invalid = Some(entry.sequence);
use tokio::signal;
            break;
use tokio::signal;
        }
use tokio::signal;
        // Verify chain linkage
use tokio::signal;
        if i == 0 {
use tokio::signal;
            if entry.previous_hash != "GENESIS" {
use tokio::signal;
                first_invalid = Some(entry.sequence);
use tokio::signal;
                break;
use tokio::signal;
            }
use tokio::signal;
        } else if entry.previous_hash != prev_hash {
use tokio::signal;
            first_invalid = Some(entry.sequence);
use tokio::signal;
            break;
use tokio::signal;
        }
use tokio::signal;
        prev_hash = entry.entry_hash.clone();
use tokio::signal;
    }
use tokio::signal;
    let total = rows.len() as i64;
use tokio::signal;
    let response = VerifyResponse {
use tokio::signal;
        valid: first_invalid.is_none(),
use tokio::signal;
        total_entries: total,
use tokio::signal;
        checked_entries: total,
use tokio::signal;
        first_invalid_at: first_invalid,
use tokio::signal;
        message: if first_invalid.is_none() {
use tokio::signal;
            "Hash chain integrity verified — no tampering detected".to_string()
use tokio::signal;
        } else {
use tokio::signal;
            format!("TAMPERING DETECTED at sequence {}", first_invalid.unwrap())
use tokio::signal;
        },
use tokio::signal;
    };
use tokio::signal;
    HttpResponse::Ok().json(response)
use tokio::signal;
}
use tokio::signal;
/// Get recent high-risk entries from PostgreSQL
use tokio::signal;
async fn get_high_risk(data: web::Data<AppState>) -> HttpResponse {
use tokio::signal;
    let pool = &data.pool;
use tokio::signal;
    let rows = sqlx::query(
use tokio::signal;
        "SELECT id, sequence, timestamp::text, agent_id, agent_code, action, resource, resource_id, ip_address, user_agent, metadata, risk_score, previous_hash, entry_hash FROM audit_chain WHERE risk_score >= 50 ORDER BY sequence DESC LIMIT 100"
use tokio::signal;
    )
use tokio::signal;
    .fetch_all(pool)
use tokio::signal;
    .await;
use tokio::signal;
    match rows {
use tokio::signal;
        Ok(rows) => {
use tokio::signal;
            let entries: Vec<AuditEntry> = rows.iter().map(|row| AuditEntry {
use tokio::signal;
                id: row.get("id"),
use tokio::signal;
                sequence: row.get("sequence"),
use tokio::signal;
                timestamp: row.get("timestamp"),
use tokio::signal;
                agent_id: row.get("agent_id"),
use tokio::signal;
                agent_code: row.get("agent_code"),
use tokio::signal;
                action: row.get("action"),
use tokio::signal;
                resource: row.get("resource"),
use tokio::signal;
                resource_id: row.get("resource_id"),
use tokio::signal;
                ip_address: row.get("ip_address"),
use tokio::signal;
                user_agent: row.get("user_agent"),
use tokio::signal;
                metadata: row.get("metadata"),
use tokio::signal;
                risk_score: row.get("risk_score"),
use tokio::signal;
                previous_hash: row.get("previous_hash"),
use tokio::signal;
                entry_hash: row.get("entry_hash"),
use tokio::signal;
            }).collect();
use tokio::signal;
            HttpResponse::Ok().json(entries)
use tokio::signal;
        }
use tokio::signal;
        Err(e) => HttpResponse::InternalServerError().json(serde_json::json!({
use tokio::signal;
            "error": format!("Database error: {}", e)
use tokio::signal;
        })),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
/// Health check
use tokio::signal;
async fn health(data: web::Data<AppState>) -> HttpResponse {
use tokio::signal;
    let db_ok = sqlx::query("SELECT 1")
use tokio::signal;
        .fetch_one(&data.pool)
use tokio::signal;
        .await
use tokio::signal;
        .is_ok();
use tokio::signal;
    HttpResponse::Ok().json(serde_json::json!({
use tokio::signal;
        "status": if db_ok { "healthy" } else { "degraded" },
use tokio::signal;
        "service": "audit-chain",
use tokio::signal;
        "version": "2.0.0",
use tokio::signal;
        "storage": "postgresql",
use tokio::signal;
    }))
use tokio::signal;
}
use tokio::signal;
#[actix_web::main]
use tokio::signal;
async fn main() -> std::io::Result<()> {
use tokio::signal;
    let siem_endpoint = std::env::var("SIEM_ENDPOINT").ok();
use tokio::signal;
    let port: u16 = std::env::var("AUDIT_CHAIN_PORT")
use tokio::signal;
        .unwrap_or_else(|_| "8260".to_string())
use tokio::signal;
        .parse()
use tokio::signal;
        .unwrap_or(8260);
use tokio::signal;
    let database_url = std::env::var("DATABASE_URL")
use tokio::signal;
        .or_else(|_| std::env::var("POSTGRES_URL"))
use tokio::signal;
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/agentbanking".to_string());
use tokio::signal;
    println!("Audit Chain Service v2.0.0 starting on port {}", port);
use tokio::signal;
    println!("SIEM forwarding: {}", siem_endpoint.as_deref().unwrap_or("disabled"));
use tokio::signal;
    println!("PostgreSQL: connecting...");
use tokio::signal;
    let pool = PgPoolOptions::new()
use tokio::signal;
        .max_connections(25)
use tokio::signal;
        .acquire_timeout(std::time::Duration::from_secs(10))
use tokio::signal;
        .connect(&database_url)
use tokio::signal;
        .await
use tokio::signal;
        .expect("Failed to connect to PostgreSQL");
use tokio::signal;
    init_db(&pool).await;
use tokio::signal;
    let data = web::Data::new(AppState {
use tokio::signal;
        pool,
use tokio::signal;
        siem_endpoint,
use tokio::signal;
    });
use tokio::signal;
    HttpServer::new(move || {
use tokio::signal;
        App::new()
use tokio::signal;
            .app_data(data.clone())
use tokio::signal;
            .route("/health", web::get().to(health))
use tokio::signal;
            .route("/append", web::post().to(append_entry))
use tokio::signal;
            .route("/verify", web::get().to(verify_chain))
use tokio::signal;
            .route("/high-risk", web::get().to(get_high_risk))
use tokio::signal;
    })
use tokio::signal;
    .bind(("0.0.0.0", port))?
use tokio::signal;
    .run()
use tokio::signal;
    .await
use tokio::signal;
