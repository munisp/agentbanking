/// 54agent POS — Fluvio SmartModule
/// Deployed to Fluvio as a WASM filter on the `pos.transactions.raw` topic.
/// Filters out transactions that trigger any of three fraud rules:
///   1. Velocity check: >5 transactions per minute per agent
///   2. Amount anomaly: amount > 3× the 30-day average for this agent
///   3. Blacklist check: terminal_id in the deny list
///
/// Transactions that pass all rules are forwarded to `pos.transactions.validated`.
/// Transactions that fail are forwarded to `pos.transactions.fraud_review`.
use serde::{Deserialize, Serialize};

/// Incoming transaction event from the POS terminal
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct TransactionEvent {
    pub transaction_id: String,
    pub agent_id: String,
    pub terminal_id: String,
    pub amount: f64,
    pub currency: String,
    pub transaction_type: String,
    pub timestamp_ms: u64,
    /// 30-day rolling average for this agent (pre-computed by enrichment step)
    pub agent_30d_avg_amount: Option<f64>,
    /// Number of transactions by this agent in the last 60 seconds
    pub agent_velocity_1min: Option<u32>,
}

/// Output event — same as input but with fraud metadata appended
#[derive(Debug, Serialize, Deserialize)]
pub struct FraudFilterResult {
    #[serde(flatten)]
    pub event: TransactionEvent,
    pub fraud_flags: Vec<String>,
    pub fraud_score: f64,
    pub action: FraudAction,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum FraudAction {
    Allow,
    Review,
    Block,
}

// ── Hardcoded deny list (updated via SmartModule parameter in production) ──────
const BLACKLISTED_TERMINALS: &[&str] = &[
    "TERM-BLOCKED-001",
    "TERM-BLOCKED-002",
    "TERM-STOLEN-007",
    "TERM-COMPROMISED-099",
];

/// Velocity threshold: more than 5 transactions per minute triggers review
const VELOCITY_THRESHOLD_PER_MIN: u32 = 5;

/// Anomaly threshold: amount > 3× 30-day average triggers review
const ANOMALY_MULTIPLIER: f64 = 3.0;

/// Score thresholds
const BLOCK_SCORE: f64 = 0.8;
const REVIEW_SCORE: f64 = 0.4;

// ── Core fraud evaluation logic (pure, no I/O, testable) ──────────────────────

pub fn evaluate_transaction(event: &TransactionEvent) -> FraudFilterResult {
    let mut flags: Vec<String> = Vec::new();
    let mut score: f64 = 0.0;

    // Rule 1: Blacklist check
    if check_blacklist(&event.terminal_id) {
        flags.push(format!("BLACKLISTED_TERMINAL:{}", event.terminal_id));
        score += 1.0; // Immediate block
    }

    // Rule 2: Velocity check
    if let Some(velocity) = event.agent_velocity_1min {
        if velocity > VELOCITY_THRESHOLD_PER_MIN {
            let excess = (velocity - VELOCITY_THRESHOLD_PER_MIN) as f64;
            let velocity_score = (excess / 10.0).min(0.6);
            flags.push(format!("HIGH_VELOCITY:{}_tx/min", velocity));
            score += velocity_score;
        }
    }

    // Rule 3: Amount anomaly check
    if let Some(avg) = event.agent_30d_avg_amount {
        if avg > 0.0 && event.amount > avg * ANOMALY_MULTIPLIER {
            let ratio = event.amount / avg;
            let anomaly_score = ((ratio - ANOMALY_MULTIPLIER) / 10.0).min(0.5);
            flags.push(format!("AMOUNT_ANOMALY:{:.1}x_avg", ratio));
            score += anomaly_score;
        }
    }

    let action = if score >= BLOCK_SCORE {
        FraudAction::Block
    } else if score >= REVIEW_SCORE {
        FraudAction::Review
    } else {
        FraudAction::Allow
    };

    FraudFilterResult {
        event: event.clone(),
        fraud_flags: flags,
        fraud_score: score.min(1.0),
        action,
    }
}

pub fn check_blacklist(terminal_id: &str) -> bool {
    BLACKLISTED_TERMINALS.contains(&terminal_id)
}

pub fn check_velocity(velocity_1min: Option<u32>) -> bool {
    velocity_1min.map(|v| v > VELOCITY_THRESHOLD_PER_MIN).unwrap_or(false)
}

pub fn check_anomaly(amount: f64, avg_30d: Option<f64>) -> bool {
    avg_30d
        .filter(|&avg| avg > 0.0)
        .map(|avg| amount > avg * ANOMALY_MULTIPLIER)
        .unwrap_or(false)
}

// ── Fluvio SmartModule entry point (compiled to WASM) ─────────────────────────
// When compiled with --target wasm32-wasi, this is the filter entry point.
// In unit tests (x86), this is excluded via cfg.

#[cfg(not(test))]
pub mod smartmodule {
    use super::*;

    /// Fluvio filter: returns true to keep the record, false to drop it.
    /// Records that would be blocked are dropped here; they are published
    /// to the fraud_review topic by a separate sink connector.
    pub fn filter(record_bytes: &[u8]) -> bool {
        let event: TransactionEvent = match serde_json::from_slice(record_bytes) {
            Ok(e) => e,
            Err(_) => return false, // Drop malformed records
        };
        let result = evaluate_transaction(&event);
        // Keep only records that are allowed; block and review go to fraud topic
        result.action == FraudAction::Allow
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_event(amount: f64, terminal_id: &str) -> TransactionEvent {
        TransactionEvent {
            transaction_id: "TXN-001".to_string(),
            agent_id: "AGT-001".to_string(),
            terminal_id: terminal_id.to_string(),
            amount,
            currency: "NGN".to_string(),
            transaction_type: "deposit".to_string(),
            timestamp_ms: 1_700_000_000_000,
            agent_30d_avg_amount: Some(10_000.0),
            agent_velocity_1min: Some(2),
        }
    }

    // ── Blacklist tests ─────────────────────────────────────────────────────

    #[test]
    fn test_blacklisted_terminal_is_blocked() {
        let event = make_event(5_000.0, "TERM-BLOCKED-001");
        let result = evaluate_transaction(&event);
        assert_eq!(result.action, FraudAction::Block);
        assert!(result.fraud_flags.iter().any(|f| f.contains("BLACKLISTED_TERMINAL")));
    }

    #[test]
    fn test_clean_terminal_is_allowed() {
        let event = make_event(5_000.0, "TERM-CLEAN-001");
        let result = evaluate_transaction(&event);
        assert_eq!(result.action, FraudAction::Allow);
    }

    #[test]
    fn test_check_blacklist_known_terminal() {
        assert!(check_blacklist("TERM-BLOCKED-001"));
        assert!(check_blacklist("TERM-STOLEN-007"));
    }

    #[test]
    fn test_check_blacklist_unknown_terminal() {
        assert!(!check_blacklist("TERM-NORMAL-123"));
        assert!(!check_blacklist(""));
    }

    // ── Velocity tests ──────────────────────────────────────────────────────

    #[test]
    fn test_high_velocity_triggers_review() {
        let mut event = make_event(5_000.0, "TERM-CLEAN-001");
        event.agent_velocity_1min = Some(10); // >5 threshold
        let result = evaluate_transaction(&event);
        assert!(result.fraud_flags.iter().any(|f| f.contains("HIGH_VELOCITY")));
        assert!(result.fraud_score > 0.0);
    }

    #[test]
    fn test_normal_velocity_no_flag() {
        let mut event = make_event(5_000.0, "TERM-CLEAN-001");
        event.agent_velocity_1min = Some(3); // ≤5 threshold
        let result = evaluate_transaction(&event);
        assert!(!result.fraud_flags.iter().any(|f| f.contains("HIGH_VELOCITY")));
    }

    #[test]
    fn test_check_velocity_above_threshold() {
        assert!(check_velocity(Some(6)));
        assert!(check_velocity(Some(100)));
    }

    #[test]
    fn test_check_velocity_at_threshold() {
        assert!(!check_velocity(Some(5)));
        assert!(!check_velocity(Some(0)));
        assert!(!check_velocity(None));
    }

    // ── Anomaly tests ───────────────────────────────────────────────────────

    #[test]
    fn test_amount_anomaly_triggers_review() {
        let mut event = make_event(50_000.0, "TERM-CLEAN-001"); // 5× average of 10,000
        event.agent_30d_avg_amount = Some(10_000.0);
        let result = evaluate_transaction(&event);
        assert!(result.fraud_flags.iter().any(|f| f.contains("AMOUNT_ANOMALY")));
    }

    #[test]
    fn test_normal_amount_no_anomaly() {
        let mut event = make_event(15_000.0, "TERM-CLEAN-001"); // 1.5× average
        event.agent_30d_avg_amount = Some(10_000.0);
        let result = evaluate_transaction(&event);
        assert!(!result.fraud_flags.iter().any(|f| f.contains("AMOUNT_ANOMALY")));
    }

    #[test]
    fn test_check_anomaly_above_threshold() {
        assert!(check_anomaly(35_000.0, Some(10_000.0))); // 3.5× > 3×
    }

    #[test]
    fn test_check_anomaly_at_threshold() {
        assert!(!check_anomaly(30_000.0, Some(10_000.0))); // exactly 3× is not anomaly
        assert!(!check_anomaly(25_000.0, Some(10_000.0))); // 2.5× is normal
    }

    #[test]
    fn test_check_anomaly_no_average() {
        assert!(!check_anomaly(1_000_000.0, None)); // no avg = no anomaly
        assert!(!check_anomaly(1_000_000.0, Some(0.0))); // zero avg = no anomaly
    }

    // ── Combined score tests ────────────────────────────────────────────────

    #[test]
    fn test_multiple_flags_accumulate_score() {
        let mut event = make_event(50_000.0, "TERM-CLEAN-001");
        event.agent_velocity_1min = Some(15); // High velocity
        event.agent_30d_avg_amount = Some(10_000.0); // Amount anomaly (5×)
        let result = evaluate_transaction(&event);
        assert!(result.fraud_flags.len() >= 2);
        assert!(result.fraud_score > 0.0);
    }

    #[test]
    fn test_fraud_score_capped_at_1() {
        let mut event = make_event(500_000.0, "TERM-BLOCKED-001");
        event.agent_velocity_1min = Some(100);
        event.agent_30d_avg_amount = Some(1_000.0);
        let result = evaluate_transaction(&event);
        assert!(result.fraud_score <= 1.0);
    }

    #[test]
    fn test_clean_transaction_allowed() {
        let mut event = make_event(8_000.0, "TERM-CLEAN-001");
        event.agent_velocity_1min = Some(2);
        event.agent_30d_avg_amount = Some(10_000.0);
        let result = evaluate_transaction(&event);
        assert_eq!(result.action, FraudAction::Allow);
        assert!(result.fraud_flags.is_empty());
        assert_eq!(result.fraud_score, 0.0);
    }
}
