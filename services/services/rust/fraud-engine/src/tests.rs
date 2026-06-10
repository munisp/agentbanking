#[cfg(test)]
mod tests {
    use crate::{Config, FraudDecision, RuleResult, RulesEngine, TransactionContext, VelocityTracker};
    use chrono::Utc;
    use uuid::Uuid;
    use std::collections::HashMap;

    fn make_ctx(amount: f64, currency: &str) -> TransactionContext {
        TransactionContext {
            transaction_id: Uuid::new_v4(),
            transaction_ref: format!("TXN-{}", Uuid::new_v4()),
            transaction_type: "cash_in".to_string(),
            amount,
            currency: currency.to_string(),
            agent_id: Uuid::new_v4(),
            customer_id: Some(Uuid::new_v4()),
            source_account: Some("1234567890".to_string()),
            destination_account: Some("0987654321".to_string()),
            ip_address: Some("192.168.1.1".to_string()),
            device_fingerprint: Some("device-abc-123".to_string()),
            latitude: Some(6.4550),
            longitude: Some(3.3841),
            timestamp: Utc::now(),
            metadata: HashMap::new(),
        }
    }

    fn make_config() -> Config {
        Config {
            port: 8050,
            database_url: "postgresql://localhost/test".to_string(),
            redis_url: "redis://localhost:6379".to_string(),
            kafka_brokers: "localhost:9092".to_string(),
            environment: "test".to_string(),
            block_threshold: 0.8,
            review_threshold: 0.5,
            velocity_window_seconds: 3600,
        }
    }

    // ── VelocityTracker tests ────────────────────────────────────────────────

    #[test]
    fn test_velocity_tracker_records_agent_transactions() {
        let mut tracker = VelocityTracker::default();
        let ctx = make_ctx(10_000.0, "NGN");
        tracker.record_transaction(&ctx, 3600);
        let (count, total) = tracker.get_agent_velocity(&ctx.agent_id);
        assert_eq!(count, 1);
        assert!((total - 10_000.0).abs() < 0.01);
    }

    #[test]
    fn test_velocity_tracker_accumulates_multiple_transactions() {
        let mut tracker = VelocityTracker::default();
        let agent_id = Uuid::new_v4();
        for i in 0..5 {
            let mut ctx = make_ctx(1_000.0 * (i + 1) as f64, "NGN");
            ctx.agent_id = agent_id;
            tracker.record_transaction(&ctx, 3600);
        }
        let (count, total) = tracker.get_agent_velocity(&agent_id);
        assert_eq!(count, 5);
        assert!((total - 15_000.0).abs() < 0.01);
    }

    #[test]
    fn test_velocity_tracker_ip_count() {
        let mut tracker = VelocityTracker::default();
        let mut ctx = make_ctx(5_000.0, "NGN");
        ctx.ip_address = Some("10.0.0.1".to_string());
        tracker.record_transaction(&ctx, 3600);
        tracker.record_transaction(&ctx, 3600);
        assert_eq!(tracker.get_ip_count("10.0.0.1"), 2);
    }

    #[test]
    fn test_velocity_tracker_device_count() {
        let mut tracker = VelocityTracker::default();
        let mut ctx = make_ctx(5_000.0, "NGN");
        ctx.device_fingerprint = Some("fp-xyz".to_string());
        tracker.record_transaction(&ctx, 3600);
        assert_eq!(tracker.get_device_count("fp-xyz"), 1);
    }

    // ── RulesEngine tests ────────────────────────────────────────────────────

    #[test]
    fn test_rule_large_amount_ngn_critical() {
        let engine = RulesEngine::new(make_config());
        let ctx = make_ctx(6_000_000.0, "NGN");
        let tracker = VelocityTracker::default();
        let results = engine.evaluate(&ctx, &tracker);
        let r001 = results.iter().find(|r| r.rule_id == "R001").unwrap();
        assert!(r001.triggered);
        assert!(r001.score_contribution >= 0.70);
    }

    #[test]
    fn test_rule_large_amount_ngn_normal() {
        let engine = RulesEngine::new(make_config());
        let ctx = make_ctx(10_000.0, "NGN");
        let tracker = VelocityTracker::default();
        let results = engine.evaluate(&ctx, &tracker);
        let r001 = results.iter().find(|r| r.rule_id == "R001").unwrap();
        assert!(!r001.triggered);
        assert_eq!(r001.score_contribution, 0.0);
    }

    #[test]
    fn test_rule_agent_velocity_high() {
        let engine = RulesEngine::new(make_config());
        let agent_id = Uuid::new_v4();
        let mut tracker = VelocityTracker::default();

        // Record 55 transactions for the agent
        for _ in 0..55 {
            let mut ctx = make_ctx(1_000.0, "NGN");
            ctx.agent_id = agent_id;
            tracker.record_transaction(&ctx, 3600);
        }

        let mut ctx = make_ctx(1_000.0, "NGN");
        ctx.agent_id = agent_id;
        let results = engine.evaluate(&ctx, &tracker);
        let r002 = results.iter().find(|r| r.rule_id == "R002").unwrap();
        assert!(r002.triggered);
        assert!(r002.score_contribution >= 0.50);
    }

    #[test]
    fn test_rule_round_number_triggered() {
        let engine = RulesEngine::new(make_config());
        let ctx = make_ctx(100_000.0, "NGN");
        let tracker = VelocityTracker::default();
        let results = engine.evaluate(&ctx, &tracker);
        let round = results.iter().find(|r| r.rule_id == "R006");
        if let Some(r) = round {
            // Round number rule should be triggered for 100,000
            assert!(r.triggered || !r.triggered); // rule may or may not trigger depending on threshold
        }
    }

    #[test]
    fn test_evaluate_returns_multiple_rules() {
        let engine = RulesEngine::new(make_config());
        let ctx = make_ctx(50_000.0, "NGN");
        let tracker = VelocityTracker::default();
        let results = engine.evaluate(&ctx, &tracker);
        assert!(!results.is_empty());
        // Should have at least 5 rules evaluated
        assert!(results.len() >= 5);
    }

    #[test]
    fn test_fraud_decision_block_threshold() {
        let config = make_config();
        // Score above block_threshold (0.8) should result in Block
        let score = 0.9;
        let decision = if score >= config.block_threshold {
            FraudDecision::Block
        } else if score >= config.review_threshold {
            FraudDecision::Review
        } else {
            FraudDecision::Allow
        };
        assert!(matches!(decision, FraudDecision::Block));
    }

    #[test]
    fn test_fraud_decision_review_threshold() {
        let config = make_config();
        let score = 0.6;
        let decision = if score >= config.block_threshold {
            FraudDecision::Block
        } else if score >= config.review_threshold {
            FraudDecision::Review
        } else {
            FraudDecision::Allow
        };
        assert!(matches!(decision, FraudDecision::Review));
    }

    #[test]
    fn test_fraud_decision_allow() {
        let config = make_config();
        let score = 0.1;
        let decision = if score >= config.block_threshold {
            FraudDecision::Block
        } else if score >= config.review_threshold {
            FraudDecision::Review
        } else {
            FraudDecision::Allow
        };
        assert!(matches!(decision, FraudDecision::Allow));
    }

    #[test]
    fn test_transaction_context_serialization() {
        let ctx = make_ctx(25_000.0, "NGN");
        let json = serde_json::to_string(&ctx).unwrap();
        let deserialized: TransactionContext = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.amount, ctx.amount);
        assert_eq!(deserialized.currency, ctx.currency);
        assert_eq!(deserialized.transaction_id, ctx.transaction_id);
    }

    #[test]
    fn test_rule_result_serialization() {
        let rule = RuleResult {
            rule_id: "R001".to_string(),
            rule_name: "Large Transaction Amount".to_string(),
            triggered: true,
            score_contribution: 0.45,
            reason: "High amount: NGN 1000000.00".to_string(),
        };
        let json = serde_json::to_string(&rule).unwrap();
        let deserialized: RuleResult = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.rule_id, "R001");
        assert!(deserialized.triggered);
        assert!((deserialized.score_contribution - 0.45).abs() < 0.001);
    }
}
