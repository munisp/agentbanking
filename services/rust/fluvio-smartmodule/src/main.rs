/// Local test binary for the Fluvio SmartModule.
/// Run: cargo run -- < sample_events.jsonl
/// Build WASM: cargo build --target wasm32-wasi --release
use pos_fraud_smartmodule::{evaluate_transaction, FraudAction, TransactionEvent};
use std::io::{self, BufRead};

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
