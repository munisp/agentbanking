use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
pub struct Settings {
    pub server: ServerConfig,
    pub rails: RailsConfig,
    pub metrics: MetricsConfig,
    pub security: SecurityConfig,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Deserialize, Clone)]
pub struct RailsConfig {
    pub cips: CipsConfig,
    pub papss: PapssConfig,
    pub swift: SwiftConfig,
}

#[derive(Debug, Deserialize, Clone)]
pub struct CipsConfig {
    /// Currencies routed via CIPS
    pub currencies: Vec<String>,
    /// Estimated settlement seconds
    pub settlement_ttl_s: i64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct PapssConfig {
    /// ISO 3166-1 alpha-2 country codes that are PAPSS participants
    pub member_countries: Vec<String>,
    pub settlement_ttl_s: i64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SwiftConfig {
    pub settlement_ttl_s: i64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct MetricsConfig {
    pub enabled: bool,
    pub port: u16,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SecurityConfig {
    pub enforce_api_key: bool,
    pub api_key: String,
}

impl Settings {
    pub fn load() -> Result<Self, config::ConfigError> {
        let cfg = config::Config::builder()
            .add_source(config::File::with_name("config/default").required(false))
            .add_source(config::Environment::with_prefix("CORRIDOR").separator("__"))
            .set_default("server.host", "0.0.0.0")?
            .set_default("server.port", 50051)?
            .set_default("rails.cips.currencies", vec!["CNY"])?
            .set_default("rails.cips.settlement_ttl_s", 30)?
            .set_default(
                "rails.papss.member_countries",
                vec![
                    "NG", "GH", "KE", "ZA", "EG", "ET", "TZ", "UG", "SN", "CI",
                    "CM", "AO", "MZ", "ZM", "ZW", "RW", "TN", "MA", "DZ", "LY",
                ],
            )?
            .set_default("rails.papss.settlement_ttl_s", 120)?
            .set_default("rails.swift.settlement_ttl_s", 86400)?
            .set_default("metrics.enabled", true)?
            .set_default("metrics.port", 9090)?
            .set_default("security.enforce_api_key", false)?
            .set_default("security.api_key", "")?
            .build()?;

        cfg.try_deserialize()
    }
}