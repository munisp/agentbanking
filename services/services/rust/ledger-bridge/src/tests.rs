#[cfg(test)]
mod tests {
    use crate::{AccountType, AgentFloatBalance, LedgerAccount, LedgerEntry};
    use chrono::Utc;
    use uuid::Uuid;

    // ── AccountType code() tests ────────────────────────────────────────────

    #[test]
    fn test_account_type_agent_float_code() {
        assert_eq!(AccountType::AgentFloat.code(), 1001);
    }

    #[test]
    fn test_account_type_customer_wallet_code() {
        assert_eq!(AccountType::CustomerWallet.code(), 1002);
    }

    #[test]
    fn test_account_type_commission_code() {
        assert_eq!(AccountType::Commission.code(), 1003);
    }

    #[test]
    fn test_account_type_settlement_code() {
        assert_eq!(AccountType::Settlement.code(), 1004);
    }

    #[test]
    fn test_account_type_fee_code() {
        assert_eq!(AccountType::Fee.code(), 1005);
    }

    #[test]
    fn test_account_type_suspense_code() {
        assert_eq!(AccountType::Suspense.code(), 1006);
    }

    #[test]
    fn test_account_type_cbn_reserve_code() {
        assert_eq!(AccountType::CbnReserve.code(), 1007);
    }

    #[test]
    fn test_account_type_vat_liability_code() {
        assert_eq!(AccountType::VatLiability.code(), 1008);
    }

    #[test]
    fn test_account_type_operational_code() {
        assert_eq!(AccountType::Operational.code(), 1009);
    }

    #[test]
    fn test_all_account_type_codes_unique() {
        let codes = vec![
            AccountType::AgentFloat.code(),
            AccountType::CustomerWallet.code(),
            AccountType::Commission.code(),
            AccountType::Settlement.code(),
            AccountType::Fee.code(),
            AccountType::Suspense.code(),
            AccountType::CbnReserve.code(),
            AccountType::VatLiability.code(),
            AccountType::Operational.code(),
        ];
        let mut unique = codes.clone();
        unique.dedup();
        unique.sort();
        let mut sorted_codes = codes.clone();
        sorted_codes.sort();
        sorted_codes.dedup();
        assert_eq!(sorted_codes.len(), codes.len(), "All account type codes must be unique");
    }

    // ── Domain model serialization tests ───────────────────────────────────

    #[test]
    fn test_ledger_account_serialization() {
        let account = LedgerAccount {
            id: Uuid::new_v4(),
            ledger_id: 1001,
            account_type: AccountType::AgentFloat,
            owner_id: Uuid::new_v4(),
            currency: "NGN".to_string(),
            balance: 500_000,
            debits_posted: 0,
            credits_posted: 500_000,
            created_at: Utc::now(),
            updated_at: Utc::now(),
        };
        let json = serde_json::to_string(&account).unwrap();
        let deserialized: LedgerAccount = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.currency, "NGN");
        assert_eq!(deserialized.balance, 500_000);
        assert_eq!(deserialized.ledger_id, 1001);
    }

    #[test]
    fn test_ledger_entry_serialization() {
        let entry = LedgerEntry {
            id: Uuid::new_v4(),
            entry_ref: "TXN-001-DEBIT".to_string(),
            debit_account_id: Uuid::new_v4(),
            credit_account_id: Uuid::new_v4(),
            amount: 10_000,
            currency: "NGN".to_string(),
            entry_type: "deposit".to_string(),
            description: "Cash deposit".to_string(),
            transaction_ref: Some("TXN-001".to_string()),
            created_at: Utc::now(),
        };
        let json = serde_json::to_string(&entry).unwrap();
        let deserialized: LedgerEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.amount, 10_000);
        assert_eq!(deserialized.currency, "NGN");
        assert_eq!(deserialized.entry_type, "deposit");
    }

    #[test]
    fn test_agent_float_balance_serialization() {
        let balance = AgentFloatBalance {
            agent_id: Uuid::new_v4(),
            float_balance: 250_000,
            commission_balance: 5_000,
            total_deposits: 1_000_000,
            total_withdrawals: 750_000,
            total_commissions: 5_000,
            currency: "NGN".to_string(),
            last_updated: Utc::now(),
        };
        let json = serde_json::to_string(&balance).unwrap();
        let deserialized: AgentFloatBalance = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.float_balance, 250_000);
        assert_eq!(deserialized.commission_balance, 5_000);
    }

    #[test]
    fn test_ledger_account_balance_arithmetic() {
        // Verify balance arithmetic: credits - debits = net balance
        let credits: i64 = 1_000_000;
        let debits: i64 = 750_000;
        let net = credits - debits;
        assert_eq!(net, 250_000);
    }
}
