use chrono::Utc;

use crate::{
    config::Settings,
    error::CorridorError,
    rails::{cips, papss, swift},
};

/// The selected payment rail with routing metadata.
#[derive(Debug, Clone)]
pub struct RoutingDecision {
    pub rail: Rail,
    pub reason: String,
    pub estimated_ttl_s: i64,
    pub routed_at: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Rail {
    Cips,
    Papss,
    Swift,
}

/// Input to the RailSelector — validated payment instruction.
#[derive(Debug, Clone)]
pub struct PaymentInstruction {
    pub transaction_id: String,
    pub currency: String,
    pub origin_country: String,
    pub dest_country: String,
    pub origin_bank_bic: String,
    pub dest_bank_bic: String,
    pub amount_minor: u64,
    pub sender_id: String,
    pub beneficiary_id: String,
}

impl PaymentInstruction {
    /// Validate and construct from raw string fields (as received from gRPC).
    pub fn from_raw(
        transaction_id: String,
        currency: String,
        origin_country: String,
        dest_country: String,
        origin_bank_bic: String,
        dest_bank_bic: String,
        amount_minor_str: &str,
        sender_id: String,
        beneficiary_id: String,
    ) -> Result<Self, CorridorError> {
        if transaction_id.is_empty() {
            return Err(CorridorError::MissingField("transaction_id".into()));
        }
        if currency.len() != 3 {
            return Err(CorridorError::InvalidCurrency(currency));
        }
        if origin_country.len() != 2 {
            return Err(CorridorError::InvalidCountry(origin_country));
        }
        if dest_country.len() != 2 {
            return Err(CorridorError::InvalidCountry(dest_country));
        }
        if sender_id.is_empty() {
            return Err(CorridorError::MissingField("sender_id".into()));
        }
        if beneficiary_id.is_empty() {
            return Err(CorridorError::MissingField("beneficiary_id".into()));
        }
        let amount_minor = amount_minor_str
            .parse::<u64>()
            .map_err(|_| CorridorError::InvalidAmount(amount_minor_str.into()))?;

        Ok(Self {
            transaction_id,
            currency: currency.to_uppercase(),
            origin_country: origin_country.to_uppercase(),
            dest_country: dest_country.to_uppercase(),
            origin_bank_bic,
            dest_bank_bic,
            amount_minor,
            sender_id,
            beneficiary_id,
        })
    }
}

/// RailSelector — the core routing engine.
///
/// Priority order:
///   1. CIPS  — if currency is CNY (or configured CIPS currencies)
///   2. PAPSS — if both origin and destination are PAPSS member countries
///   3. SWIFT — universal fallback
pub struct RailSelector {
    settings: Settings,
}

impl RailSelector {
    pub fn new(settings: Settings) -> Self {
        Self { settings }
    }

    pub fn select(&self, instruction: &PaymentInstruction) -> RoutingDecision {
        let (rail, reason, ttl) = if cips::should_use(
            &instruction.currency,
            &self.settings.rails.cips,
        ) {
            (
                Rail::Cips,
                cips::routing_reason(&instruction.currency),
                self.settings.rails.cips.settlement_ttl_s,
            )
        } else if papss::should_use(
            &instruction.origin_country,
            &instruction.dest_country,
            &self.settings.rails.papss,
        ) {
            (
                Rail::Papss,
                papss::routing_reason(&instruction.origin_country, &instruction.dest_country),
                self.settings.rails.papss.settlement_ttl_s,
            )
        } else {
            (
                Rail::Swift,
                swift::routing_reason(
                    &instruction.origin_country,
                    &instruction.dest_country,
                    &instruction.currency,
                ),
                self.settings.rails.swift.settlement_ttl_s,
            )
        };

        RoutingDecision {
            rail,
            reason,
            estimated_ttl_s: ttl,
            routed_at: Utc::now().to_rfc3339(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{
        CipsConfig, MetricsConfig, PapssConfig, RailsConfig, SecurityConfig, ServerConfig,
        SwiftConfig,
    };

    fn test_settings() -> Settings {
        Settings {
            server: ServerConfig {
                host: "0.0.0.0".into(),
                port: 50051,
            },
            rails: RailsConfig {
                cips: CipsConfig {
                    currencies: vec!["CNY".into()],
                    settlement_ttl_s: 30,
                },
                papss: PapssConfig {
                    member_countries: vec!["NG".into(), "GH".into(), "KE".into()],
                    settlement_ttl_s: 120,
                },
                swift: SwiftConfig {
                    settlement_ttl_s: 86400,
                },
            },
            metrics: MetricsConfig {
                enabled: false,
                port: 9090,
            },
            security: SecurityConfig {
                enforce_api_key: false,
                api_key: "".into(),
            },
        }
    }

    fn instruction(currency: &str, origin: &str, dest: &str) -> PaymentInstruction {
        PaymentInstruction {
            transaction_id: "txn-001".into(),
            currency: currency.into(),
            origin_country: origin.into(),
            dest_country: dest.into(),
            origin_bank_bic: "GTBINGLA".into(),
            dest_bank_bic: "SCBLGHAC".into(),
            amount_minor: 100_000,
            sender_id: "sender-1".into(),
            beneficiary_id: "bene-1".into(),
        }
    }

    #[test]
    fn cny_routes_to_cips() {
        let selector = RailSelector::new(test_settings());
        let decision = selector.select(&instruction("CNY", "CN", "NG"));
        assert_eq!(decision.rail, Rail::Cips);
        assert_eq!(decision.estimated_ttl_s, 30);
    }

    #[test]
    fn intra_african_routes_to_papss() {
        let selector = RailSelector::new(test_settings());
        let decision = selector.select(&instruction("NGN", "NG", "GH"));
        assert_eq!(decision.rail, Rail::Papss);
        assert_eq!(decision.estimated_ttl_s, 120);
    }

    #[test]
    fn usd_outside_africa_routes_to_swift() {
        let selector = RailSelector::new(test_settings());
        let decision = selector.select(&instruction("USD", "US", "NG"));
        assert_eq!(decision.rail, Rail::Swift);
        assert_eq!(decision.estimated_ttl_s, 86400);
    }

    #[test]
    fn cny_beats_papss_for_intra_african_cny() {
        // CNY corridor from CN→NG: CIPS takes priority even if dest is Africa
        let selector = RailSelector::new(test_settings());
        let decision = selector.select(&instruction("CNY", "CN", "NG"));
        assert_eq!(decision.rail, Rail::Cips);
    }
}