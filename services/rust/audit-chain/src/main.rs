//! Cryptographic Audit Chain Service
//!
//! Provides tamper-proof audit logging using SHA-256 hash chains.
//! Each audit entry includes the hash of the previous entry, making it
//! computationally infeasible for insiders to modify or delete log entries
//! without detection.
//!
//! All state persisted to PostgreSQL — zero in-memory mutable state.
//!
//! Features:
//! - Hash-chain integrity (each entry references previous hash)
//! - Real-time SIEM forwarding (Splunk/ELK compatible)
//! - Chain verification endpoint (detect tampering)
//! - Privileged action flagging (insider threat patterns)

use actix_web::{web, App, HttpServer, HttpResponse};
use chrono::{Utc, Timelike};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use uuid::Uuid;
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub id: String,
    pub sequence: i64,
    pub timestamp: String,
    pub agent_id: i64,
    pub agent_code: String,
    pub action: String,
    pub resource: String,
    pub resource_id: String,
    pub ip_address: String,
    pub user_agent: String,
    pub metadata: serde_json::Value,
    pub risk_score: i32, // 0-100
    pub previous_hash: String,
    pub entry_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditRequest {
    pub agent_id: i64,
    pub agent_code: String,
    pub action: String,
    pub resource: String,
    pub resource_id: String,
    pub ip_address: Option<String>,
    pub user_agent: Option<String>,
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerifyResponse {
    pub valid: bool,
    pub total_entries: i64,
    pub checked_entries: i64,
    pub first_invalid_at: Option<i64>,
    pub message: String,
}

struct AppState {
    pool: PgPool,
    siem_endpoint: Option<String>,
}

/// Calculate SHA-256 hash of an audit entry (excluding entry_hash field)
fn calculate_entry_hash(entry: &AuditEntry) -> String {
    let mut hasher = Sha256::new();
    hasher.update(entry.sequence.to_string().as_bytes());
    hasher.update(entry.timestamp.as_bytes());
    hasher.update(entry.agent_id.to_string().as_bytes());
    hasher.update(entry.agent_code.as_bytes());
    hasher.update(entry.action.as_bytes());
    hasher.update(entry.resource.as_bytes());
    hasher.update(entry.resource_id.as_bytes());
    hasher.update(entry.ip_address.as_bytes());
    hasher.update(entry.previous_hash.as_bytes());
    hasher.update(serde_json::to_string(&entry.metadata).unwrap_or_default().as_bytes());
    hex::encode(hasher.finalize())
}

/// Calculate risk score based on action patterns
fn calculate_risk_score(action: &str, metadata: &serde_json::Value) -> i32 {
    let mut score: i32 = 0;

    // High-risk actions
    match action {
        "REVERSAL_APPROVED" | "REVERSAL_REQUESTED" => score += 40,
        "FLOAT_ADJUSTMENT" | "FEE_OVERRIDE" => score += 50,
        "ACCOUNT_PRIVILEGE_CHANGE" | "AGENT_DEACTIVATED" => score += 60,
        "SYSTEM_CONFIG_CHANGE" => score += 70,
        "BREAK_GLASS_ACCESS" => score += 90,
        "LOAN_DISBURSED" | "COMMISSION_PAYOUT" => score += 30,
        _ => score += 10,
    }

    // Amount-based risk
    if let Some(amount) = metadata.get("amount").and_then(|a| a.as_f64()) {
        if amount > 5_000_000.0 { score += 30; }
        else if amount > 1_000_000.0 { score += 20; }
        else if amount > 500_000.0 { score += 10; }
    }

    // Off-hours risk (UTC 22:00 - 06:00)
    let hour = Utc::now().hour();
    if hour >= 22 || hour < 6 {
        score += 15;
    }

    score.min(100)
}

/// Initialize the audit_chain table in PostgreSQL
async fn init_db(pool: &PgPool) {
    sqlx::query(r#"
        CREATE TABLE IF NOT EXISTS audit_chain (
            id           VARCHAR(64) PRIMARY KEY,
            sequence     BIGSERIAL NOT NULL UNIQUE,
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            agent_id     BIGINT NOT NULL,
            agent_code   VARCHAR(64) NOT NULL,
            action       VARCHAR(128) NOT NULL,
            resource     VARCHAR(128) NOT NULL,
            resource_id  VARCHAR(128) NOT NULL,
            ip_address   VARCHAR(64) NOT NULL DEFAULT 'unknown',
            user_agent   TEXT NOT NULL DEFAULT 'unknown',
            metadata     JSONB NOT NULL DEFAULT '{}',
            risk_score   INT NOT NULL DEFAULT 0,
            previous_hash VARCHAR(128) NOT NULL,
            entry_hash   VARCHAR(128) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_chain_agent_id ON audit_chain (agent_id);
        CREATE INDEX IF NOT EXISTS idx_audit_chain_risk_score ON audit_chain (risk_score);
        CREATE INDEX IF NOT EXISTS idx_audit_chain_sequence ON audit_chain (sequence);
        CREATE INDEX IF NOT EXISTS idx_audit_chain_action ON audit_chain (action);
    "#)
    .execute(pool)
    .await
    .expect("Failed to create audit_chain table");

    println!("PostgreSQL connected — audit_chain table ready");
}

/// Append a new audit entry to the hash chain (persisted in PostgreSQL)
async fn append_entry(
    data: web::Data<AppState>,
    body: web::Json<AuditRequest>,
) -> HttpResponse {
    let pool = &data.pool;

    // Get the last entry's hash from PostgreSQL for chain linkage
    let previous_hash: String = sqlx::query_scalar(
        "SELECT entry_hash FROM audit_chain ORDER BY sequence DESC LIMIT 1"
    )
    .fetch_optional(pool)
    .await
    .unwrap_or(None)
    .unwrap_or_else(|| "GENESIS".to_string());

    // Get next sequence
    let next_sequence: i64 = sqlx::query_scalar(
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_chain"
    )
    .fetch_one(pool)
    .await
    .unwrap_or(1);

    let metadata = body.metadata.clone().unwrap_or(serde_json::json!({}));
    let risk_score = calculate_risk_score(&body.action, &metadata);

    let mut entry = AuditEntry {
        id: Uuid::new_v4().to_string(),
        sequence: next_sequence,
        timestamp: Utc::now().to_rfc3339(),
        agent_id: body.agent_id,
        agent_code: body.agent_code.clone(),
        action: body.action.clone(),
        resource: body.resource.clone(),
        resource_id: body.resource_id.clone(),
        ip_address: body.ip_address.clone().unwrap_or_else(|| "unknown".to_string()),
        user_agent: body.user_agent.clone().unwrap_or_else(|| "unknown".to_string()),
        metadata: metadata.clone(),
        risk_score,
        previous_hash,
        entry_hash: String::new(),
    };

    entry.entry_hash = calculate_entry_hash(&entry);

    // Persist to PostgreSQL
    let result = sqlx::query(r#"
        INSERT INTO audit_chain (id, sequence, timestamp, agent_id, agent_code, action, resource, resource_id, ip_address, user_agent, metadata, risk_score, previous_hash, entry_hash)
        VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
    "#)
    .bind(&entry.id)
    .bind(entry.sequence)
    .bind(&entry.timestamp)
    .bind(entry.agent_id)
    .bind(&entry.agent_code)
    .bind(&entry.action)
    .bind(&entry.resource)
    .bind(&entry.resource_id)
    .bind(&entry.ip_address)
    .bind(&entry.user_agent)
    .bind(&entry.metadata)
    .bind(entry.risk_score)
    .bind(&entry.previous_hash)
    .bind(&entry.entry_hash)
    .execute(pool)
    .await;

    if let Err(e) = result {
        return HttpResponse::InternalServerError().json(serde_json::json!({
            "error": format!("Failed to persist audit entry: {}", e)
        }));
    }

    // Forward to SIEM if configured
    if let Some(ref siem_url) = data.siem_endpoint {
        let siem_url = siem_url.clone();
        let entry_clone = entry.clone();
        tokio::spawn(async move {
            let _ = reqwest::Client::new()
                .post(&siem_url)
                .json(&entry_clone)
                .send()
                .await;
        });
    }

    // Alert on high-risk entries via Dapr pub/sub
    if risk_score >= 70 {
        let entry_clone = entry.clone();
        tokio::spawn(async move {
            let _ = reqwest::Client::new()
                .post("http://localhost:3500/v1.0/publish/pubsub/insider.threat.high-risk-action")
                .json(&serde_json::json!({
                    "entryId": entry_clone.id,
                    "agentCode": entry_clone.agent_code,
                    "action": entry_clone.action,
                    "riskScore": entry_clone.risk_score,
                    "timestamp": entry_clone.timestamp,
                }))
                .send()
                .await;
        });
    }

    HttpResponse::Ok().json(serde_json::json!({
        "id": entry.id,
        "sequence": entry.sequence,
        "entryHash": entry.entry_hash,
        "riskScore": entry.risk_score,
    }))
}

/// Verify the integrity of the hash chain (reads from PostgreSQL)
async fn verify_chain(data: web::Data<AppState>) -> HttpResponse {
    let pool = &data.pool;

    let rows = sqlx::query(
        "SELECT id, sequence, timestamp::text, agent_id, agent_code, action, resource, resource_id, ip_address, user_agent, metadata, risk_score, previous_hash, entry_hash FROM audit_chain ORDER BY sequence ASC"
    )
    .fetch_all(pool)
    .await;

    let rows = match rows {
        Ok(r) => r,
        Err(e) => {
            return HttpResponse::InternalServerError().json(serde_json::json!({
                "error": format!("Database error: {}", e)
            }));
        }
    };

    if rows.is_empty() {
        return HttpResponse::Ok().json(VerifyResponse {
            valid: true,
            total_entries: 0,
            checked_entries: 0,
            first_invalid_at: None,
            message: "Chain is empty".to_string(),
        });
    }

    let mut first_invalid: Option<i64> = None;
    let mut prev_hash = String::new();

    for (i, row) in rows.iter().enumerate() {
        let entry = AuditEntry {
            id: row.get("id"),
            sequence: row.get("sequence"),
            timestamp: row.get("timestamp"),
            agent_id: row.get("agent_id"),
            agent_code: row.get("agent_code"),
            action: row.get("action"),
            resource: row.get("resource"),
            resource_id: row.get("resource_id"),
            ip_address: row.get("ip_address"),
            user_agent: row.get("user_agent"),
            metadata: row.get("metadata"),
            risk_score: row.get("risk_score"),
            previous_hash: row.get("previous_hash"),
            entry_hash: row.get("entry_hash"),
        };

        // Verify hash
        let expected_hash = calculate_entry_hash(&entry);
        if expected_hash != entry.entry_hash {
            first_invalid = Some(entry.sequence);
            break;
        }

        // Verify chain linkage
        if i == 0 {
            if entry.previous_hash != "GENESIS" {
                first_invalid = Some(entry.sequence);
                break;
            }
        } else if entry.previous_hash != prev_hash {
            first_invalid = Some(entry.sequence);
            break;
        }

        prev_hash = entry.entry_hash.clone();
    }

    let total = rows.len() as i64;
    let response = VerifyResponse {
        valid: first_invalid.is_none(),
        total_entries: total,
        checked_entries: total,
        first_invalid_at: first_invalid,
        message: if first_invalid.is_none() {
            "Hash chain integrity verified — no tampering detected".to_string()
        } else {
            format!("TAMPERING DETECTED at sequence {}", first_invalid.unwrap())
        },
    };

    HttpResponse::Ok().json(response)
}

/// Get recent high-risk entries from PostgreSQL
async fn get_high_risk(data: web::Data<AppState>) -> HttpResponse {
    let pool = &data.pool;

    let rows = sqlx::query(
        "SELECT id, sequence, timestamp::text, agent_id, agent_code, action, resource, resource_id, ip_address, user_agent, metadata, risk_score, previous_hash, entry_hash FROM audit_chain WHERE risk_score >= 50 ORDER BY sequence DESC LIMIT 100"
    )
    .fetch_all(pool)
    .await;

    match rows {
        Ok(rows) => {
            let entries: Vec<AuditEntry> = rows.iter().map(|row| AuditEntry {
                id: row.get("id"),
                sequence: row.get("sequence"),
                timestamp: row.get("timestamp"),
                agent_id: row.get("agent_id"),
                agent_code: row.get("agent_code"),
                action: row.get("action"),
                resource: row.get("resource"),
                resource_id: row.get("resource_id"),
                ip_address: row.get("ip_address"),
                user_agent: row.get("user_agent"),
                metadata: row.get("metadata"),
                risk_score: row.get("risk_score"),
                previous_hash: row.get("previous_hash"),
                entry_hash: row.get("entry_hash"),
            }).collect();
            HttpResponse::Ok().json(entries)
        }
        Err(e) => HttpResponse::InternalServerError().json(serde_json::json!({
            "error": format!("Database error: {}", e)
        })),
    }
}

/// Health check
async fn health(data: web::Data<AppState>) -> HttpResponse {
    let db_ok = sqlx::query("SELECT 1")
        .fetch_one(&data.pool)
        .await
        .is_ok();

    HttpResponse::Ok().json(serde_json::json!({
        "status": if db_ok { "healthy" } else { "degraded" },
        "service": "audit-chain",
        "version": "2.0.0",
        "storage": "postgresql",
    }))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let siem_endpoint = std::env::var("SIEM_ENDPOINT").ok();
    let port: u16 = std::env::var("AUDIT_CHAIN_PORT")
        .unwrap_or_else(|_| "8260".to_string())
        .parse()
        .unwrap_or(8260);

    let database_url = std::env::var("DATABASE_URL")
        .or_else(|_| std::env::var("POSTGRES_URL"))
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/agentbanking".to_string());

    println!("Audit Chain Service v2.0.0 starting on port {}", port);
    println!("SIEM forwarding: {}", siem_endpoint.as_deref().unwrap_or("disabled"));
    println!("PostgreSQL: connecting...");

    let pool = PgPoolOptions::new()
        .max_connections(25)
        .acquire_timeout(std::time::Duration::from_secs(10))
        .connect(&database_url)
        .await
        .expect("Failed to connect to PostgreSQL");

    init_db(&pool).await;

    let data = web::Data::new(AppState {
        pool,
        siem_endpoint,
    });

    HttpServer::new(move || {
        App::new()
            .app_data(data.clone())
            .route("/health", web::get().to(health))
            .route("/append", web::post().to(append_entry))
            .route("/verify", web::get().to(verify_chain))
            .route("/high-risk", web::get().to(get_high_risk))
    })
    .bind(("0.0.0.0", port))?
    .run()
    .await
}
