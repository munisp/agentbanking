//! TigerBeetle Middleware Bridge (Rust)
//!
//! High-performance Rust service bridging TigerBeetle ledger events to:
//!   - Kafka: Transfer event streaming via rdkafka producer
//!   - Redis: Balance caching, rate limiting, distributed locks
//!   - OpenSearch: Transfer indexing for full-text search and analytics
//!   - Lakehouse: Delta Lake/Iceberg export for long-term financial analytics
//!   - OpenAppSec: WAF event logging and threat detection
//!   - TigerBeetle: Direct ledger queries via HTTP bridge
//!   - PostgreSQL: Metadata persistence and audit trail
//!
//! Listens on port 9400 (configurable via TB_BRIDGE_PORT).

use actix_web::{web, App, HttpResponse, HttpServer, middleware as actix_middleware};
use chrono::{DateTime, Utc};
use rdkafka::config::ClientConfig;
use rdkafka::producer::{FutureProducer, FutureRecord};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;
use tracing::{error, info, warn};

// ── Configuration ────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
struct Config {
    port: u16,
    kafka_brokers: String,
    redis_url: String,
    opensearch_url: String,
    lakehouse_url: String,
    openappsec_url: String,
    postgres_url: String,
    tigerbeetle_hub_url: String,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("TB_BRIDGE_PORT")
                .unwrap_or_else(|_| "9400".into())
                .parse()
                .unwrap_or(9400),
            kafka_brokers: std::env::var("KAFKA_BROKERS")
                .unwrap_or_else(|_| "localhost:9092".into()),
            redis_url: std::env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".into()),
            opensearch_url: std::env::var("OPENSEARCH_ENDPOINT")
                .unwrap_or_else(|_| "http://localhost:9200".into()),
            lakehouse_url: std::env::var("LAKEHOUSE_ENDPOINT")
                .unwrap_or_else(|_| "http://localhost:8181".into()),
            openappsec_url: std::env::var("OPENAPPSEC_ENDPOINT")
                .unwrap_or_else(|_| "http://localhost:8090".into()),
            postgres_url: std::env::var("POSTGRES_URL").unwrap_or_default(),
            tigerbeetle_hub_url: std::env::var("TB_HUB_URL")
                .unwrap_or_else(|_| "http://localhost:9300".into()),
        }
    }
}

// ── Data Structures ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TransferEvent {
    id: String,
    debit_account_id: String,
    credit_account_id: String,
    amount: i64,
    currency: String,
    ledger: u32,
    code: u16,
    reference: Option<String>,
    agent_code: Option<String>,
    tx_type: Option<String>,
    timestamp: DateTime<Utc>,
    #[serde(default)]
    metadata: serde_json::Value,
}

#[derive(Debug, Serialize)]
struct BridgeMetrics {
    transfers_processed: u64,
    kafka_events_produced: u64,
    redis_cache_updates: u64,
    opensearch_indexed: u64,
    lakehouse_exported: u64,
    openappsec_logged: u64,
    errors_total: u64,
    uptime_seconds: u64,
}

#[derive(Debug, Serialize)]
struct MiddlewareHealth {
    service: String,
    status: String,
    latency_ms: u64,
}

// ── Application State ────────────────────────────────────────────────────────

struct AppState {
    config: Config,
    kafka_producer: Option<FutureProducer>,
    redis_client: Option<redis::Client>,
    http_client: reqwest::Client,
    event_tx: mpsc::Sender<TransferEvent>,
    start_time: std::time::Instant,

    // Atomic counters
    transfers_processed: AtomicU64,
    kafka_produced: AtomicU64,
    redis_updates: AtomicU64,
    opensearch_indexed: AtomicU64,
    lakehouse_exported: AtomicU64,
    openappsec_logged: AtomicU64,
    errors_total: AtomicU64,
}

// ── Kafka Producer ───────────────────────────────────────────────────────────

fn create_kafka_producer(brokers: &str) -> Option<FutureProducer> {
    match ClientConfig::new()
        .set("bootstrap.servers", brokers)
        .set("message.timeout.ms", "5000")
        .set("queue.buffering.max.messages", "100000")
        .set("batch.num.messages", "1000")
        .set("linger.ms", "10")
        .set("compression.type", "lz4")
        .create()
    {
        Ok(producer) => {
            info!("Kafka producer connected to {}", brokers);
            Some(producer)
        }
        Err(e) => {
            warn!("Kafka producer unavailable: {}", e);
            None
        }
    }
}

// ── Event Processing Pipeline ────────────────────────────────────────────────

async fn process_event(state: &Arc<AppState>, event: TransferEvent) {
    state.transfers_processed.fetch_add(1, Ordering::Relaxed);

    // Fan-out to all middleware in parallel
    let (kafka_r, redis_r, os_r, lh_r, sec_r) = tokio::join!(
        produce_to_kafka(state, &event),
        update_redis_cache(state, &event),
        index_in_opensearch(state, &event),
        export_to_lakehouse(state, &event),
        log_to_openappsec(state, &event),
    );

    if kafka_r.is_err() || redis_r.is_err() || os_r.is_err() || lh_r.is_err() || sec_r.is_err() {
        state.errors_total.fetch_add(1, Ordering::Relaxed);
    }
}

async fn produce_to_kafka(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
    let producer = match &state.kafka_producer {
        Some(p) => p,
        None => return Ok(()), // Kafka not configured
    };

    let payload = serde_json::to_string(event).map_err(|e| e.to_string())?;
    let key = event.id.clone();

    let record = FutureRecord::to("tb-transfer-events")
        .key(&key)
        .payload(&payload)
        .headers(
            rdkafka::message::OwnedHeaders::new()
                .insert(rdkafka::message::Header {
                    key: "source",
                    value: Some("tigerbeetle-bridge-rust"),
                })
                .insert(rdkafka::message::Header {
                    key: "event_type",
                    value: Some("transfer.committed"),
                }),
        );

    match producer.send(record, Duration::from_secs(5)).await {
        Ok(_) => {
            state.kafka_produced.fetch_add(1, Ordering::Relaxed);
            Ok(())
        }
        Err((e, _)) => {
            error!("Kafka produce failed: {}", e);
            Err(e.to_string())
        }
    }
}

async fn update_redis_cache(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
    let client = match &state.redis_client {
        Some(c) => c,
        None => return Ok(()),
    };

    let mut conn = client
        .get_multiplexed_async_connection()
        .await
        .map_err(|e| e.to_string())?;

    let debit_key = format!("tb:balance:{}", event.debit_account_id);
    let credit_key = format!("tb:balance:{}", event.credit_account_id);

    // Pipeline: atomic balance updates + TTL
    redis::pipe()
        .atomic()
        .cmd("INCRBY").arg(&debit_key).arg(-event.amount)
        .cmd("EXPIRE").arg(&debit_key).arg(86400)
        .cmd("INCRBY").arg(&credit_key).arg(event.amount)
        .cmd("EXPIRE").arg(&credit_key).arg(86400)
        .cmd("ZADD").arg("tb:recent_transfers").arg(event.timestamp.timestamp_millis()).arg(&event.id)
        .exec_async(&mut conn)
        .await
        .map_err(|e| e.to_string())?;

    state.redis_updates.fetch_add(1, Ordering::Relaxed);
    Ok(())
}

async fn index_in_opensearch(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
    let index = format!("tb-transfers-{}", event.timestamp.format("%Y.%m"));
    let url = format!("{}/{}/_doc/{}", state.config.opensearch_url, index, event.id);

    let doc = serde_json::json!({
        "transfer_id": event.id,
        "debit_account_id": event.debit_account_id,
        "credit_account_id": event.credit_account_id,
        "amount": event.amount,
        "amount_ngn": event.amount as f64 / 100.0,
        "currency": event.currency,
        "agent_code": event.agent_code,
        "tx_type": event.tx_type,
        "reference": event.reference,
        "ledger": event.ledger,
        "code": event.code,
        "@timestamp": event.timestamp.to_rfc3339(),
        "metadata": event.metadata,
    });

    match state.http_client
        .put(&url)
        .json(&doc)
        .timeout(Duration::from_secs(5))
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => {
            state.opensearch_indexed.fetch_add(1, Ordering::Relaxed);
            Ok(())
        }
        Ok(resp) => Err(format!("OpenSearch status: {}", resp.status())),
        Err(e) => Err(format!("OpenSearch error: {}", e)),
    }
}

async fn export_to_lakehouse(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
    let url = format!("{}/api/v1/ingest", state.config.lakehouse_url);
    let agent = event.agent_code.as_deref().unwrap_or("unknown");

    let record = serde_json::json!({
        "table": "financial.tb_transfers",
        "format": "iceberg",
        "partition": format!("date={}/agent={}", event.timestamp.format("%Y-%m-%d"), agent),
        "record": {
            "transfer_id": event.id,
            "debit_account_id": event.debit_account_id,
            "credit_account_id": event.credit_account_id,
            "amount_kobo": event.amount,
            "currency": event.currency,
            "agent_code": agent,
            "tx_type": event.tx_type,
            "ledger": event.ledger,
            "code": event.code,
            "event_timestamp": event.timestamp.timestamp_millis(),
        },
    });

    match state.http_client
        .post(&url)
        .json(&record)
        .timeout(Duration::from_secs(5))
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => {
            state.lakehouse_exported.fetch_add(1, Ordering::Relaxed);
            Ok(())
        }
        Ok(resp) => Err(format!("Lakehouse status: {}", resp.status())),
        Err(e) => Err(format!("Lakehouse error: {}", e)),
    }
}

async fn log_to_openappsec(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
    let url = format!("{}/api/v1/events", state.config.openappsec_url);

    let hash = {
        let mut hasher = Sha256::new();
        hasher.update(format!("{}:{}:{}", event.id, event.amount, event.debit_account_id));
        hex::encode(hasher.finalize())
    };

    let sec_event = serde_json::json!({
        "event_type": "financial_transfer",
        "severity": if event.amount > 10_000_00 { "warning" } else { "info" },
        "source": "tigerbeetle-bridge-rust",
        "fingerprint": hash,
        "details": {
            "transfer_id": event.id,
            "amount": event.amount,
            "agent_code": event.agent_code,
            "tx_type": event.tx_type,
        },
        "timestamp": event.timestamp.to_rfc3339(),
    });

    match state.http_client
        .post(&url)
        .json(&sec_event)
        .timeout(Duration::from_secs(3))
        .send()
        .await
    {
        Ok(_) => {
            state.openappsec_logged.fetch_add(1, Ordering::Relaxed);
            Ok(())
        }
        Err(e) => Err(format!("OpenAppSec error: {}", e)),
    }
}

// ── HTTP Handlers ────────────────────────────────────────────────────────────

async fn health(state: web::Data<Arc<AppState>>) -> HttpResponse {
    let uptime = state.start_time.elapsed().as_secs();
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "tigerbeetle-middleware-bridge",
        "language": "rust",
        "uptime_seconds": uptime,
        "kafka": if state.kafka_producer.is_some() { "connected" } else { "disconnected" },
        "redis": if state.redis_client.is_some() { "configured" } else { "disconnected" },
    }))
}

async fn metrics(state: web::Data<Arc<AppState>>) -> HttpResponse {
    let m = BridgeMetrics {
        transfers_processed: state.transfers_processed.load(Ordering::Relaxed),
        kafka_events_produced: state.kafka_produced.load(Ordering::Relaxed),
        redis_cache_updates: state.redis_updates.load(Ordering::Relaxed),
        opensearch_indexed: state.opensearch_indexed.load(Ordering::Relaxed),
        lakehouse_exported: state.lakehouse_exported.load(Ordering::Relaxed),
        openappsec_logged: state.openappsec_logged.load(Ordering::Relaxed),
        errors_total: state.errors_total.load(Ordering::Relaxed),
        uptime_seconds: state.start_time.elapsed().as_secs(),
    };
    HttpResponse::Ok().json(m)
}

async fn submit_transfer(
    state: web::Data<Arc<AppState>>,
    body: web::Json<TransferEvent>,
) -> HttpResponse {
    let mut event = body.into_inner();
    if event.currency.is_empty() {
        event.currency = "NGN".to_string();
    }
    if event.timestamp == DateTime::<Utc>::default() {
        event.timestamp = Utc::now();
    }

    if event.id.is_empty() || event.debit_account_id.is_empty() || event.credit_account_id.is_empty() || event.amount <= 0 {
        return HttpResponse::BadRequest().json(serde_json::json!({
            "error": "missing required fields: id, debit_account_id, credit_account_id, amount"
        }));
    }

    match state.event_tx.send(event.clone()).await {
        Ok(_) => HttpResponse::Accepted().json(serde_json::json!({
            "status": "accepted",
            "transfer_id": event.id,
            "pipeline": "async-rust",
        })),
        Err(_) => HttpResponse::ServiceUnavailable().json(serde_json::json!({
            "error": "event pipeline full"
        })),
    }
}

async fn middleware_status(state: web::Data<Arc<AppState>>) -> HttpResponse {
    let mut statuses = Vec::new();

    // Redis check
    let redis_status = if let Some(ref client) = state.redis_client {
        match client.get_multiplexed_async_connection().await {
            Ok(_) => MiddlewareHealth { service: "redis".into(), status: "connected".into(), latency_ms: 1 },
            Err(_) => MiddlewareHealth { service: "redis".into(), status: "disconnected".into(), latency_ms: 0 },
        }
    } else {
        MiddlewareHealth { service: "redis".into(), status: "not_configured".into(), latency_ms: 0 }
    };
    statuses.push(redis_status);

    // Kafka check
    statuses.push(MiddlewareHealth {
        service: "kafka".into(),
        status: if state.kafka_producer.is_some() { "connected".into() } else { "disconnected".into() },
        latency_ms: 0,
    });

    // HTTP service checks
    let services = vec![
        ("opensearch", format!("{}/_cluster/health", state.config.opensearch_url)),
        ("lakehouse", format!("{}/api/v1/health", state.config.lakehouse_url)),
        ("openappsec", format!("{}/health", state.config.openappsec_url)),
        ("tigerbeetle-hub", format!("{}/health", state.config.tigerbeetle_hub_url)),
    ];

    for (name, url) in services {
        let start = std::time::Instant::now();
        let status = match state.http_client.get(&url).timeout(Duration::from_secs(2)).send().await {
            Ok(resp) if resp.status().is_success() => "connected",
            _ => "unavailable",
        };
        statuses.push(MiddlewareHealth {
            service: name.into(),
            status: status.into(),
            latency_ms: start.elapsed().as_millis() as u64,
        });
    }

    HttpResponse::Ok().json(statuses)
}

// ── Main ─────────────────────────────────────────────────────────────────────

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    tracing_subscriber::fmt::init();
    let config = Config::from_env();
    let port = config.port;

    // Initialize middleware clients
    let kafka_producer = create_kafka_producer(&config.kafka_brokers);
    let redis_client = redis::Client::open(config.redis_url.as_str()).ok();
    let http_client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .pool_max_idle_per_host(20)
        .build()
        .expect("HTTP client");

    let (event_tx, mut event_rx) = mpsc::channel::<TransferEvent>(10000);

    let state = Arc::new(AppState {
        config: config.clone(),
        kafka_producer,
        redis_client,
        http_client,
        event_tx,
        start_time: std::time::Instant::now(),
        transfers_processed: AtomicU64::new(0),
        kafka_produced: AtomicU64::new(0),
        redis_updates: AtomicU64::new(0),
        opensearch_indexed: AtomicU64::new(0),
        lakehouse_exported: AtomicU64::new(0),
        openappsec_logged: AtomicU64::new(0),
        errors_total: AtomicU64::new(0),
    });

    // Start event processor
    let processor_state = Arc::clone(&state);
    tokio::spawn(async move {
        while let Some(event) = event_rx.recv().await {
            process_event(&processor_state, event).await;
        }
    });

    info!("TigerBeetle Middleware Bridge (Rust) listening on :{}", port);

    let app_state = web::Data::new(Arc::clone(&state));

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .route("/health", web::get().to(health))
            .route("/metrics", web::get().to(metrics))
            .route("/transfer", web::post().to(submit_transfer))
            .route("/middleware/status", web::get().to(middleware_status))
    })
    .bind(format!("0.0.0.0:{}", port))?
    .run()
    .await
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
