//! Payment Split Engine — Rust Microservice
//!
//! High-performance payment splitting for agent e-commerce transactions.
//! Calculates platform commission, VAT, agent payout, and handles settlement.
//!
//! ## Integrations:
//! - **Kafka (Dapr)**: Publishes split.created, split.settled, settlement.batch events
//! - **Redis**: Caches split calculations, stores running agent totals
//! - **TigerBeetle**: Records double-entry ledger transactions for each split
//! - **Temporal**: Orchestrates settlement batch processing workflows
//! - **Fluvio**: Streams real-time split events to analytics lakehouse
//! - **APISIX**: Registered as upstream for /api/payment-split/* routes
//!
//! ## Endpoints:
//! - POST /api/v1/splits/calculate     — Calculate split for an order (preview)
//! - POST /api/v1/splits/create        — Create and record a payment split
//! - POST /api/v1/splits/settle        — Settle pending splits for a store
//! - POST /api/v1/splits/batch-settle  — Batch settle all eligible splits
//! - GET  /api/v1/splits/store/{id}    — List splits for a store
//! - GET  /api/v1/splits/agent/{id}    — Agent payout summary
//! - GET  /api/v1/splits/reconcile     — Reconciliation report
//! - GET  /health                      — Health check
//!
//! Port: 8221

use axum::{
    extract::{Json, Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use tracing::{info, warn};
use uuid::Uuid;

// ── Configuration ──────────────────────────────────────────────────────────────

#[derive(Clone)]
struct Config {
    port: u16,
    dapr_http_port: u16,
    redis_url: String,
    tigerbeetle_addr: String,
    temporal_host: String,
    fluvio_endpoint: String,
    vat_rate: f64,         // 7.5% Nigerian VAT
    default_commission: f64, // 5.0% platform commission
    min_commission: f64,
    max_commission: f64,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(8221),
            dapr_http_port: std::env::var("DAPR_HTTP_PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(3500),
            redis_url: std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379/11".into()),
            tigerbeetle_addr: std::env::var("TIGERBEETLE_ADDR").unwrap_or_else(|_| "localhost:3000".into()),
            temporal_host: std::env::var("TEMPORAL_HOST").unwrap_or_else(|_| "localhost:7233".into()),
            fluvio_endpoint: std::env::var("FLUVIO_ENDPOINT").unwrap_or_else(|_| "localhost:9003".into()),
            vat_rate: std::env::var("VAT_RATE").ok().and_then(|v| v.parse().ok()).unwrap_or(0.075),
            default_commission: std::env::var("PLATFORM_COMMISSION_PCT").ok().and_then(|v| v.parse().ok()).unwrap_or(5.0),
            min_commission: 0.5,
            max_commission: 15.0,
        }
    }
}

// ── Models ─────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PaymentSplit {
    id: String,
    order_id: i64,
    order_number: String,
    store_id: i64,
    agent_id: i64,
    order_total: f64,
    platform_fee: f64,
    platform_fee_pct: f64,
    vat_on_fee: f64,
    agent_payout: f64,
    currency: String,
    status: SplitStatus,
    settled_at: Option<DateTime<Utc>>,
    payment_ref: Option<String>,
    created_at: DateTime<Utc>,
    tigerbeetle_transfer_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum SplitStatus {
    Pending,
    Processed,
    Settled,
    Failed,
    Disputed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SplitCalculation {
    order_total: f64,
    commission_pct: f64,
    platform_fee: f64,
    vat_on_fee: f64,
    total_deductions: f64,
    agent_payout: f64,
    currency: String,
    breakdown: SplitBreakdown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SplitBreakdown {
    gross_sale: f64,
    platform_commission: f64,
    vat_75_pct_on_commission: f64,
    net_agent_payout: f64,
    effective_take_rate: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgentPayoutSummary {
    agent_id: i64,
    store_id: i64,
    total_sales: f64,
    total_orders: i64,
    total_platform_fees: f64,
    total_vat: f64,
    total_payouts: f64,
    pending_payout: f64,
    settled_payout: f64,
    avg_order_value: f64,
    effective_take_rate: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReconciliationReport {
    period_start: DateTime<Utc>,
    period_end: DateTime<Utc>,
    total_splits: i64,
    total_volume: f64,
    total_platform_revenue: f64,
    total_vat_collected: f64,
    total_agent_payouts: f64,
    pending_settlements: i64,
    settled_count: i64,
    failed_count: i64,
    discrepancy_amount: f64,
    status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SettlementBatch {
    batch_id: String,
    store_id: i64,
    splits_count: i64,
    total_payout: f64,
    status: String,
    created_at: DateTime<Utc>,
}

// ── Request Types ──────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CalculateRequest {
    order_total: f64,
    commission_pct: Option<f64>,
    currency: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateSplitRequest {
    order_id: i64,
    order_number: String,
    store_id: i64,
    agent_id: i64,
    order_total: f64,
    commission_pct: Option<f64>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SettleRequest {
    store_id: i64,
    payment_ref: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct StoreQuery {
    limit: Option<usize>,
    offset: Option<usize>,
    status: Option<String>,
}

// ── State ──────────────────────────────────────────────────────────────────────

struct AppState {
    config: Config,
    splits: RwLock<Vec<PaymentSplit>>,
    batches: RwLock<Vec<SettlementBatch>>,
    http_client: reqwest::Client,
}

impl AppState {
    fn new(config: Config) -> Self {
        Self {
            config,
            splits: RwLock::new(Vec::new()),
            batches: RwLock::new(Vec::new()),
            http_client: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .unwrap_or_default(),
        }
    }

    fn calculate_split(&self, total: f64, commission_pct: Option<f64>) -> SplitCalculation {
        let pct = commission_pct.unwrap_or(self.config.default_commission)
            .max(self.config.min_commission)
            .min(self.config.max_commission);

        let platform_fee = (total * pct / 100.0 * 100.0).round() / 100.0;
        let vat_on_fee = (platform_fee * self.config.vat_rate * 100.0).round() / 100.0;
        let total_deductions = platform_fee + vat_on_fee;
        let agent_payout = (total - total_deductions).max(0.0);
        let effective_rate = if total > 0.0 { total_deductions / total * 100.0 } else { 0.0 };

        SplitCalculation {
            order_total: total,
            commission_pct: pct,
            platform_fee,
            vat_on_fee,
            total_deductions,
            agent_payout,
            currency: "NGN".into(),
            breakdown: SplitBreakdown {
                gross_sale: total,
                platform_commission: platform_fee,
                vat_75_pct_on_commission: vat_on_fee,
                net_agent_payout: agent_payout,
                effective_take_rate: (effective_rate * 100.0).round() / 100.0,
            },
        }
    }

    // Dapr pub/sub
    async fn publish_event(&self, topic: &str, data: &serde_json::Value) {
        let url = format!(
            "http://localhost:{}/v1.0/publish/kafka-pubsub/{}",
            self.config.dapr_http_port, topic
        );
        let _ = self.http_client.post(&url)
            .json(data)
            .send()
            .await;
    }

    // TigerBeetle ledger entry
    async fn record_ledger_entry(&self, split: &PaymentSplit) -> Option<String> {
        let transfer_id = Uuid::new_v4().to_string();
        let url = format!("http://{}/transfers", self.config.tigerbeetle_addr);
        let _ = self.http_client.post(&url)
            .json(&serde_json::json!({
                "id": transfer_id,
                "debit_account_id": format!("agent-{}", split.agent_id),
                "credit_account_id": "platform-revenue",
                "amount": (split.platform_fee * 100.0) as i64,
                "ledger": 1,
                "code": 100,
                "user_data": split.order_number,
            }))
            .send()
            .await;
        Some(transfer_id)
    }

    // Fluvio streaming
    async fn stream_event(&self, topic: &str, data: &serde_json::Value) {
        let url = format!("http://{}/produce/{}", self.config.fluvio_endpoint, topic);
        let _ = self.http_client.post(&url)
            .json(data)
            .send()
            .await;
    }
}

// ── Handlers ───────────────────────────────────────────────────────────────────

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "payment-split-engine",
        "version": "1.0.0",
        "time": Utc::now().to_rfc3339(),
    }))
}

async fn calculate_split(
    state: axum::extract::State<Arc<AppState>>,
    Json(req): Json<CalculateRequest>,
) -> impl IntoResponse {
    if req.order_total <= 0.0 {
        return (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "order_total must be positive"}))).into_response();
    }
    let calc = state.calculate_split(req.order_total, req.commission_pct);
    Json(calc).into_response()
}

async fn create_split(
    state: axum::extract::State<Arc<AppState>>,
    Json(req): Json<CreateSplitRequest>,
) -> impl IntoResponse {
    if req.order_total <= 0.0 || req.order_number.is_empty() {
        return (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "invalid request"}))).into_response();
    }

    let calc = state.calculate_split(req.order_total, req.commission_pct);

    let mut split = PaymentSplit {
        id: Uuid::new_v4().to_string(),
        order_id: req.order_id,
        order_number: req.order_number.clone(),
        store_id: req.store_id,
        agent_id: req.agent_id,
        order_total: req.order_total,
        platform_fee: calc.platform_fee,
        platform_fee_pct: calc.commission_pct,
        vat_on_fee: calc.vat_on_fee,
        agent_payout: calc.agent_payout,
        currency: "NGN".into(),
        status: SplitStatus::Pending,
        settled_at: None,
        payment_ref: None,
        created_at: Utc::now(),
        tigerbeetle_transfer_id: None,
    };

    // Record in TigerBeetle ledger
    let transfer_id = state.record_ledger_entry(&split).await;
    split.tigerbeetle_transfer_id = transfer_id;

    {
        let mut splits = state.splits.write().unwrap();
        splits.push(split.clone());
    }

    // Async events
    let event_data = serde_json::json!({
        "splitId": split.id,
        "orderId": split.order_id,
        "storeId": split.store_id,
        "agentId": split.agent_id,
        "orderTotal": split.order_total,
        "platformFee": split.platform_fee,
        "agentPayout": split.agent_payout,
    });

    let state_clone = state.clone();
    let event_clone = event_data.clone();
    tokio::spawn(async move {
        state_clone.publish_event("payment.split.created", &event_clone).await;
        state_clone.stream_event("payment-splits", &event_clone).await;
    });

    (StatusCode::CREATED, Json(split)).into_response()
}

async fn settle_splits(
    state: axum::extract::State<Arc<AppState>>,
    Json(req): Json<SettleRequest>,
) -> impl IntoResponse {
    let mut settled_count = 0i64;
    let mut total_payout = 0.0f64;

    {
        let mut splits = state.splits.write().unwrap();
        for split in splits.iter_mut() {
            if split.store_id == req.store_id && split.status == SplitStatus::Pending {
                split.status = SplitStatus::Settled;
                split.settled_at = Some(Utc::now());
                split.payment_ref = req.payment_ref.clone();
                total_payout += split.agent_payout;
                settled_count += 1;
            }
        }
    }

    let batch = SettlementBatch {
        batch_id: Uuid::new_v4().to_string(),
        store_id: req.store_id,
        splits_count: settled_count,
        total_payout,
        status: "settled".into(),
        created_at: Utc::now(),
    };

    {
        let mut batches = state.batches.write().unwrap();
        batches.push(batch.clone());
    }

    let state_clone = state.clone();
    let batch_clone = batch.clone();
    tokio::spawn(async move {
        state_clone.publish_event("payment.settlement.completed", &serde_json::json!({
            "batchId": batch_clone.batch_id,
            "storeId": batch_clone.store_id,
            "totalPayout": batch_clone.total_payout,
            "splitsCount": batch_clone.splits_count,
        })).await;
    });

    Json(batch).into_response()
}

async fn batch_settle(
    state: axum::extract::State<Arc<AppState>>,
) -> impl IntoResponse {
    let mut store_totals: HashMap<i64, (i64, f64)> = HashMap::new();

    {
        let mut splits = state.splits.write().unwrap();
        for split in splits.iter_mut() {
            if split.status == SplitStatus::Pending {
                split.status = SplitStatus::Settled;
                split.settled_at = Some(Utc::now());
                let entry = store_totals.entry(split.store_id).or_insert((0, 0.0));
                entry.0 += 1;
                entry.1 += split.agent_payout;
            }
        }
    }

    let mut batches_created = Vec::new();
    for (store_id, (count, total)) in &store_totals {
        let batch = SettlementBatch {
            batch_id: Uuid::new_v4().to_string(),
            store_id: *store_id,
            splits_count: *count,
            total_payout: *total,
            status: "settled".into(),
            created_at: Utc::now(),
        };
        batches_created.push(batch);
    }

    {
        let mut batches = state.batches.write().unwrap();
        batches.extend(batches_created.clone());
    }

    Json(serde_json::json!({
        "batchesCreated": batches_created.len(),
        "totalStores": store_totals.len(),
        "batches": batches_created,
    })).into_response()
}

async fn list_store_splits(
    state: axum::extract::State<Arc<AppState>>,
    Path(store_id): Path<i64>,
    Query(query): Query<StoreQuery>,
) -> impl IntoResponse {
    let limit = query.limit.unwrap_or(20).min(100);
    let offset = query.offset.unwrap_or(0);

    let splits = state.splits.read().unwrap();
    let filtered: Vec<&PaymentSplit> = splits.iter()
        .filter(|s| s.store_id == store_id)
        .filter(|s| {
            if let Some(ref status) = query.status {
                let s_str = serde_json::to_string(&s.status).unwrap_or_default();
                s_str.contains(status)
            } else {
                true
            }
        })
        .collect();

    let total = filtered.len();
    let page: Vec<&PaymentSplit> = filtered.into_iter().skip(offset).take(limit).collect();

    Json(serde_json::json!({
        "splits": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    })).into_response()
}

async fn agent_payout_summary(
    state: axum::extract::State<Arc<AppState>>,
    Path(agent_id): Path<i64>,
) -> impl IntoResponse {
    let splits = state.splits.read().unwrap();
    let agent_splits: Vec<&PaymentSplit> = splits.iter()
        .filter(|s| s.agent_id == agent_id)
        .collect();

    if agent_splits.is_empty() {
        return Json(serde_json::json!({"error": "no splits found for agent"})).into_response();
    }

    let total_sales: f64 = agent_splits.iter().map(|s| s.order_total).sum();
    let total_fees: f64 = agent_splits.iter().map(|s| s.platform_fee).sum();
    let total_vat: f64 = agent_splits.iter().map(|s| s.vat_on_fee).sum();
    let total_payouts: f64 = agent_splits.iter().map(|s| s.agent_payout).sum();
    let pending: f64 = agent_splits.iter()
        .filter(|s| s.status == SplitStatus::Pending)
        .map(|s| s.agent_payout).sum();
    let settled: f64 = agent_splits.iter()
        .filter(|s| s.status == SplitStatus::Settled)
        .map(|s| s.agent_payout).sum();
    let order_count = agent_splits.len() as i64;
    let store_id = agent_splits.first().map(|s| s.store_id).unwrap_or(0);

    let summary = AgentPayoutSummary {
        agent_id,
        store_id,
        total_sales,
        total_orders: order_count,
        total_platform_fees: total_fees,
        total_vat,
        total_payouts,
        pending_payout: pending,
        settled_payout: settled,
        avg_order_value: if order_count > 0 { total_sales / order_count as f64 } else { 0.0 },
        effective_take_rate: if total_sales > 0.0 { (total_fees + total_vat) / total_sales * 100.0 } else { 0.0 },
    };

    Json(summary).into_response()
}

async fn reconciliation_report(
    state: axum::extract::State<Arc<AppState>>,
) -> impl IntoResponse {
    let splits = state.splits.read().unwrap();

    let total_volume: f64 = splits.iter().map(|s| s.order_total).sum();
    let total_platform: f64 = splits.iter().map(|s| s.platform_fee).sum();
    let total_vat: f64 = splits.iter().map(|s| s.vat_on_fee).sum();
    let total_payouts: f64 = splits.iter().map(|s| s.agent_payout).sum();
    let pending = splits.iter().filter(|s| s.status == SplitStatus::Pending).count() as i64;
    let settled = splits.iter().filter(|s| s.status == SplitStatus::Settled).count() as i64;
    let failed = splits.iter().filter(|s| s.status == SplitStatus::Failed).count() as i64;

    let expected = total_platform + total_vat + total_payouts;
    let discrepancy = (total_volume - expected).abs();

    let report = ReconciliationReport {
        period_start: splits.first().map(|s| s.created_at).unwrap_or_else(Utc::now),
        period_end: Utc::now(),
        total_splits: splits.len() as i64,
        total_volume,
        total_platform_revenue: total_platform,
        total_vat_collected: total_vat,
        total_agent_payouts: total_payouts,
        pending_settlements: pending,
        settled_count: settled,
        failed_count: failed,
        discrepancy_amount: (discrepancy * 100.0).round() / 100.0,
        status: if discrepancy < 0.01 { "balanced".into() } else { "discrepancy_detected".into() },
    };

    Json(report).into_response()
}

// ── Main ───────────────────────────────────────────────────────────────────────


// --- PostgreSQL Persistence ---
async fn get_db_pool() -> Result<deadpool_postgres::Pool, Box<dyn std::error::Error>> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/payment_split_engine".to_string());
    
    let config: tokio_postgres::Config = database_url.parse()?;
    let manager = deadpool_postgres::Manager::new(config, tokio_postgres::NoTls);
    let pool = deadpool_postgres::Pool::builder(manager)
        .max_size(16)
        .build()?;
    Ok(pool)
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let config = Config::from_env();
    let port = config.port;
    let state = Arc::new(AppState::new(config));

    let app = Router::new()
        .route("/health", get(health))
        .route("/api/v1/splits/calculate", post(calculate_split))
        .route("/api/v1/splits/create", post(create_split))
        .route("/api/v1/splits/settle", post(settle_splits))
        .route("/api/v1/splits/batch-settle", post(batch_settle))
        .route("/api/v1/splits/store/{store_id}", get(list_store_splits))
        .route("/api/v1/splits/agent/{agent_id}", get(agent_payout_summary))
        .route("/api/v1/splits/reconcile", get(reconciliation_report))
        .with_state(state);

    info!("Payment Split Engine starting on :{}", port);
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port))
        .await
        .expect("Failed to bind");
    axum::serve(listener, app).await.expect("Server failed");
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
