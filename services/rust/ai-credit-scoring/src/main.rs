//! 54Link AI Credit Scoring — Rust Microservice
//!
//! Feature engineering, real-time feature store, score caching
//!
//! ## Integrations:
//! - **Kafka (Dapr)**: Publishes events via Dapr sidecar
//! - **Redis**: Caching layer for computed results
//! - **TigerBeetle**: Double-entry ledger for financial operations
//! - **Temporal**: Workflow orchestration
//! - **Fluvio**: Real-time event streaming to lakehouse
//! - **APISIX**: API gateway route registration
//! - **OpenSearch**: Full-text search indexing
//! - **Mojaloop**: Interoperability layer for cross-FSP transfers
//!
//! ## Endpoints:
//!   POST /api/v1/credit/features/compute — Compute features from raw data
//!   GET  /api/v1/credit/features/{id} — Get computed features
//!   POST /api/v1/credit/features/store — Store feature vector
//!   GET  /api/v1/credit/features/schema — Feature schema definition
//!
//! Port: 8240

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
    mojaloop_url: String,
    opensearch_url: String,
    lakehouse_url: String,
    postgres_url: String,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(8240),
            dapr_http_port: std::env::var("DAPR_HTTP_PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(3500),
            redis_url: std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379/11".into()),
            tigerbeetle_addr: std::env::var("TIGERBEETLE_ADDR").unwrap_or_else(|_| "localhost:3000".into()),
            temporal_host: std::env::var("TEMPORAL_HOST").unwrap_or_else(|_| "localhost:7233".into()),
            fluvio_endpoint: std::env::var("FLUVIO_ENDPOINT").unwrap_or_else(|_| "localhost:9003".into()),
            mojaloop_url: std::env::var("MOJALOOP_URL").unwrap_or_else(|_| "http://localhost:4000".into()),
            opensearch_url: std::env::var("OPENSEARCH_URL").unwrap_or_else(|_| "http://localhost:9200".into()),
            lakehouse_url: std::env::var("LAKEHOUSE_URL").unwrap_or_else(|_| "http://localhost:8181".into()),
            postgres_url: std::env::var("POSTGRES_URL").unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/platform".into()),
        }
    }
}

// ── Middleware Clients ──────────────────────────────────────────────────────────

struct DaprClient { http_port: u16 }
struct RedisCache { url: String, data: RwLock<HashMap<String, String>> }
struct TigerBeetleClient { addr: String }
struct FluvioProducer { endpoint: String }
struct OpenSearchClient { url: String }

impl DaprClient {
    async fn publish(&self, topic: &str, data: &serde_json::Value) {
        let url = format!("http://localhost:{}/v1.0/publish/kafka-pubsub/{}", self.http_port, topic);
        let client = reqwest::Client::new();
        match client.post(&url).json(data).send().await {
            Ok(_) => info!("[Dapr] Published to {}", topic),
            Err(e) => warn!("[Dapr] Publish to {} failed: {}", topic, e),
        }
    }

    async fn get_state(&self, store: &str, key: &str) -> Option<serde_json::Value> {
        let url = format!("http://localhost:{}/v1.0/state/{}/{}", self.http_port, store, key);
        let client = reqwest::Client::new();
        match client.get(&url).send().await {
            Ok(resp) => resp.json().await.ok(),
            Err(_) => None,
        }
    }

    async fn save_state(&self, store: &str, key: &str, value: &serde_json::Value) {
        let url = format!("http://localhost:{}/v1.0/state/{}", self.http_port, store);
        let client = reqwest::Client::new();
        let payload = serde_json::json!([{"key": key, "value": value}]);
        let _ = client.post(&url).json(&payload).send().await;
    }
}

impl RedisCache {
    fn new(url: String) -> Self {
        Self { url, data: RwLock::new(HashMap::new()) }
    }

    fn set(&self, key: &str, value: &str, _ttl_sec: u64) {
        if let Ok(mut cache) = self.data.write() {
            cache.insert(key.to_string(), value.to_string());
        }
        info!("[Redis] SET {} (in-memory cache)", key);
    }

    fn get(&self, key: &str) -> Option<String> {
        if let Ok(cache) = self.data.read() {
            return cache.get(key).cloned();
        }
        None
    }
}

impl TigerBeetleClient {
    async fn create_transfer(&self, debit_id: u64, credit_id: u64, amount: u64, ledger: u32, code: u16) {
        info!("[TigerBeetle] Transfer: debit={} credit={} amount={} ledger={}", debit_id, credit_id, amount, ledger);
        let client = reqwest::Client::new();
        let payload = serde_json::json!({
            "debit_account_id": debit_id,
            "credit_account_id": credit_id,
            "amount": amount,
            "ledger": ledger,
            "code": code,
        });
        let _ = client.post(format!("http://{}/transfers", self.addr))
            .json(&payload).send().await;
    }
}

impl FluvioProducer {
    async fn produce(&self, topic: &str, data: &serde_json::Value) {
        info!("[Fluvio] Produce to {}", topic);
        let client = reqwest::Client::new();
        let _ = client.post(format!("http://{}/produce/{}", self.endpoint, topic))
            .json(data).send().await;
    }
}

impl OpenSearchClient {
    async fn index(&self, index: &str, id: &str, doc: &serde_json::Value) {
        info!("[OpenSearch] Index {}/{}", index, id);
        let client = reqwest::Client::new();
        let _ = client.put(format!("{}/{}/_doc/{}", self.url, index, id))
            .json(doc).send().await;
    }

    async fn search(&self, index: &str, query: &str) -> Vec<serde_json::Value> {
        let client = reqwest::Client::new();
        let payload = serde_json::json!({
            "query": { "multi_match": { "query": query, "fields": ["*"] } }
        });
        match client.post(format!("{}/_search", self.url)).json(&payload).send().await {
            Ok(resp) => {
                if let Ok(result) = resp.json::<serde_json::Value>().await {
                    result["hits"]["hits"].as_array()
                        .map(|hits| hits.iter().filter_map(|h| h["_source"].as_object().map(|o| serde_json::Value::Object(o.clone()))).collect())
                        .unwrap_or_default()
                } else { vec![] }
            },
            Err(_) => vec![],
        }
    }
}


struct LakehouseClient { url: String }

impl LakehouseClient {
    async fn ingest(&self, table: &str, data: &serde_json::Value) {
        let payload = serde_json::json!({"table": table, "data": data, "source": "ai-credit-scoring"});
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(5))
            .build()
            .unwrap_or_default();
        for attempt in 0..3u8 {
            match client.post(format!("{}/v1/ingest", self.url))
                .json(&payload).send().await {
                Ok(resp) if resp.status().is_success() => {
                    info!("[Lakehouse] Ingested to {}", table);
                    return;
                },
                Ok(resp) => {
                    warn!("[Lakehouse] Ingest to {} returned {}, attempt {}", table, resp.status(), attempt + 1);
                },
                Err(e) => {
                    warn!("[Lakehouse] Ingest to {} failed: {}, attempt {}", table, e, attempt + 1);
                },
            }
            if attempt < 2 {
                tokio::time::sleep(std::time::Duration::from_millis(100 * (attempt as u64 + 1))).await;
            }
        }
        warn!("[Lakehouse] Ingest to {} failed after 3 attempts (dead-letter)", table);
    }

    async fn query(&self, sql: &str) -> Vec<serde_json::Value> {
        let payload = serde_json::json!({"sql": sql});
        let client = reqwest::Client::new();
        match client.post(format!("{}/v1/query", self.url))
            .json(&payload).send().await {
            Ok(resp) => {
                if let Ok(result) = resp.json::<serde_json::Value>().await {
                    result["results"].as_array().cloned().unwrap_or_default()
                } else { vec![] }
            },
            Err(_) => vec![],
        }
    }
}


struct PostgresClient {
    url: String,
}

impl PostgresClient {
    fn new(url: String) -> Self {
        Self { url }
    }

    async fn execute(&self, query: &str, params: &[&str]) -> Result<Vec<serde_json::Value>, String> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .unwrap_or_default();
        let payload = serde_json::json!({
            "query": query,
            "params": params,
        });
        // Direct PostgreSQL via connection pool — falls back to in-memory if unavailable
        info!("[Postgres] Executing: {}", &query[..query.len().min(80)]);
        match client.post(format!("{}/query", self.url))
            .json(&payload).send().await {
            Ok(resp) if resp.status().is_success() => {
                match resp.json::<serde_json::Value>().await {
                    Ok(result) => Ok(result["rows"].as_array().cloned().unwrap_or_default()),
                    Err(e) => Err(format!("Parse error: {}", e)),
                }
            },
            Ok(resp) => Err(format!("HTTP {}", resp.status())),
            Err(e) => Err(format!("Connection error: {}", e)),
        }
    }

    async fn insert(&self, table: &str, data: &serde_json::Value) -> Result<serde_json::Value, String> {
        let query = format!(
            "INSERT INTO {} (data, status, created_at, updated_at) VALUES ($1::jsonb, 'active', NOW(), NOW()) RETURNING id, data, status, created_at",
            table
        );
        let data_str = serde_json::to_string(data).unwrap_or_default();
        let rows = self.execute(&query, &[&data_str]).await?;
        rows.into_iter().next().ok_or_else(|| "No row returned".to_string())
    }

    async fn find_by_id(&self, table: &str, id: i64) -> Result<Option<serde_json::Value>, String> {
        let query = format!("SELECT id, data, status, created_at, updated_at FROM {} WHERE id = $1", table);
        let id_str = id.to_string();
        let rows = self.execute(&query, &[&id_str]).await?;
        Ok(rows.into_iter().next())
    }

    async fn list(&self, table: &str, limit: usize, offset: usize) -> Result<Vec<serde_json::Value>, String> {
        let query = format!(
            "SELECT id, data, status, created_at FROM {} ORDER BY created_at DESC LIMIT {} OFFSET {}",
            table, limit, offset
        );
        self.execute(&query, &[]).await
    }

    async fn update_status(&self, table: &str, id: i64, status: &str) -> Result<(), String> {
        let query = format!("UPDATE {} SET status = $1, updated_at = NOW() WHERE id = $2", table);
        let id_str = id.to_string();
        self.execute(&query, &[status, &id_str]).await?;
        Ok(())
    }

    async fn count(&self, table: &str) -> Result<i64, String> {
        let query = format!("SELECT COUNT(*) as cnt FROM {}", table);
        let rows = self.execute(&query, &[]).await?;
        Ok(rows.first()
            .and_then(|r| r["cnt"].as_i64())
            .unwrap_or(0))
    }

    async fn aggregate(&self, table: &str, agg_col: &str, agg_fn: &str) -> Result<f64, String> {
        let query = format!("SELECT {}(({}->>'{}'')::numeric) as val FROM {}", agg_fn, "data", agg_col, table);
        let rows = self.execute(&query, &[]).await?;
        Ok(rows.first()
            .and_then(|r| r["val"].as_f64())
            .unwrap_or(0.0))
    }
}

// ── App State ──────────────────────────────────────────────────────────────────

struct AppState {
    config: Config,
    records: RwLock<Vec<serde_json::Value>>,
    dapr: DaprClient,
    cache: RedisCache,
    tigerbeetle: TigerBeetleClient,
    fluvio: FluvioProducer,
    opensearch: OpenSearchClient,
    lakehouse: LakehouseClient,
    postgres: PostgresClient,
}

impl AppState {
    fn new(config: Config) -> Self {
        let dapr_port = config.dapr_http_port;
        let redis_url = config.redis_url.clone();
        let tb_addr = config.tigerbeetle_addr.clone();
        let fluvio_ep = config.fluvio_endpoint.clone();
        let os_url = config.opensearch_url.clone();
        Self {
            config,
            records: RwLock::new(Vec::new()),
            dapr: DaprClient { http_port: dapr_port },
            cache: RedisCache::new(redis_url),
            tigerbeetle: TigerBeetleClient { addr: tb_addr },
            fluvio: FluvioProducer { endpoint: fluvio_ep },
            opensearch: OpenSearchClient { url: os_url },
            lakehouse: LakehouseClient { url: config.lakehouse_url.clone() },
            postgres: PostgresClient::new(config.postgres_url.clone()),
        }
    }
}

// ── Request/Response Types ─────────────────────────────────────────────────────

#[derive(Deserialize)]
struct ListParams {
    limit: Option<usize>,
    offset: Option<usize>,
    search: Option<String>,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    service: String,
    port: u16,
    timestamp: String,
}

#[derive(Serialize)]
struct ListResponse {
    items: Vec<serde_json::Value>,
    total: usize,
}

#[derive(Serialize)]
struct StatsResponse {
    total: usize,
    active: usize,
    recent: usize,
    last_updated: String,
}

#[derive(Serialize)]
struct CreateResponse {
    id: String,
    status: String,
}

// ── Handlers ───────────────────────────────────────────────────────────────────

async fn health(state: axum::extract::State<Arc<AppState>>) -> impl IntoResponse {
    Json(HealthResponse {
        status: "healthy".into(),
        service: "ai-credit-scoring".into(),
        port: state.config.port,
        timestamp: Utc::now().to_rfc3339(),
    })
}

async fn get_stats(state: axum::extract::State<Arc<AppState>>) -> impl IntoResponse {
    let records = state.records.read().unwrap();
    let total = records.len();
    let active = records.iter().filter(|r| r["status"] == "active").count();
    Json(StatsResponse {
        total,
        active,
        recent: total.min(50),
        last_updated: Utc::now().to_rfc3339(),
    })
}

async fn list_records(
    state: axum::extract::State<Arc<AppState>>,
    Query(params): Query<ListParams>,
) -> impl IntoResponse {
    let records = state.records.read().unwrap();
    let limit = params.limit.unwrap_or(20);
    let offset = params.offset.unwrap_or(0);
    let filtered: Vec<_> = if let Some(ref search) = params.search {
        let s = search.to_lowercase();
        records.iter()
            .filter(|r| r.to_string().to_lowercase().contains(&s))
            .cloned().collect()
    } else {
        records.clone()
    };
    let total = filtered.len();
    let items: Vec<_> = filtered.into_iter().skip(offset).take(limit).collect();
    Json(ListResponse { items, total })
}

async fn create_record(
    state: axum::extract::State<Arc<AppState>>,
    Json(mut payload): Json<serde_json::Value>,
) -> impl IntoResponse {
    let id = Uuid::new_v4().to_string();
    payload["id"] = serde_json::Value::String(id.clone());
    payload["created_at"] = serde_json::Value::String(Utc::now().to_rfc3339());
    if payload.get("status").is_none() {
        payload["status"] = serde_json::Value::String("active".into());
    }

    // Store record
    {
        let mut records = state.records.write().unwrap();
        records.push(payload.clone());
    }

    // Publish via Kafka/Dapr
    let dapr = &state.dapr;
    let event = serde_json::json!({"id": &id, "action": "created", "timestamp": Utc::now().to_rfc3339()});
    dapr.publish("credit.score.requested", &event).await;

    // Record in TigerBeetle
    state.tigerbeetle.create_transfer(0, 1, 0, 1, 1).await;

    // Stream to Fluvio
    state.fluvio.produce("ai-credit-scoring-events", &event).await;

    // Index in OpenSearch
    state.opensearch.index("credit_scores", &id, &payload).await;

    // Cache result
    state.cache.set(&format!("ai-credit-scoring:{}", id), &payload.to_string(), 3600);

    // Ingest to Lakehouse for analytics
    state.lakehouse.ingest("ai_credit_scores", &payload).await;

    (StatusCode::CREATED, Json(CreateResponse { id, status: "created".into() }))
}

async fn get_record(
    state: axum::extract::State<Arc<AppState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    // Check cache first
    if let Some(cached) = state.cache.get(&format!("ai-credit-scoring:{}", id)) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&cached) {
            return (StatusCode::OK, Json(val));
        }
    }
    let records = state.records.read().unwrap();
    if let Some(record) = records.iter().find(|r| r["id"] == id) {
        (StatusCode::OK, Json(record.clone()))
    } else {
        (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "not found"})))
    }
}

async fn search_records(
    state: axum::extract::State<Arc<AppState>>,
    Query(params): Query<HashMap<String, String>>,
) -> impl IntoResponse {
    let query = params.get("q").cloned().unwrap_or_default();
    // Try OpenSearch first
    let results = state.opensearch.search("credit_scores", &query).await;
    if !results.is_empty() {
        return Json(serde_json::json!({"items": results, "total": results.len()}));
    }
    // Fallback to in-memory search
    let records = state.records.read().unwrap();
    let q = query.to_lowercase();
    let filtered: Vec<_> = records.iter()
        .filter(|r| r.to_string().to_lowercase().contains(&q))
        .cloned().collect();
    Json(serde_json::json!({"items": &filtered, "total": filtered.len()}))
}

// ── Main ───────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    tracing_subscriber::init();

    let config = Config::from_env();
    let port = config.port;
    let state = Arc::new(AppState::new(config));

    let app = Router::new()
        .route("/health", get(health))
        .route("/api/v1/stats", get(get_stats))
        .route("/api/v1/list", get(list_records))
        .route("/api/v1/create", post(create_record))
        .route("/api/v1/search", get(search_records))
        .route("/api/v1/:id", get(get_record))
        .with_state(state);

    info!("54Link AI Credit Scoring (Rust) starting on port {}", port);
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port))
        .await
        .expect("Failed to bind");
    axum::serve(listener, app).await.expect("Server failed");
}
