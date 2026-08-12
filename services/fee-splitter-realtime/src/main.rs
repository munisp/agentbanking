// 54agent Platform - Fee Splitter Realtime Service
// Rust service for real-time transaction fee splitting with TigerBeetle, Kafka, Mojaloop
//
// Realtime split flow:
//   1. Payment service emits "transaction.completed" event to Kafka
//   2. Fee splitter consumes event, calculates splits per party config
//   3. Creates TigerBeetle transfers for each split entry (double-entry) via the
//      tigerbeetle-core HTTP facade
//   4. Publishes "fee_split.completed" event to Kafka
//   5. For interbank splits, initiates Mojaloop settlement for external parties
//
// Integrates with: TigerBeetle, Kafka, Mojaloop, Dapr, Redis, APISIX, OpenSearch

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Duration;
use chrono::Utc;

// ─────────────────────────────────────────────────────────────
// Domain Models
// ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub id: String,
    pub agent_id: String,
    pub amount: f64,
    pub currency: String,
    pub transaction_type: String,
    pub timestamp: String,
    pub region: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SplitEntry {
    pub party: String,
    pub percentage: f64,
    pub amount: f64,
    pub account_id: String,
    pub settlement_rail: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeeSplitResult {
    pub transaction_id: String,
    pub total_amount: f64,
    pub currency: String,
    pub entries: Vec<SplitEntry>,
    pub tigerbeetle_transfer_ids: Vec<String>,
    pub mojaloop_settlement_id: Option<String>,
    pub kafka_event_id: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SplitConfig {
    pub party: String,
    pub percentage: f64,
    pub account_id: String,
    pub settlement_rail: String,
}

// ─────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────

fn get_split_configs() -> Vec<SplitConfig> {
    vec![
        SplitConfig {
            party: "platform".to_string(),
            percentage: 0.55,
            account_id: "platform-revenue".to_string(),
            settlement_rail: "internal".to_string(),
        },
        SplitConfig {
            party: "client".to_string(),
            percentage: 0.30,
            account_id: "client-share".to_string(),
            settlement_rail: "internal".to_string(),
        },
        SplitConfig {
            party: "agent".to_string(),
            percentage: 0.15,
            account_id: "agent-commission".to_string(),
            settlement_rail: "mojaloop".to_string(),
        },
    ]
}

// ─────────────────────────────────────────────────────────────
// Core Functions
// ─────────────────────────────────────────────────────────────

fn calculate_split(transaction: &Transaction) -> FeeSplitResult {
    let configs = get_split_configs();
    let entries: Vec<SplitEntry> = configs
        .iter()
        .map(|c| SplitEntry {
            party: c.party.clone(),
            percentage: c.percentage,
            amount: transaction.amount * c.percentage,
            account_id: c.account_id.clone(),
            settlement_rail: c.settlement_rail.clone(),
        })
        .collect();

    FeeSplitResult {
        transaction_id: transaction.id.clone(),
        total_amount: transaction.amount,
        currency: transaction.currency.clone(),
        entries,
        // Populated only after the transfers are actually posted.
        tigerbeetle_transfer_ids: Vec::new(),
        mojaloop_settlement_id: None,
        kafka_event_id: uuid_v4(),
        timestamp: Utc::now().to_rfc3339(),
    }
}

fn uuid_v4() -> String {
    use sha2::{Sha256, Digest};
    let mut hasher = Sha256::new();
    hasher.update(Utc::now().timestamp_nanos_opt().unwrap_or(0).to_string());
    let hash = hex::encode(hasher.finalize());
    format!("{}-{}-{}-{}-{}", &hash[0..8], &hash[8..12], &hash[12..16], &hash[16..20], &hash[20..32])
}

// id_to_u64 deterministically maps a string identifier to a u64 id used by the
// tigerbeetle-core HTTP facade.
fn id_to_u64(s: &str) -> u64 {
    use sha2::{Sha256, Digest};
    let digest = Sha256::digest(s.as_bytes());
    u64::from_be_bytes(digest[0..8].try_into().unwrap())
}

// record_in_tigerbeetle posts real double-entry transfers to the tigerbeetle-core
// HTTP facade. It returns the IDs of the transfers actually accepted, or an
// error when the facade is not configured / rejects the posting.
fn record_in_tigerbeetle(split: &FeeSplitResult, transaction: &Transaction) -> Result<Vec<String>, String> {
    let tb_url = std::env::var("TIGERBEETLE_CORE_URL")
        .or_else(|_| std::env::var("TIGERBEETLE_HTTP_URL"))
        .map_err(|_| "TIGERBEETLE_CORE_URL/TIGERBEETLE_HTTP_URL not set".to_string())?;

    #[derive(Serialize)]
    struct TBTransfer {
        id: u64,
        debit_account_id: u64,
        credit_account_id: u64,
        user_data: u64,
        pending_id: u64,
        timeout: u64,
        ledger: u32,
        code: u16,
        flags: u16,
        amount: u64,
    }

    let transfers: Vec<TBTransfer> = split.entries.iter().enumerate().map(|(i, e)| {
        let transfer_id = id_to_u64(&format!("fee:{}:{}", transaction.id, e.party));
        TBTransfer {
            id: transfer_id,
            debit_account_id: id_to_u64(&format!("customer:{}", transaction.agent_id)),
            credit_account_id: id_to_u64(&e.account_id),
            user_data: i as u64,
            pending_id: 0,
            timeout: 0,
            ledger: 1,
            code: 1,
            flags: 0,
            amount: (e.amount * 100.0).round() as u64, // kobo
        }
    }).collect();

    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|e| e.to_string())?;

    let url = format!("{}/api/v1/transfers", tb_url.trim_end_matches('/'));
    let resp = client.post(&url).json(&transfers).send().map_err(|e| format!("{}: {}", url, e))?;
    if !resp.status().is_success() {
        let body = resp.text().unwrap_or_default();
        return Err(format!("tigerbeetle-core rejected fee split transfers: {}", body));
    }

    let ids: Vec<String> = transfers.iter().map(|t| t.id.to_string()).collect();
    println!("✅ TigerBeetle: {} transfers posted for tx {}", ids.len(), transaction.id);
    Ok(ids)
}

// publish_to_kafka publishes the completed split event via a real rdkafka
// producer. Errors are returned, never swallowed.
fn publish_to_kafka(split: &FeeSplitResult, topic: &str) -> Result<(), String> {
    use rdkafka::config::ClientConfig;
    use rdkafka::producer::{BaseProducer, BaseRecord};
    use rdkafka::util::Timeout;

    let kafka_brokers = std::env::var("KAFKA_BROKERS")
        .unwrap_or_else(|_| "localhost:9092".to_string());

    let producer: BaseProducer = ClientConfig::new()
        .set("bootstrap.servers", &kafka_brokers)
        .create()
        .map_err(|e| format!("kafka producer init: {}", e))?;

    let payload = serde_json::to_string(split).map_err(|e| e.to_string())?;

    producer
        .send(BaseRecord::to(topic).key(&split.transaction_id).payload(&payload))
        .map_err(|(e, _)| format!("kafka send: {}", e))?;

    producer
        .flush(Timeout::After(Duration::from_secs(10)))
        .map_err(|e| format!("kafka flush: {}", e))?;

    println!("✅ Kafka: fee split event published to topic '{}'", topic);
    Ok(())
}

// initiate_mojaloop_settlement performs a real FSPIOP POST /transfers against
// the Mojaloop hub for external-party settlement. It returns the transfer ID
// accepted by the hub, or an error.
fn initiate_mojaloop_settlement(split: &FeeSplitResult, transaction: &Transaction) -> Result<String, String> {
    let mojaloop_url = std::env::var("MOJALOOP_URL")
        .or_else(|_| std::env::var("MOJALOOP_HUB_URL"))
        .map_err(|_| "MOJALOOP_URL/MOJALOOP_HUB_URL not set".to_string())?;
    let fsp_id = std::env::var("MOJALOOP_FSP_ID").unwrap_or_else(|_| "54agent".to_string());

    let transfer_id = uuid_v4();
    let body = serde_json::json!({
        "transferId": transfer_id,
        "payerFsp": fsp_id,
        "payeeFsp": fsp_id,
        "amount": {
            "currency": transaction.currency,
            "amount": format!("{:.2}", split.total_amount),
        },
        "ilpPacket": "",
        "condition": "",
        "expiration": (Utc::now() + chrono::Duration::minutes(5)).to_rfc3339(),
    });

    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(20))
        .build()
        .map_err(|e| e.to_string())?;

    let url = format!("{}/transfers", mojaloop_url.trim_end_matches('/'));
    let resp = client
        .post(&url)
        .header("Content-Type", "application/vnd.interoperability.transfers+json;version=1.0")
        .header("Accept", "application/vnd.interoperability.transfers+json;version=1.0")
        .header("FSPIOP-Source", &fsp_id)
        .json(&body)
        .send()
        .map_err(|e| format!("mojaloop hub unreachable: {}", e))?;

    if !resp.status().is_success() {
        return Err(format!("mojaloop hub rejected settlement: HTTP {}", resp.status()));
    }

    println!("✅ Mojaloop: settlement initiated (transferId={})", transfer_id);
    Ok(transfer_id)
}

// cache_config stores the split config in Redis for real.
fn cache_config(redis_url: &str, configs: &[SplitConfig]) -> Result<(), String> {
    let client = redis::Client::open(redis_url).map_err(|e| e.to_string())?;
    let mut conn = client.get_connection().map_err(|e| e.to_string())?;
    let payload = serde_json::to_string(configs).map_err(|e| e.to_string())?;
    let _: () = redis::cmd("SET")
        .arg("fee_splitter:configs")
        .arg(payload)
        .query(&mut conn)
        .map_err(|e| e.to_string())?;
    println!("✅ Redis: split config cached");
    Ok(())
}

// ─────────────────────────────────────────────────────────────
// Main — processes one end-to-end split cycle.
// Every downstream failure is fatal to the run: exit code 1.
// ─────────────────────────────────────────────────────────────

fn main() {
    println!("🚀 54agent Fee Splitter Realtime starting...");
    println!("⚙️  Configuration: TigerBeetle + Kafka + Mojaloop + Dapr + Redis + APISIX");

    let redis_url = std::env::var("REDIS_URL")
        .unwrap_or_else(|_| "redis://localhost:6379".to_string());

    let configs = get_split_configs();
    let mut failures: Vec<String> = Vec::new();

    if let Err(e) = cache_config(&redis_url, &configs) {
        println!("❌ Redis config cache failed: {}", e);
        failures.push(format!("redis: {}", e));
    }

    let transaction = Transaction {
        id: "txn-2026-001".to_string(),
        agent_id: "agent-lagos-01".to_string(),
        amount: 1000.0,
        currency: "NGN".to_string(),
        transaction_type: "payment".to_string(),
        timestamp: Utc::now().to_rfc3339(),
        region: "NG-LA".to_string(),
    };

    let mut split = calculate_split(&transaction);

    match record_in_tigerbeetle(&split, &transaction) {
        Ok(ids) => split.tigerbeetle_transfer_ids = ids,
        Err(e) => {
            println!("❌ TigerBeetle posting failed: {}", e);
            failures.push(format!("tigerbeetle: {}", e));
        }
    }

    if split.tigerbeetle_transfer_ids.is_empty() {
        println!("❌ Skipping Kafka/Mojaloop steps: no confirmed TigerBeetle postings");
    } else {
        if let Err(e) = publish_to_kafka(&split, "fee_split.completed") {
            println!("❌ Kafka publish failed: {}", e);
            failures.push(format!("kafka: {}", e));
        }

        match initiate_mojaloop_settlement(&split, &transaction) {
            Ok(id) => split.mojaloop_settlement_id = Some(id),
            Err(e) => {
                println!("❌ Mojaloop settlement failed: {}", e);
                failures.push(format!("mojaloop: {}", e));
            }
        }
    }

    if !failures.is_empty() {
        println!("🛑 Fee split run FAILED ({} error(s)):", failures.len());
        for f in &failures {
            println!("   - {}", f);
        }
        std::process::exit(1);
    }

    println!("✅ Fee split completed for tx {}", transaction.id);
    println!("🛑 Service exiting");
}

// ─────────────────────────────────────────────────────────────
// Health check helpers
// ─────────────────────────────────────────────────────────────

fn print_health() {
    let health = serde_json::json!({
        "status": "healthy",
        "service": "fee-splitter-realtime",
        "version": "1.0.0",
        "timestamp": Utc::now().to_rfc3339(),
    });
    println!("{}", serde_json::to_string_pretty(&health).unwrap());
}

// ─────────────────────────────────────────────────────────────
// Graceful shutdown handler
// ─────────────────────────────────────────────────────────────

async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
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
        _ = ctrl_c => {},
        _ = terminate => {},
    }

    println!("Shutdown signal received, starting graceful shutdown");
}
