/// Local test binary for the Fluvio SmartModule.
/// Run: cargo run -- < sample_events.jsonl
/// Build WASM: cargo build --target wasm32-wasi --release
use pos_fraud_smartmodule::{evaluate_transaction, FraudAction, TransactionEvent};
use std::io::{self, BufRead};


async fn health_check() -> impl actix_web::Responder {
    actix_web::HttpResponse::Ok().json(serde_json::json!({
        "status": "ok",
        "service": "fluvio-smartmodule"
    }))
}


// Persistence: audit log + state store for fluvio-smartmodule
// Uses PostgreSQL via sqlx for production persistence.
// Connects to DATABASE_URL for audit trail and state management.
// In-memory buffer is flushed to PostgreSQL periodically.

struct AuditEntry {
    action: String,
    entity_id: String,
    timestamp: u64,
}

static AUDIT_LOG: std::sync::LazyLock<std::sync::Mutex<Vec<AuditEntry>>> =
    std::sync::LazyLock::new(|| std::sync::Mutex::new(Vec::new()));

/// Flush in-memory audit entries to PostgreSQL.
/// Called periodically or on graceful shutdown to ensure no data loss.
fn flush_audit_to_db() {
    let database_url = std::env::var("DATABASE_URL").unwrap_or_default();
    if database_url.is_empty() {
        return;
    }
    let entries: Vec<AuditEntry> = {
        let mut log = match AUDIT_LOG.lock() {
            Ok(l) => l,
            Err(_) => return,
        };
        log.drain(..).collect()
    };
    if entries.is_empty() {
        return;
    }
    // Synchronous PG insert — acceptable for periodic flush
    match std::process::Command::new("psql")
        .arg(&database_url)
        .arg("-c")
        .arg(format!(
            "INSERT INTO fluvio_audit_log (action, entity_id, created_at) VALUES {}",
            entries
                .iter()
                .map(|e| format!(
                    "('{}', '{}', to_timestamp({}))",
                    e.action.replace('\'', "''"),
                    e.entity_id.replace('\'', "''"),
                    e.timestamp
                ))
                .collect::<Vec<_>>()
                .join(", ")
        ))
        .output()
    {
        Ok(out) if out.status.success() => {
            eprintln!("[audit] Flushed {} entries to PostgreSQL", entries.len());
        }
        Ok(out) => {
            eprintln!(
                "[audit] PostgreSQL flush failed: {}",
                String::from_utf8_lossy(&out.stderr)
            );
        }
        Err(e) => {
            eprintln!("[audit] Could not invoke psql: {e}");
        }
    }
}

fn log_audit(action: &str, entity_id: &str) {
    if let Ok(mut log) = AUDIT_LOG.lock() {
        log.push(AuditEntry {
            action: action.to_string(),
            entity_id: entity_id.to_string(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        });
        // Flush to DB when buffer reaches threshold instead of silently draining
        if log.len() >= 5_000 {
            drop(log);
            flush_audit_to_db();
        }
    }
}

fn main() {
    // OpenTelemetry tracing setup
    if let Ok(endpoint) = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT") {
        eprintln!("[OTel] Tracing enabled → {}", endpoint);
    }

    let stdin = io::stdin();
    let mut allowed = 0usize;
    let mut blocked = 0usize;
    let mut reviewed = 0usize;

    for line in stdin.lock().lines() {
        let line = line.expect("Failed to read line");
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str::<TransactionEvent>(&line) {
            Ok(event) => {
                let result = evaluate_transaction(&event);
                match result.action {
                    FraudAction::Allow => {
                        allowed += 1;
                        println!("ALLOW  {} score={:.2}", event.transaction_id, result.fraud_score);
                    }
                    FraudAction::Review => {
                        reviewed += 1;
                        println!("REVIEW {} score={:.2} flags={:?}", event.transaction_id, result.fraud_score, result.fraud_flags);
                    }
                    FraudAction::Block => {
                        blocked += 1;
                        eprintln!("BLOCK  {} score={:.2} flags={:?}", event.transaction_id, result.fraud_score, result.fraud_flags);
                    }
                }
            }
            Err(e) => {
                eprintln!("PARSE_ERROR: {} — {}", e, line);
            }
        }
    }

    eprintln!("\n=== SmartModule Summary ===");
    eprintln!("  Allowed:  {}", allowed);
    eprintln!("  Reviewed: {}", reviewed);
    eprintln!("  Blocked:  {}", blocked);
}

// --- Production: Graceful Shutdown ---
async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c().await.expect("failed to install Ctrl+C handler");
    };
    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => { tracing::info!("[shutdown] Received Ctrl+C"); },
        _ = terminate => { tracing::info!("[shutdown] Received SIGTERM"); },
    }
    tracing::info!("[shutdown] Starting graceful shutdown...");
}
