// 54Link Agency Banking Platform - Rust Transaction Validator
// Language: Rust
// Purpose: Ultra-low-latency transaction validation engine.
//          Validates transactions against business rules, CBN limits,
//          agent permissions, and account constraints before processing.
//          Target: <1ms validation latency at 100k TPS.

#[cfg(test)]
mod tests;

use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::sync::Arc;
use tracing::info;
use uuid::Uuid;

// ── Configuration ──────────────────────────────────────────────────────────────
#[derive(Debug, Clone)]
struct Config {
    port: u16,
    environment: String,
    // CBN limits (NGN)
    single_tx_limit_tier1: f64,
    single_tx_limit_tier2: f64,
    single_tx_limit_tier3: f64,
    daily_limit_tier1: f64,
    daily_limit_tier2: f64,
    daily_limit_tier3: f64,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("PORT").unwrap_or_else(|_| "8070".to_string()).parse().unwrap_or(8070),
            environment: std::env::var("ENVIRONMENT").unwrap_or_else(|_| "production".to_string()),
            // CBN Agency Banking Limits
            single_tx_limit_tier1: 20_000.0,
            single_tx_limit_tier2: 100_000.0,
            single_tx_limit_tier3: 500_000.0,
            daily_limit_tier1: 100_000.0,
            daily_limit_tier2: 500_000.0,
            daily_limit_tier3: 2_000_000.0,
        }
    }
}

// ── Domain Models ──────────────────────────────────────────────────────────────
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationRequest {
    pub transaction_id: Uuid,
    pub transaction_type: String,
    pub amount: f64,
    pub currency: String,
    pub agent_id: Uuid,
    pub agent_tier: Option<String>,
    pub customer_id: Option<Uuid>,
    pub customer_tier: Option<String>,
    pub source_account: Option<String>,
    pub destination_account: Option<String>,
    pub daily_total_so_far: Option<f64>,
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ValidationStatus {
    Approved,
    Rejected,
    RequiresReview,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationError {
    pub code: String,
    pub message: String,
    pub field: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    pub transaction_id: Uuid,
    pub status: ValidationStatus,
    pub errors: Vec<ValidationError>,
    pub warnings: Vec<String>,
    pub applied_rules: Vec<String>,
    pub processing_time_us: u64,
    pub timestamp: DateTime<Utc>,
}

// ── Validation Rules ───────────────────────────────────────────────────────────
struct Validator {
    config: Config,
}

impl Validator {
    fn new(config: Config) -> Self {
        Self { config }
    }

    fn validate(&self, req: &ValidationRequest) -> ValidationResult {
        let start = std::time::Instant::now();
        let mut errors = Vec::new();
        let mut warnings = Vec::new();
        let mut applied_rules = Vec::new();

        // Rule 1: Amount must be positive
        applied_rules.push("R-AMOUNT-POSITIVE".to_string());
        if req.amount <= 0.0 {
            errors.push(ValidationError {
                code: "INVALID_AMOUNT".to_string(),
                message: "Transaction amount must be positive".to_string(),
                field: Some("amount".to_string()),
            });
        }

        // Rule 2: Amount must not have more than 2 decimal places
        applied_rules.push("R-AMOUNT-PRECISION".to_string());
        let rounded = (req.amount * 100.0).round() / 100.0;
        if (req.amount - rounded).abs() > 1e-10 {
            errors.push(ValidationError {
                code: "INVALID_AMOUNT_PRECISION".to_string(),
                message: "Amount cannot have more than 2 decimal places".to_string(),
                field: Some("amount".to_string()),
            });
        }

        // Rule 3: Currency must be supported
        applied_rules.push("R-CURRENCY-SUPPORTED".to_string());
        let supported_currencies = ["NGN", "USD", "GBP", "EUR", "GHS", "KES", "ZAR"];
        if !supported_currencies.contains(&req.currency.as_str()) {
            errors.push(ValidationError {
                code: "UNSUPPORTED_CURRENCY".to_string(),
                message: format!("Currency {} is not supported", req.currency),
                field: Some("currency".to_string()),
            });
        }

        // Rule 4: Transaction type must be valid
        applied_rules.push("R-TX-TYPE-VALID".to_string());
        let valid_types = ["deposit", "withdrawal", "transfer", "bill_payment", "airtime", "data", "pos", "qr_payment", "reversal"];
        if !valid_types.contains(&req.transaction_type.as_str()) {
            errors.push(ValidationError {
                code: "INVALID_TRANSACTION_TYPE".to_string(),
                message: format!("Transaction type {} is not valid", req.transaction_type),
                field: Some("transaction_type".to_string()),
            });
        }

        // Rule 5: CBN single transaction limits
        if req.currency == "NGN" {
            applied_rules.push("R-CBN-SINGLE-LIMIT".to_string());
            let tier = req.agent_tier.as_deref().unwrap_or("tier1");
            let limit = match tier {
                "tier3" => self.config.single_tx_limit_tier3,
                "tier2" => self.config.single_tx_limit_tier2,
                _ => self.config.single_tx_limit_tier1,
            };
            if req.amount > limit {
                errors.push(ValidationError {
                    code: "EXCEEDS_SINGLE_TX_LIMIT".to_string(),
                    message: format!("Amount NGN {:.2} exceeds {} single transaction limit of NGN {:.2}", req.amount, tier, limit),
                    field: Some("amount".to_string()),
                });
            }
        }

        // Rule 6: CBN daily transaction limits
        if req.currency == "NGN" {
            if let Some(daily_total) = req.daily_total_so_far {
                applied_rules.push("R-CBN-DAILY-LIMIT".to_string());
                let tier = req.agent_tier.as_deref().unwrap_or("tier1");
                let limit = match tier {
                    "tier3" => self.config.daily_limit_tier3,
                    "tier2" => self.config.daily_limit_tier2,
                    _ => self.config.daily_limit_tier1,
                };
                let projected_total = daily_total + req.amount;
                if projected_total > limit {
                    errors.push(ValidationError {
                        code: "EXCEEDS_DAILY_LIMIT".to_string(),
                        message: format!("Daily total NGN {:.2} would exceed {} limit of NGN {:.2}", projected_total, tier, limit),
                        field: Some("amount".to_string()),
                    });
                } else if projected_total > limit * 0.9 {
                    warnings.push(format!("Approaching daily limit: {:.1}% used", (projected_total / limit) * 100.0));
                }
            }
        }

        // Rule 7: Withdrawal requires source account
        applied_rules.push("R-WITHDRAWAL-ACCOUNT".to_string());
        if req.transaction_type == "withdrawal" && req.source_account.is_none() {
            errors.push(ValidationError {
                code: "MISSING_SOURCE_ACCOUNT".to_string(),
                message: "Withdrawal requires a source account".to_string(),
                field: Some("source_account".to_string()),
            });
        }

        // Rule 8: Transfer requires both accounts
        applied_rules.push("R-TRANSFER-ACCOUNTS".to_string());
        if req.transaction_type == "transfer" {
            if req.source_account.is_none() {
                errors.push(ValidationError {
                    code: "MISSING_SOURCE_ACCOUNT".to_string(),
                    message: "Transfer requires a source account".to_string(),
                    field: Some("source_account".to_string()),
                });
            }
            if req.destination_account.is_none() {
                errors.push(ValidationError {
                    code: "MISSING_DESTINATION_ACCOUNT".to_string(),
                    message: "Transfer requires a destination account".to_string(),
                    field: Some("destination_account".to_string()),
                });
            }
        }

        // Rule 9: Minimum transaction amount
        applied_rules.push("R-MIN-AMOUNT".to_string());
        let min_amount = if req.currency == "NGN" { 50.0 } else { 0.01 };
        if req.amount < min_amount && req.amount > 0.0 {
            errors.push(ValidationError {
                code: "BELOW_MINIMUM_AMOUNT".to_string(),
                message: format!("Amount {} {:.2} is below minimum of {:.2}", req.currency, req.amount, min_amount),
                field: Some("amount".to_string()),
            });
        }

        // Rule 10: Bill payment requires destination
        applied_rules.push("R-BILL-DESTINATION".to_string());
        if req.transaction_type == "bill_payment" && req.destination_account.is_none() {
            errors.push(ValidationError {
                code: "MISSING_BILLER_ACCOUNT".to_string(),
                message: "Bill payment requires a biller account/reference".to_string(),
                field: Some("destination_account".to_string()),
            });
        }

        let elapsed_us = start.elapsed().as_micros() as u64;

        let status = if errors.is_empty() {
            ValidationStatus::Approved
        } else {
            ValidationStatus::Rejected
        };

        ValidationResult {
            transaction_id: req.transaction_id,
            status,
            errors,
            warnings,
            applied_rules,
            processing_time_us: elapsed_us,
            timestamp: Utc::now(),
        }
    }
}

// ── Application State ──────────────────────────────────────────────────────────
#[derive(Clone)]
struct AppState {
    config: Config,
    validator: Arc<Validator>,
}

impl AppState {
    fn new(config: Config) -> Self {
        let validator = Arc::new(Validator::new(config.clone()));
        Self { config, validator }
    }
}

// ── HTTP Handlers ──────────────────────────────────────────────────────────────
async fn handle_health(State(state): State<AppState>) -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "rust-tx-validator",
        "version": "14.0.0",
        "environment": state.config.environment,
        "cbn_limits": {
            "tier1_single": state.config.single_tx_limit_tier1,
            "tier2_single": state.config.single_tx_limit_tier2,
            "tier3_single": state.config.single_tx_limit_tier3,
            "tier1_daily": state.config.daily_limit_tier1,
            "tier2_daily": state.config.daily_limit_tier2,
            "tier3_daily": state.config.daily_limit_tier3,
        },
        "timestamp": Utc::now(),
    }))
}

async fn handle_validate(
    State(state): State<AppState>,
    Json(req): Json<ValidationRequest>,
) -> Json<ValidationResult> {
    let result = state.validator.validate(&req);
    info!(
        transaction_id = %req.transaction_id,
        status = ?result.status,
        errors = result.errors.len(),
        processing_us = result.processing_time_us,
        "transaction validated"
    );
    Json(result)
}

async fn handle_validate_batch(
    State(state): State<AppState>,
    Json(batch): Json<Vec<ValidationRequest>>,
) -> Result<Json<Vec<ValidationResult>>, (StatusCode, Json<serde_json::Value>)> {
    if batch.len() > 10_000 {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "Batch size exceeds 10,000"})),
        ));
    }

    let results: Vec<ValidationResult> = batch.iter()
        .map(|req| state.validator.validate(req))
        .collect();

    Ok(Json(results))
}

async fn handle_get_rules(State(state): State<AppState>) -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "rules": [
            {"id": "R-AMOUNT-POSITIVE", "description": "Amount must be positive"},
            {"id": "R-AMOUNT-PRECISION", "description": "Amount max 2 decimal places"},
            {"id": "R-CURRENCY-SUPPORTED", "description": "Currency must be supported"},
            {"id": "R-TX-TYPE-VALID", "description": "Transaction type must be valid"},
            {"id": "R-CBN-SINGLE-LIMIT", "description": "CBN single transaction limit by tier"},
            {"id": "R-CBN-DAILY-LIMIT", "description": "CBN daily transaction limit by tier"},
            {"id": "R-WITHDRAWAL-ACCOUNT", "description": "Withdrawal requires source account"},
            {"id": "R-TRANSFER-ACCOUNTS", "description": "Transfer requires both accounts"},
            {"id": "R-MIN-AMOUNT", "description": "Minimum transaction amount"},
            {"id": "R-BILL-DESTINATION", "description": "Bill payment requires destination"},
        ],
        "cbn_limits": {
            "tier1": {
                "single_transaction": state.config.single_tx_limit_tier1,
                "daily": state.config.daily_limit_tier1,
            },
            "tier2": {
                "single_transaction": state.config.single_tx_limit_tier2,
                "daily": state.config.daily_limit_tier2,
            },
            "tier3": {
                "single_transaction": state.config.single_tx_limit_tier3,
                "daily": state.config.daily_limit_tier3,
            },
        },
    }))
}

// ── Main ───────────────────────────────────────────────────────────────────────

// --- PostgreSQL Persistence ---
async fn get_db_pool() -> Result<deadpool_postgres::Pool, Box<dyn std::error::Error>> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/tx_validator".to_string());
    
    let config: tokio_postgres::Config = database_url.parse()?;
    let manager = deadpool_postgres::Manager::new(config, tokio_postgres::NoTls);
    let pool = deadpool_postgres::Pool::builder(manager)
        .max_size(16)
        .build()?;
    Ok(pool)
}


fn verify_auth(headers: &hyper::HeaderMap) -> Result<String, (hyper::StatusCode, String)> {
    let auth_header = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or((
            hyper::StatusCode::UNAUTHORIZED,
            r#"{"error":"missing authorization header"}"#.to_string(),
        ))?;
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
        return Err((
            hyper::StatusCode::UNAUTHORIZED,
            r#"{"error":"invalid token format"}"#.to_string(),
        ));
    }
    Ok(auth_header[7..].to_string())
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenvy::dotenv().ok();

    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env()
            .add_directive("tx_validator=info".parse()?)
            .add_directive("axum=info".parse()?))
        .json()
        .init();

    let config = Config::from_env();
    let port = config.port;
    let env = config.environment.clone();

    info!(port = port, environment = %env, "starting rust-tx-validator");

    let state = AppState::new(config);

    let app = Router::new()
        .route("/health", get(handle_health))
        .route("/api/v1/validate", post(handle_validate))
        .route("/api/v1/validate/batch", post(handle_validate_batch))
        .route("/api/v1/validate/rules", get(handle_get_rules))
        .with_state(state)
        .layer(tower_http::cors::CorsLayer::permissive())
        .layer(tower_http::trace::TraceLayer::new_for_http());

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("rust-tx-validator listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener,
        app.into_make_service())
        .with_graceful_shutdown(async {
            tokio::signal::ctrl_c().await.expect("ctrl+c handler failed");
        })
        .await?;

    info!("rust-tx-validator stopped");
    Ok(())
}

// ── JWT Auth Middleware ─────────────────────────────────────────────────────────

fn validate_bearer_token(req: &tiny_http::Request) -> Result<(), (u16, &'static str)> {
    let path = req.url();
            if let Err((code, msg)) = validate_bearer_token(&req) {
                let resp = tiny_http::Response::from_string(format!("{{\"error\":{{\"code\":{},\"message\":\"{}\"}}}}", code, msg))
                    .with_status_code(code)
                    .with_header(tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap());
                let _ = req.respond(resp);
                continue;
            }
    // Skip auth for health/metrics endpoints
    if path == "/health" || path == "/healthz" || path == "/metrics" || path == "/ready" {
        return Ok(());
    }
    let auth = req.headers().iter()
        .find(|h| h.field.as_str().eq_ignore_ascii_case("Authorization"))
        .map(|h| h.value.as_str().to_string());
    match auth {
        None => Err((401, "missing authorization header")),
        Some(val) => {
            let parts: Vec<&str> = val.splitn(2, ' ').collect();
            if parts.len() != 2 || !parts[0].eq_ignore_ascii_case("bearer") || parts[1].len() < 10 {
                Err((401, "invalid bearer token format"))
            } else {
                // In production, validate JWT against Keycloak JWKS
                Ok(())
            }
        }
    }
}
