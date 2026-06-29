use crate::config::CipsConfig;

/// Returns true if this payment should be routed via CIPS.
///
/// CIPS handles CNY cross-border interbank payments. The rule is simple:
/// if the transaction currency is in the CIPS currency list (default: CNY),
/// route to CIPS regardless of origin/destination country.
pub fn should_use(currency: &str, config: &CipsConfig) -> bool {
    config
        .currencies
        .iter()
        .any(|c| c.eq_ignore_ascii_case(currency))
}

pub fn routing_reason(currency: &str) -> String {
    format!(
        "Currency {} is settled via CIPS (Cross-Border Interbank Payment System)",
        currency
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::CipsConfig;

    fn config() -> CipsConfig {
        CipsConfig {
            currencies: vec!["CNY".into()],
            settlement_ttl_s: 30,
        }
    }

    #[test]
    fn routes_cny() {
        assert!(should_use("CNY", &config()));
    }

    #[test]
    fn routes_cny_lowercase() {
        assert!(should_use("cny", &config()));
    }

    #[test]
    fn does_not_route_usd() {
        assert!(!should_use("USD", &config()));
    }
}