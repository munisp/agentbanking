#[cfg(test)]
mod tests {
    use crate::{Config, ValidationRequest, ValidationStatus, Validator};
    use uuid::Uuid;

    fn make_config() -> Config {
        Config {
            port: 8070,
            environment: "test".to_string(),
            single_tx_limit_tier1: 20_000.0,
            single_tx_limit_tier2: 100_000.0,
            single_tx_limit_tier3: 500_000.0,
            daily_limit_tier1: 100_000.0,
            daily_limit_tier2: 500_000.0,
            daily_limit_tier3: 2_000_000.0,
        }
    }

    fn make_request(amount: f64, currency: &str, tx_type: &str) -> ValidationRequest {
        ValidationRequest {
            transaction_id: Uuid::new_v4(),
            transaction_type: tx_type.to_string(),
            amount,
            currency: currency.to_string(),
            agent_id: Uuid::new_v4(),
            agent_tier: Some("tier1".to_string()),
            customer_id: Some(Uuid::new_v4()),
            customer_tier: Some("tier1".to_string()),
            source_account: Some("1234567890".to_string()),
            destination_account: Some("0987654321".to_string()),
            daily_total_so_far: Some(0.0),
            metadata: None,
        }
    }

    #[test]
    fn test_valid_transaction_passes() {
        let validator = Validator::new(make_config());
        let req = make_request(5_000.0, "NGN", "deposit");
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Approved));
        assert!(result.errors.is_empty());
    }

    #[test]
    fn test_negative_amount_fails() {
        let validator = Validator::new(make_config());
        let req = make_request(-100.0, "NGN", "deposit");
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "INVALID_AMOUNT"));
    }

    #[test]
    fn test_zero_amount_fails() {
        let validator = Validator::new(make_config());
        let req = make_request(0.0, "NGN", "deposit");
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "INVALID_AMOUNT"));
    }

    #[test]
    fn test_unsupported_currency_fails() {
        let validator = Validator::new(make_config());
        let req = make_request(1_000.0, "XYZ", "deposit");
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "UNSUPPORTED_CURRENCY"));
    }

    #[test]
    fn test_supported_currencies_pass() {
        let validator = Validator::new(make_config());
        for currency in &["NGN", "USD", "GBP", "EUR", "GHS", "KES", "ZAR"] {
            let req = make_request(1_000.0, currency, "deposit");
            let result = validator.validate(&req);
            assert!(!result.errors.iter().any(|e| e.code == "UNSUPPORTED_CURRENCY"),
                "Currency {} should be supported", currency);
        }
    }

    #[test]
    fn test_invalid_transaction_type_fails() {
        let validator = Validator::new(make_config());
        let req = make_request(1_000.0, "NGN", "invalid_type");
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "INVALID_TRANSACTION_TYPE"));
    }

    #[test]
    fn test_valid_transaction_types() {
        let validator = Validator::new(make_config());
        for tx_type in &["deposit", "withdrawal", "transfer", "bill_payment", "airtime", "pos"] {
            let req = make_request(1_000.0, "NGN", tx_type);
            let result = validator.validate(&req);
            assert!(!result.errors.iter().any(|e| e.code == "INVALID_TRANSACTION_TYPE"),
                "Transaction type {} should be valid", tx_type);
        }
    }

    #[test]
    fn test_cbn_tier1_single_limit_exceeded() {
        let validator = Validator::new(make_config());
        let req = make_request(25_000.0, "NGN", "deposit"); // tier1 limit is 20,000
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "EXCEEDS_SINGLE_TX_LIMIT"));
    }

    #[test]
    fn test_cbn_tier2_single_limit_passes() {
        let validator = Validator::new(make_config());
        let mut req = make_request(50_000.0, "NGN", "deposit"); // tier2 limit is 100,000
        req.agent_tier = Some("tier2".to_string());
        let result = validator.validate(&req);
        assert!(!result.errors.iter().any(|e| e.code == "EXCEEDS_SINGLE_TX_LIMIT"));
    }

    #[test]
    fn test_cbn_tier3_single_limit_passes() {
        let validator = Validator::new(make_config());
        let mut req = make_request(400_000.0, "NGN", "deposit"); // tier3 limit is 500,000
        req.agent_tier = Some("tier3".to_string());
        let result = validator.validate(&req);
        assert!(!result.errors.iter().any(|e| e.code == "EXCEEDS_SINGLE_TX_LIMIT"));
    }

    #[test]
    fn test_daily_limit_exceeded() {
        let validator = Validator::new(make_config());
        let mut req = make_request(10_000.0, "NGN", "deposit");
        req.daily_total_so_far = Some(95_000.0); // tier1 daily limit is 100,000
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "EXCEEDS_DAILY_LIMIT"));
    }

    #[test]
    fn test_approaching_daily_limit_warning() {
        let validator = Validator::new(make_config());
        let mut req = make_request(5_000.0, "NGN", "deposit");
        req.daily_total_so_far = Some(92_000.0); // 97% of tier1 daily limit
        let result = validator.validate(&req);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_withdrawal_without_source_account_fails() {
        let validator = Validator::new(make_config());
        let mut req = make_request(5_000.0, "NGN", "withdrawal");
        req.source_account = None;
        let result = validator.validate(&req);
        assert!(matches!(result.status, ValidationStatus::Rejected));
        assert!(result.errors.iter().any(|e| e.code == "MISSING_SOURCE_ACCOUNT"));
    }

    #[test]
    fn test_applied_rules_populated() {
        let validator = Validator::new(make_config());
        let req = make_request(5_000.0, "NGN", "deposit");
        let result = validator.validate(&req);
        assert!(!result.applied_rules.is_empty());
        assert!(result.applied_rules.contains(&"R-AMOUNT-POSITIVE".to_string()));
        assert!(result.applied_rules.contains(&"R-CURRENCY-SUPPORTED".to_string()));
    }

    #[test]
    fn test_processing_time_recorded() {
        let validator = Validator::new(make_config());
        let req = make_request(5_000.0, "NGN", "deposit");
        let result = validator.validate(&req);
        assert!(result.processing_time_us < 1_000_000);
    }
}
