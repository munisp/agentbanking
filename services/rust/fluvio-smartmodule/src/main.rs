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

fn main() {
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
