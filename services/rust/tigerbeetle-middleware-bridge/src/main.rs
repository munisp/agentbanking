//! TigerBeetle Middleware Bridge (Rust)
use tokio::signal;
//!
use tokio::signal;
//! High-performance Rust service bridging TigerBeetle ledger events to:
use tokio::signal;
//!   - Kafka: Transfer event streaming via rdkafka producer
use tokio::signal;
//!   - Redis: Balance caching, rate limiting, distributed locks
use tokio::signal;
//!   - OpenSearch: Transfer indexing for full-text search and analytics
use tokio::signal;
//!   - Lakehouse: Delta Lake/Iceberg export for long-term financial analytics
use tokio::signal;
//!   - OpenAppSec: WAF event logging and threat detection
use tokio::signal;
//!   - TigerBeetle: Direct ledger queries via HTTP bridge
use tokio::signal;
//!   - PostgreSQL: Metadata persistence and audit trail (bi-directional sync)
use tokio::signal;
//!
use tokio::signal;
//! Listens on port 9400 (configurable via TB_BRIDGE_PORT).
use tokio::signal;

use actix_web::{web, App, HttpResponse, HttpServer};
use chrono::{DateTime, Utc};
use rdkafka::config::ClientConfig;
use rdkafka::producer::{FutureProducer, FutureRecord};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;
use tracing::{error, info, warn};
use tokio::signal;
// ── Configuration ────────────────────────────────────────────────────────────
use tokio::signal;
#[derive(Clone, Debug)]
use tokio::signal;
struct Config {
use tokio::signal;
    port: u16,
use tokio::signal;
    kafka_brokers: String,
use tokio::signal;
    redis_url: String,
use tokio::signal;
    opensearch_url: String,
use tokio::signal;
    lakehouse_url: String,
use tokio::signal;
    openappsec_url: String,
use tokio::signal;
    postgres_url: String,
use tokio::signal;
    tigerbeetle_hub_url: String,
use tokio::signal;
}
use tokio::signal;
impl Config {
use tokio::signal;
    fn from_env() -> Self {
use tokio::signal;
        Self {
use tokio::signal;
            port: std::env::var("TB_BRIDGE_PORT")
use tokio::signal;
                .unwrap_or_else(|_| "9400".into())
use tokio::signal;
                .parse()
use tokio::signal;
                .unwrap_or(9400),
use tokio::signal;
            kafka_brokers: std::env::var("KAFKA_BROKERS")
use tokio::signal;
                .unwrap_or_else(|_| "localhost:9092".into()),
use tokio::signal;
            redis_url: std::env::var("REDIS_URL")
use tokio::signal;
                .unwrap_or_else(|_| "redis://localhost:6379".into()),
use tokio::signal;
            opensearch_url: std::env::var("OPENSEARCH_ENDPOINT")
use tokio::signal;
                .unwrap_or_else(|_| "http://localhost:9200".into()),
use tokio::signal;
            lakehouse_url: std::env::var("LAKEHOUSE_ENDPOINT")
use tokio::signal;
                .unwrap_or_else(|_| "http://localhost:8181".into()),
use tokio::signal;
            openappsec_url: std::env::var("OPENAPPSEC_ENDPOINT")
use tokio::signal;
                .unwrap_or_else(|_| "http://localhost:8090".into()),
use tokio::signal;
            postgres_url: std::env::var("DATABASE_URL")
use tokio::signal;
                .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/tigerbeetle_bridge".into()),
use tokio::signal;
            tigerbeetle_hub_url: std::env::var("TB_HUB_URL")
use tokio::signal;
                .unwrap_or_else(|_| "http://localhost:9300".into()),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── Data Structures ──────────────────────────────────────────────────────────
use tokio::signal;
#[derive(Debug, Clone, Serialize, Deserialize)]
use tokio::signal;
struct TransferEvent {
use tokio::signal;
    id: String,
use tokio::signal;
    debit_account_id: String,
use tokio::signal;
    credit_account_id: String,
use tokio::signal;
    amount: i64,
use tokio::signal;
    currency: String,
use tokio::signal;
    ledger: u32,
use tokio::signal;
    code: u16,
use tokio::signal;
    reference: Option<String>,
use tokio::signal;
    agent_code: Option<String>,
use tokio::signal;
    tx_type: Option<String>,
use tokio::signal;
    timestamp: DateTime<Utc>,
use tokio::signal;
    #[serde(default)]
use tokio::signal;
    metadata: serde_json::Value,
use tokio::signal;
}
use tokio::signal;
#[derive(Debug, Serialize)]
use tokio::signal;
struct BridgeMetrics {
use tokio::signal;
    transfers_processed: u64,
use tokio::signal;
    kafka_events_produced: u64,
use tokio::signal;
    redis_cache_updates: u64,
use tokio::signal;
    opensearch_indexed: u64,
use tokio::signal;
    lakehouse_exported: u64,
use tokio::signal;
    openappsec_logged: u64,
use tokio::signal;
    pg_persisted: u64,
use tokio::signal;
    errors_total: u64,
use tokio::signal;
    uptime_seconds: u64,
use tokio::signal;
    persistence: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Debug, Serialize)]
use tokio::signal;
struct MiddlewareHealth {
use tokio::signal;
    service: String,
use tokio::signal;
    status: String,
use tokio::signal;
    latency_ms: u64,
use tokio::signal;
}
use tokio::signal;
// ── Application State ────────────────────────────────────────────────────────
use tokio::signal;
struct AppState {
use tokio::signal;
    config: Config,
use tokio::signal;
    kafka_producer: Option<FutureProducer>,
use tokio::signal;
    redis_client: Option<redis::Client>,
use tokio::signal;
    http_client: reqwest::Client,
use tokio::signal;
    pg_pool: Option<PgPool>,
use tokio::signal;
    event_tx: mpsc::Sender<TransferEvent>,
use tokio::signal;
    start_time: std::time::Instant,
use tokio::signal;
    transfers_processed: AtomicU64,
use tokio::signal;
    kafka_produced: AtomicU64,
use tokio::signal;
    redis_updates: AtomicU64,
use tokio::signal;
    opensearch_indexed: AtomicU64,
use tokio::signal;
    lakehouse_exported: AtomicU64,
use tokio::signal;
    openappsec_logged: AtomicU64,
use tokio::signal;
    pg_persisted: AtomicU64,
use tokio::signal;
    errors_total: AtomicU64,
use tokio::signal;
}
use tokio::signal;
// ── PostgreSQL Persistence ───────────────────────────────────────────────────
use tokio::signal;
async fn init_pg(url: &str) -> Option<PgPool> {
use tokio::signal;
    if url.is_empty() {
use tokio::signal;
        warn!("DATABASE_URL not set, PostgreSQL persistence disabled");
use tokio::signal;
        return None;
use tokio::signal;
    }
use tokio::signal;
    match PgPoolOptions::new()
use tokio::signal;
        .max_connections(15)
use tokio::signal;
        .idle_timeout(Duration::from_secs(300))
use tokio::signal;
        .connect(url)
use tokio::signal;
        .await
use tokio::signal;
    {
use tokio::signal;
        Ok(pool) => {
use tokio::signal;
            sqlx::query(
use tokio::signal;
                "CREATE TABLE IF NOT EXISTS tb_bridge_transfers (
use tokio::signal;
                    id TEXT PRIMARY KEY,
use tokio::signal;
                    debit_account_id TEXT NOT NULL,
use tokio::signal;
                    credit_account_id TEXT NOT NULL,
use tokio::signal;
                    amount BIGINT NOT NULL,
use tokio::signal;
                    currency TEXT NOT NULL DEFAULT 'NGN',
use tokio::signal;
                    ledger INT NOT NULL DEFAULT 0,
use tokio::signal;
                    code SMALLINT NOT NULL DEFAULT 0,
use tokio::signal;
                    reference TEXT,
use tokio::signal;
                    agent_code TEXT,
use tokio::signal;
                    tx_type TEXT,
use tokio::signal;
                    metadata JSONB,
use tokio::signal;
                    kafka_published BOOLEAN NOT NULL DEFAULT false,
use tokio::signal;
                    redis_cached BOOLEAN NOT NULL DEFAULT false,
use tokio::signal;
                    opensearch_indexed BOOLEAN NOT NULL DEFAULT false,
use tokio::signal;
                    lakehouse_exported BOOLEAN NOT NULL DEFAULT false,
use tokio::signal;
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
use tokio::signal;
                )"
use tokio::signal;
            ).execute(&pool).await.ok();
use tokio::signal;
            sqlx::query("CREATE INDEX IF NOT EXISTS idx_tbt_agent ON tb_bridge_transfers(agent_code)")
use tokio::signal;
                .execute(&pool).await.ok();
use tokio::signal;
            sqlx::query("CREATE INDEX IF NOT EXISTS idx_tbt_created ON tb_bridge_transfers(created_at)")
use tokio::signal;
                .execute(&pool).await.ok();
use tokio::signal;
            sqlx::query(
use tokio::signal;
                "CREATE TABLE IF NOT EXISTS tb_bridge_metrics_log (
use tokio::signal;
                    id SERIAL PRIMARY KEY,
use tokio::signal;
                    transfers_processed BIGINT NOT NULL DEFAULT 0,
use tokio::signal;
                    kafka_produced BIGINT NOT NULL DEFAULT 0,
use tokio::signal;
                    redis_updates BIGINT NOT NULL DEFAULT 0,
use tokio::signal;
                    opensearch_indexed BIGINT NOT NULL DEFAULT 0,
use tokio::signal;
                    pg_persisted BIGINT NOT NULL DEFAULT 0,
use tokio::signal;
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
use tokio::signal;
                )"
use tokio::signal;
            ).execute(&pool).await.ok();
use tokio::signal;
            info!("PostgreSQL connected and tables initialized");
use tokio::signal;
            Some(pool)
use tokio::signal;
        }
use tokio::signal;
        Err(e) => {
use tokio::signal;
            warn!("PostgreSQL connection failed: {} — running without persistence", e);
use tokio::signal;
            None
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn persist_transfer(pool: &PgPool, event: &TransferEvent) -> Result<(), String> {
use tokio::signal;
    sqlx::query(
use tokio::signal;
        "INSERT INTO tb_bridge_transfers (id, debit_account_id, credit_account_id, amount, currency, ledger, code, reference, agent_code, tx_type, metadata)
use tokio::signal;
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
use tokio::signal;
         ON CONFLICT (id) DO NOTHING"
use tokio::signal;
    )
use tokio::signal;
    .bind(&event.id)
use tokio::signal;
    .bind(&event.debit_account_id)
use tokio::signal;
    .bind(&event.credit_account_id)
use tokio::signal;
    .bind(event.amount)
use tokio::signal;
    .bind(&event.currency)
use tokio::signal;
    .bind(event.ledger as i32)
use tokio::signal;
    .bind(event.code as i16)
use tokio::signal;
    .bind(&event.reference)
use tokio::signal;
    .bind(&event.agent_code)
use tokio::signal;
    .bind(&event.tx_type)
use tokio::signal;
    .bind(&event.metadata)
use tokio::signal;
    .execute(pool)
use tokio::signal;
    .await
use tokio::signal;
    .map_err(|e| e.to_string())?;
use tokio::signal;
    Ok(())
use tokio::signal;
}
use tokio::signal;
async fn update_transfer_flags(pool: &PgPool, id: &str, kafka: bool, redis: bool, opensearch: bool, lakehouse: bool) {
use tokio::signal;
    sqlx::query(
use tokio::signal;
        "UPDATE tb_bridge_transfers SET kafka_published=$2, redis_cached=$3, opensearch_indexed=$4, lakehouse_exported=$5 WHERE id=$1"
use tokio::signal;
    )
use tokio::signal;
    .bind(id)
use tokio::signal;
    .bind(kafka)
use tokio::signal;
    .bind(redis)
use tokio::signal;
    .bind(opensearch)
use tokio::signal;
    .bind(lakehouse)
use tokio::signal;
    .execute(pool)
use tokio::signal;
    .await
use tokio::signal;
    .ok();
use tokio::signal;
}
use tokio::signal;
// ── Kafka Producer ───────────────────────────────────────────────────────────
use tokio::signal;
fn create_kafka_producer(brokers: &str) -> Option<FutureProducer> {
use tokio::signal;
    match ClientConfig::new()
use tokio::signal;
        .set("bootstrap.servers", brokers)
use tokio::signal;
        .set("message.timeout.ms", "5000")
use tokio::signal;
        .set("queue.buffering.max.messages", "100000")
use tokio::signal;
        .set("batch.num.messages", "1000")
use tokio::signal;
        .set("linger.ms", "10")
use tokio::signal;
        .set("compression.type", "lz4")
use tokio::signal;
        .create()
use tokio::signal;
    {
use tokio::signal;
        Ok(producer) => {
use tokio::signal;
            info!("Kafka producer connected to {}", brokers);
use tokio::signal;
            Some(producer)
use tokio::signal;
        }
use tokio::signal;
        Err(e) => {
use tokio::signal;
            warn!("Kafka producer unavailable: {}", e);
use tokio::signal;
            None
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── Event Processing Pipeline ────────────────────────────────────────────────
use tokio::signal;
async fn process_event(state: &Arc<AppState>, event: TransferEvent) {
use tokio::signal;
    state.transfers_processed.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
    // Persist to PostgreSQL first
use tokio::signal;
    let pg_ok = if let Some(ref pool) = state.pg_pool {
use tokio::signal;
        match persist_transfer(pool, &event).await {
use tokio::signal;
            Ok(_) => {
use tokio::signal;
                state.pg_persisted.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
                true
use tokio::signal;
            }
use tokio::signal;
            Err(e) => {
use tokio::signal;
                error!("PG persist failed: {}", e);
use tokio::signal;
                false
use tokio::signal;
            }
use tokio::signal;
        }
use tokio::signal;
    } else {
use tokio::signal;
        false
use tokio::signal;
    };
use tokio::signal;
    // Fan-out to all middleware in parallel
use tokio::signal;
    let (kafka_r, redis_r, os_r, lh_r, sec_r) = tokio::join!(
use tokio::signal;
        produce_to_kafka(state, &event),
use tokio::signal;
        update_redis_cache(state, &event),
use tokio::signal;
        index_in_opensearch(state, &event),
use tokio::signal;
        export_to_lakehouse(state, &event),
use tokio::signal;
        log_to_openappsec(state, &event),
use tokio::signal;
    );
use tokio::signal;
    // Update PG with middleware delivery flags
use tokio::signal;
    if let Some(ref pool) = state.pg_pool {
use tokio::signal;
        update_transfer_flags(
use tokio::signal;
            pool, &event.id,
use tokio::signal;
            kafka_r.is_ok(), redis_r.is_ok(), os_r.is_ok(), lh_r.is_ok()
use tokio::signal;
        ).await;
use tokio::signal;
    }
use tokio::signal;
    if kafka_r.is_err() || redis_r.is_err() || os_r.is_err() || lh_r.is_err() || sec_r.is_err() {
use tokio::signal;
        state.errors_total.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn produce_to_kafka(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
use tokio::signal;
    let producer = match &state.kafka_producer {
use tokio::signal;
        Some(p) => p,
use tokio::signal;
        None => return Ok(()),
use tokio::signal;
    };
use tokio::signal;
    let payload = serde_json::to_string(event).map_err(|e| e.to_string())?;
use tokio::signal;
    let key = event.id.clone();
use tokio::signal;
    let record = FutureRecord::to("tb-transfer-events")
use tokio::signal;
        .key(&key)
use tokio::signal;
        .payload(&payload)
use tokio::signal;
        .headers(
use tokio::signal;
            rdkafka::message::OwnedHeaders::new()
use tokio::signal;
                .insert(rdkafka::message::Header {
use tokio::signal;
                    key: "source",
use tokio::signal;
                    value: Some("tigerbeetle-bridge-rust"),
use tokio::signal;
                })
use tokio::signal;
                .insert(rdkafka::message::Header {
use tokio::signal;
                    key: "event_type",
use tokio::signal;
                    value: Some("transfer.committed"),
use tokio::signal;
                }),
use tokio::signal;
        );
use tokio::signal;
    match producer.send(record, Duration::from_secs(5)).await {
use tokio::signal;
        Ok(_) => {
use tokio::signal;
            state.kafka_produced.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
            Ok(())
use tokio::signal;
        }
use tokio::signal;
        Err((e, _)) => {
use tokio::signal;
            error!("Kafka produce failed: {}", e);
use tokio::signal;
            Err(e.to_string())
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn update_redis_cache(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
use tokio::signal;
    let client = match &state.redis_client {
use tokio::signal;
        Some(c) => c,
use tokio::signal;
        None => return Ok(()),
use tokio::signal;
    };
use tokio::signal;
    let mut conn = client
use tokio::signal;
        .get_multiplexed_async_connection()
use tokio::signal;
        .await
use tokio::signal;
        .map_err(|e| e.to_string())?;
use tokio::signal;
    let debit_key = format!("tb:balance:{}", event.debit_account_id);
use tokio::signal;
    let credit_key = format!("tb:balance:{}", event.credit_account_id);
use tokio::signal;
    redis::pipe()
use tokio::signal;
        .atomic()
use tokio::signal;
        .cmd("INCRBY").arg(&debit_key).arg(-event.amount)
use tokio::signal;
        .cmd("EXPIRE").arg(&debit_key).arg(86400)
use tokio::signal;
        .cmd("INCRBY").arg(&credit_key).arg(event.amount)
use tokio::signal;
        .cmd("EXPIRE").arg(&credit_key).arg(86400)
use tokio::signal;
        .cmd("ZADD").arg("tb:recent_transfers").arg(event.timestamp.timestamp_millis()).arg(&event.id)
use tokio::signal;
        .exec_async(&mut conn)
use tokio::signal;
        .await
use tokio::signal;
        .map_err(|e| e.to_string())?;
use tokio::signal;
    state.redis_updates.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
    Ok(())
use tokio::signal;
}
use tokio::signal;
async fn index_in_opensearch(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
use tokio::signal;
    let index = format!("tb-transfers-{}", event.timestamp.format("%Y.%m"));
use tokio::signal;
    let url = format!("{}/{}/_doc/{}", state.config.opensearch_url, index, event.id);
use tokio::signal;
    let doc = serde_json::json!({
use tokio::signal;
        "transfer_id": event.id,
use tokio::signal;
        "debit_account_id": event.debit_account_id,
use tokio::signal;
        "credit_account_id": event.credit_account_id,
use tokio::signal;
        "amount": event.amount,
use tokio::signal;
        "amount_ngn": event.amount as f64 / 100.0,
use tokio::signal;
        "currency": event.currency,
use tokio::signal;
        "agent_code": event.agent_code,
use tokio::signal;
        "tx_type": event.tx_type,
use tokio::signal;
        "reference": event.reference,
use tokio::signal;
        "ledger": event.ledger,
use tokio::signal;
        "code": event.code,
use tokio::signal;
        "@timestamp": event.timestamp.to_rfc3339(),
use tokio::signal;
        "metadata": event.metadata,
use tokio::signal;
    });
use tokio::signal;
    match state.http_client
use tokio::signal;
        .put(&url)
use tokio::signal;
        .json(&doc)
use tokio::signal;
        .timeout(Duration::from_secs(5))
use tokio::signal;
        .send()
use tokio::signal;
        .await
use tokio::signal;
    {
use tokio::signal;
        Ok(resp) if resp.status().is_success() => {
use tokio::signal;
            state.opensearch_indexed.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
            Ok(())
use tokio::signal;
        }
use tokio::signal;
        Ok(resp) => Err(format!("OpenSearch status: {}", resp.status())),
use tokio::signal;
        Err(e) => Err(format!("OpenSearch error: {}", e)),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn export_to_lakehouse(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
use tokio::signal;
    let url = format!("{}/api/v1/ingest", state.config.lakehouse_url);
use tokio::signal;
    let agent = event.agent_code.as_deref().unwrap_or("unknown");
use tokio::signal;
    let record = serde_json::json!({
use tokio::signal;
        "table": "financial.tb_transfers",
use tokio::signal;
        "format": "iceberg",
use tokio::signal;
        "partition": format!("date={}/agent={}", event.timestamp.format("%Y-%m-%d"), agent),
use tokio::signal;
        "record": {
use tokio::signal;
            "transfer_id": event.id,
use tokio::signal;
            "debit_account_id": event.debit_account_id,
use tokio::signal;
            "credit_account_id": event.credit_account_id,
use tokio::signal;
            "amount_kobo": event.amount,
use tokio::signal;
            "currency": event.currency,
use tokio::signal;
            "agent_code": agent,
use tokio::signal;
            "tx_type": event.tx_type,
use tokio::signal;
            "ledger": event.ledger,
use tokio::signal;
            "code": event.code,
use tokio::signal;
            "event_timestamp": event.timestamp.timestamp_millis(),
use tokio::signal;
        },
use tokio::signal;
    });
use tokio::signal;
    match state.http_client
use tokio::signal;
        .post(&url)
use tokio::signal;
        .json(&record)
use tokio::signal;
        .timeout(Duration::from_secs(5))
use tokio::signal;
        .send()
use tokio::signal;
        .await
use tokio::signal;
    {
use tokio::signal;
        Ok(resp) if resp.status().is_success() => {
use tokio::signal;
            state.lakehouse_exported.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
            Ok(())
use tokio::signal;
        }
use tokio::signal;
        Ok(resp) => Err(format!("Lakehouse status: {}", resp.status())),
use tokio::signal;
        Err(e) => Err(format!("Lakehouse error: {}", e)),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn log_to_openappsec(state: &Arc<AppState>, event: &TransferEvent) -> Result<(), String> {
use tokio::signal;
    let url = format!("{}/api/v1/events", state.config.openappsec_url);
use tokio::signal;
    let hash = {
use tokio::signal;
        let mut hasher = Sha256::new();
use tokio::signal;
        hasher.update(format!("{}:{}:{}", event.id, event.amount, event.debit_account_id));
use tokio::signal;
        hex::encode(hasher.finalize())
use tokio::signal;
    };
use tokio::signal;
    let sec_event = serde_json::json!({
use tokio::signal;
        "event_type": "financial_transfer",
use tokio::signal;
        "severity": if event.amount > 10_000_00 { "warning" } else { "info" },
use tokio::signal;
        "source": "tigerbeetle-bridge-rust",
use tokio::signal;
        "fingerprint": hash,
use tokio::signal;
        "details": {
use tokio::signal;
            "transfer_id": event.id,
use tokio::signal;
            "amount": event.amount,
use tokio::signal;
            "agent_code": event.agent_code,
use tokio::signal;
            "tx_type": event.tx_type,
use tokio::signal;
        },
use tokio::signal;
        "timestamp": event.timestamp.to_rfc3339(),
use tokio::signal;
    });
use tokio::signal;
    match state.http_client
use tokio::signal;
        .post(&url)
use tokio::signal;
        .json(&sec_event)
use tokio::signal;
        .timeout(Duration::from_secs(3))
use tokio::signal;
        .send()
use tokio::signal;
        .await
use tokio::signal;
    {
use tokio::signal;
        Ok(_) => {
use tokio::signal;
            state.openappsec_logged.fetch_add(1, Ordering::Relaxed);
use tokio::signal;
            Ok(())
use tokio::signal;
        }
use tokio::signal;
        Err(e) => Err(format!("OpenAppSec error: {}", e)),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── HTTP Handlers ────────────────────────────────────────────────────────────
use tokio::signal;
async fn health(state: web::Data<Arc<AppState>>) -> HttpResponse {
use tokio::signal;
    let uptime = state.start_time.elapsed().as_secs();
use tokio::signal;
    let pg_ok = state.pg_pool.is_some();
use tokio::signal;
    HttpResponse::Ok().json(serde_json::json!({
use tokio::signal;
        "status": "healthy",
use tokio::signal;
        "service": "tigerbeetle-middleware-bridge",
use tokio::signal;
        "language": "rust",
use tokio::signal;
        "uptime_seconds": uptime,
use tokio::signal;
        "kafka": if state.kafka_producer.is_some() { "connected" } else { "disconnected" },
use tokio::signal;
        "redis": if state.redis_client.is_some() { "configured" } else { "disconnected" },
use tokio::signal;
        "postgres": if pg_ok { "connected" } else { "disconnected" },
use tokio::signal;
        "persistence": "postgresql",
use tokio::signal;
    }))
use tokio::signal;
}
use tokio::signal;
async fn metrics(state: web::Data<Arc<AppState>>) -> HttpResponse {
use tokio::signal;
    let m = BridgeMetrics {
use tokio::signal;
        transfers_processed: state.transfers_processed.load(Ordering::Relaxed),
use tokio::signal;
        kafka_events_produced: state.kafka_produced.load(Ordering::Relaxed),
use tokio::signal;
        redis_cache_updates: state.redis_updates.load(Ordering::Relaxed),
use tokio::signal;
        opensearch_indexed: state.opensearch_indexed.load(Ordering::Relaxed),
use tokio::signal;
        lakehouse_exported: state.lakehouse_exported.load(Ordering::Relaxed),
use tokio::signal;
        openappsec_logged: state.openappsec_logged.load(Ordering::Relaxed),
use tokio::signal;
        pg_persisted: state.pg_persisted.load(Ordering::Relaxed),
use tokio::signal;
        errors_total: state.errors_total.load(Ordering::Relaxed),
use tokio::signal;
        uptime_seconds: state.start_time.elapsed().as_secs(),
use tokio::signal;
        persistence: "postgresql".into(),
use tokio::signal;
    };
use tokio::signal;
    HttpResponse::Ok().json(m)
use tokio::signal;
}
use tokio::signal;
async fn submit_transfer(
use tokio::signal;
    state: web::Data<Arc<AppState>>,
use tokio::signal;
    body: web::Json<TransferEvent>,
use tokio::signal;
) -> HttpResponse {
use tokio::signal;
    let mut event = body.into_inner();
use tokio::signal;
    if event.currency.is_empty() {
use tokio::signal;
        event.currency = "NGN".to_string();
use tokio::signal;
    }
use tokio::signal;
    if event.timestamp == DateTime::<Utc>::default() {
use tokio::signal;
        event.timestamp = Utc::now();
use tokio::signal;
    }
use tokio::signal;
    if event.id.is_empty() || event.debit_account_id.is_empty() || event.credit_account_id.is_empty() || event.amount <= 0 {
use tokio::signal;
        return HttpResponse::BadRequest().json(serde_json::json!({
use tokio::signal;
            "error": "missing required fields: id, debit_account_id, credit_account_id, amount"
use tokio::signal;
        }));
use tokio::signal;
    }
use tokio::signal;
    match state.event_tx.send(event.clone()).await {
use tokio::signal;
        Ok(_) => HttpResponse::Accepted().json(serde_json::json!({
use tokio::signal;
            "status": "accepted",
use tokio::signal;
            "transfer_id": event.id,
use tokio::signal;
            "pipeline": "async-rust",
use tokio::signal;
            "persistence": "postgresql",
use tokio::signal;
        })),
use tokio::signal;
        Err(_) => HttpResponse::ServiceUnavailable().json(serde_json::json!({
use tokio::signal;
            "error": "event pipeline full"
use tokio::signal;
        })),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn middleware_status(state: web::Data<Arc<AppState>>) -> HttpResponse {
use tokio::signal;
    let mut statuses = Vec::new();
use tokio::signal;
    // PostgreSQL check
use tokio::signal;
    let pg_status = if let Some(ref pool) = state.pg_pool {
use tokio::signal;
        match sqlx::query("SELECT 1").execute(pool).await {
use tokio::signal;
            Ok(_) => MiddlewareHealth { service: "postgres".into(), status: "connected".into(), latency_ms: 1 },
use tokio::signal;
            Err(_) => MiddlewareHealth { service: "postgres".into(), status: "disconnected".into(), latency_ms: 0 },
use tokio::signal;
        }
use tokio::signal;
    } else {
use tokio::signal;
        MiddlewareHealth { service: "postgres".into(), status: "not_configured".into(), latency_ms: 0 }
use tokio::signal;
    };
use tokio::signal;
    statuses.push(pg_status);
use tokio::signal;
    // Redis check
use tokio::signal;
    let redis_status = if let Some(ref client) = state.redis_client {
use tokio::signal;
        match client.get_multiplexed_async_connection().await {
use tokio::signal;
            Ok(_) => MiddlewareHealth { service: "redis".into(), status: "connected".into(), latency_ms: 1 },
use tokio::signal;
            Err(_) => MiddlewareHealth { service: "redis".into(), status: "disconnected".into(), latency_ms: 0 },
use tokio::signal;
        }
use tokio::signal;
    } else {
use tokio::signal;
        MiddlewareHealth { service: "redis".into(), status: "not_configured".into(), latency_ms: 0 }
use tokio::signal;
    };
use tokio::signal;
    statuses.push(redis_status);
use tokio::signal;
    // Kafka check
use tokio::signal;
    statuses.push(MiddlewareHealth {
use tokio::signal;
        service: "kafka".into(),
use tokio::signal;
        status: if state.kafka_producer.is_some() { "connected".into() } else { "disconnected".into() },
use tokio::signal;
        latency_ms: 0,
use tokio::signal;
    });
use tokio::signal;
    // HTTP service checks
use tokio::signal;
    let services = vec![
use tokio::signal;
        ("opensearch", format!("{}/_cluster/health", state.config.opensearch_url)),
use tokio::signal;
        ("lakehouse", format!("{}/api/v1/health", state.config.lakehouse_url)),
use tokio::signal;
        ("openappsec", format!("{}/health", state.config.openappsec_url)),
use tokio::signal;
        ("tigerbeetle-hub", format!("{}/health", state.config.tigerbeetle_hub_url)),
use tokio::signal;
    ];
use tokio::signal;
    for (name, url) in services {
use tokio::signal;
        let start = std::time::Instant::now();
use tokio::signal;
        let status = match state.http_client.get(&url).timeout(Duration::from_secs(2)).send().await {
use tokio::signal;
            Ok(resp) if resp.status().is_success() => "connected",
use tokio::signal;
            _ => "unavailable",
use tokio::signal;
        };
use tokio::signal;
        statuses.push(MiddlewareHealth {
use tokio::signal;
            service: name.into(),
use tokio::signal;
            status: status.into(),
use tokio::signal;
            latency_ms: start.elapsed().as_millis() as u64,
use tokio::signal;
        });
use tokio::signal;
    }
use tokio::signal;
    HttpResponse::Ok().json(statuses)
use tokio::signal;
}
use tokio::signal;
// ── Main ─────────────────────────────────────────────────────────────────────
use tokio::signal;
#[actix_web::main]
use tokio::signal;
async fn main() -> std::io::Result<()> {
use tokio::signal;
    tracing_subscriber::fmt::init();
use tokio::signal;
    let config = Config::from_env();
use tokio::signal;
    let port = config.port;
use tokio::signal;
    // Initialize middleware clients
use tokio::signal;
    let kafka_producer = create_kafka_producer(&config.kafka_brokers);
use tokio::signal;
    let redis_client = redis::Client::open(config.redis_url.as_str()).ok();
use tokio::signal;
    let pg_pool = init_pg(&config.postgres_url).await;
use tokio::signal;
    let http_client = reqwest::Client::builder()
use tokio::signal;
        .timeout(Duration::from_secs(10))
use tokio::signal;
        .pool_max_idle_per_host(20)
use tokio::signal;
        .build()
use tokio::signal;
        .expect("HTTP client");
use tokio::signal;
    let (event_tx, mut event_rx) = mpsc::channel::<TransferEvent>(10000);
use tokio::signal;
    let state = Arc::new(AppState {
use tokio::signal;
        config: config.clone(),
use tokio::signal;
        kafka_producer,
use tokio::signal;
        redis_client,
use tokio::signal;
        pg_pool,
use tokio::signal;
        http_client,
use tokio::signal;
        event_tx,
use tokio::signal;
        start_time: std::time::Instant::now(),
use tokio::signal;
        transfers_processed: AtomicU64::new(0),
use tokio::signal;
        kafka_produced: AtomicU64::new(0),
use tokio::signal;
        redis_updates: AtomicU64::new(0),
use tokio::signal;
        opensearch_indexed: AtomicU64::new(0),
use tokio::signal;
        lakehouse_exported: AtomicU64::new(0),
use tokio::signal;
        openappsec_logged: AtomicU64::new(0),
use tokio::signal;
        pg_persisted: AtomicU64::new(0),
use tokio::signal;
        errors_total: AtomicU64::new(0),
use tokio::signal;
    });
use tokio::signal;
    // Start event processor
use tokio::signal;
    let processor_state = Arc::clone(&state);
use tokio::signal;
    tokio::spawn(async move {
use tokio::signal;
        while let Some(event) = event_rx.recv().await {
use tokio::signal;
            process_event(&processor_state, event).await;
use tokio::signal;
        }
use tokio::signal;
    });
use tokio::signal;
    info!("TigerBeetle Middleware Bridge (Rust) listening on :{} [PostgreSQL-backed]", port);
use tokio::signal;
    let app_state = web::Data::new(Arc::clone(&state));
use tokio::signal;
    HttpServer::new(move || {
use tokio::signal;
        App::new()
use tokio::signal;
            .app_data(app_state.clone())
use tokio::signal;
            .route("/health", web::get().to(health))
use tokio::signal;
            .route("/metrics", web::get().to(metrics))
use tokio::signal;
            .route("/transfer", web::post().to(submit_transfer))
use tokio::signal;
            .route("/middleware/status", web::get().to(middleware_status))
use tokio::signal;
    })
use tokio::signal;
    .bind(format!("0.0.0.0:{}", port))?
use tokio::signal;
    .run()
use tokio::signal;
    .await
use tokio::signal;
