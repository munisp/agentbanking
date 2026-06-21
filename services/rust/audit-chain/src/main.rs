//! Cryptographic Audit Chain Service
//!
//! Provides tamper-proof audit logging using SHA-256 hash chains.
//! Each audit entry includes the hash of the previous entry, making it
//! computationally infeasible for insiders to modify or delete log entries
//! without detection.
//!
//! Features:
//! - Hash-chain integrity (each entry references previous hash)
//! - Real-time SIEM forwarding (Splunk/ELK compatible)
//! - Chain verification endpoint (detect tampering)
//! - Privileged action flagging (insider threat patterns)

use actix_web::{web, App, HttpServer, HttpResponse, middleware};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::sync::Mutex;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub id: String,
    pub sequence: u64,
    pub timestamp: String,
    pub agent_id: i64,
    pub agent_code: String,
    pub action: String,
    pub resource: String,
    pub resource_id: String,
    pub ip_address: String,
    pub user_agent: String,
    pub metadata: serde_json::Value,
    pub risk_score: u8, // 0-100
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
    pub total_entries: u64,
    pub checked_entries: u64,
    pub first_invalid_at: Option<u64>,
    pub message: String,
}

struct AppState {
    chain: Mutex<Vec<AuditEntry>>,
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
fn calculate_risk_score(action: &str, metadata: &serde_json::Value) -> u8 {
    let mut score: u8 = 0;

    // High-risk actions
    match action {
        "REVERSAL_APPROVED" | "REVERSAL_REQUESTED" => score = score.saturating_add(40),
        "FLOAT_ADJUSTMENT" | "FEE_OVERRIDE" => score = score.saturating_add(50),
        "ACCOUNT_PRIVILEGE_CHANGE" | "AGENT_DEACTIVATED" => score = score.saturating_add(60),
        "SYSTEM_CONFIG_CHANGE" => score = score.saturating_add(70),
        "BREAK_GLASS_ACCESS" => score = score.saturating_add(90),
        "LOAN_DISBURSED" | "COMMISSION_PAYOUT" => score = score.saturating_add(30),
        _ => score = score.saturating_add(10),
    }

    // Amount-based risk
    if let Some(amount) = metadata.get("amount").and_then(|a| a.as_f64()) {
        if amount > 5_000_000.0 { score = score.saturating_add(30); }
        else if amount > 1_000_000.0 { score = score.saturating_add(20); }
        else if amount > 500_000.0 { score = score.saturating_add(10); }
    }

    // Off-hours risk (UTC 22:00 - 06:00)
    let hour = Utc::now().hour();
    if hour >= 22 || hour < 6 {
        score = score.saturating_add(15);
    }

    score.min(100)
}

/// Append a new audit entry to the hash chain
async fn append_entry(
    data: web::Data<AppState>,
    body: web::Json<AuditRequest>,
) -> HttpResponse {
    let mut chain = data.chain.lock().unwrap();

    let previous_hash = chain.last()
        .map(|e| e.entry_hash.clone())
        .unwrap_or_else(|| "GENESIS".to_string());

    let sequence = chain.len() as u64 + 1;
    let metadata = body.metadata.clone().unwrap_or(serde_json::json!({}));
    let risk_score = calculate_risk_score(&body.action, &metadata);

    let mut entry = AuditEntry {
        id: Uuid::new_v4().to_string(),
        sequence,
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
    chain.push(entry.clone());

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

    // Alert on high-risk entries
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

/// Verify the integrity of the hash chain
async fn verify_chain(data: web::Data<AppState>) -> HttpResponse {
    let chain = data.chain.lock().unwrap();

    if chain.is_empty() {
        return HttpResponse::Ok().json(VerifyResponse {
            valid: true,
            total_entries: 0,
            checked_entries: 0,
            first_invalid_at: None,
            message: "Chain is empty".to_string(),
        });
    }

    let mut first_invalid: Option<u64> = None;

    for (i, entry) in chain.iter().enumerate() {
        // Verify hash
        let expected_hash = calculate_entry_hash(entry);
        if expected_hash != entry.entry_hash {
            first_invalid = Some(entry.sequence);
            break;
        }

        // Verify chain linkage
        if i > 0 {
            let prev = &chain[i - 1];
            if entry.previous_hash != prev.entry_hash {
                first_invalid = Some(entry.sequence);
                break;
            }
        } else if entry.previous_hash != "GENESIS" {
            first_invalid = Some(entry.sequence);
            break;
        }
    }

    let response = VerifyResponse {
        valid: first_invalid.is_none(),
        total_entries: chain.len() as u64,
        checked_entries: chain.len() as u64,
        first_invalid_at: first_invalid,
        message: if first_invalid.is_none() {
            "Hash chain integrity verified — no tampering detected".to_string()
        } else {
            format!("TAMPERING DETECTED at sequence {}", first_invalid.unwrap())
        },
    };

    HttpResponse::Ok().json(response)
}

/// Get recent high-risk entries
async fn get_high_risk(data: web::Data<AppState>) -> HttpResponse {
    let chain = data.chain.lock().unwrap();
    let high_risk: Vec<&AuditEntry> = chain.iter()
        .rev()
        .filter(|e| e.risk_score >= 50)
        .take(100)
        .collect();

    HttpResponse::Ok().json(high_risk)
}

/// Health check
async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "audit-chain",
        "version": "1.0.0",
    }))
}

use chrono::Timelike;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let siem_endpoint = std::env::var("SIEM_ENDPOINT").ok();
    let port: u16 = std::env::var("AUDIT_CHAIN_PORT")
        .unwrap_or_else(|_| "8260".to_string())
        .parse()
        .unwrap_or(8260);

    println!("Audit Chain Service starting on port {}", port);
    println!("SIEM forwarding: {}", siem_endpoint.as_deref().unwrap_or("disabled"));

    let data = web::Data::new(AppState {
        chain: Mutex::new(Vec::new()),
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
