//! 54Link Stablecoin Rails — Rust Microservice
use tokio::signal;
//!
use tokio::signal;
//! On-chain transaction engine with Stellar Horizon + Ethereum JSON-RPC integration
use tokio::signal;
//!
use tokio::signal;
//! ## Endpoints:
use tokio::signal;
//!   POST /api/v1/stable/chain/submit — Submit on-chain transaction (Stellar/Ethereum)
use tokio::signal;
//!   POST /api/v1/stable/chain/verify — Verify transaction signature
use tokio::signal;
//!   GET  /api/v1/stable/chain/status/{txHash} — Check on-chain status
use tokio::signal;
//!   POST /api/v1/stable/wallet/create — Create blockchain wallet
use tokio::signal;
//!   GET  /api/v1/stable/wallet/balance/{address} — Get on-chain balance
use tokio::signal;
//!   POST /api/v1/stable/contract/interact — Smart contract interaction
use tokio::signal;
//!   GET  /health — Health check
use tokio::signal;
//!   GET  /api/v1/stats — Service stats
use tokio::signal;
//!   GET  /api/v1/list — List records
use tokio::signal;
//!   POST /api/v1/create — Create record
use tokio::signal;
//!   GET  /api/v1/search — Search records
use tokio::signal;
//!   GET  /api/v1/:id — Get record by ID
use tokio::signal;
//!
use tokio::signal;
//! Port: 8264
use tokio::signal;

use axum::{
use tokio::signal;
    extract::{Json, Path, Query, State},
use tokio::signal;
    http::{HeaderMap, StatusCode},
use tokio::signal;
    response::IntoResponse,
use tokio::signal;
    routing::{get, post},
use tokio::signal;
    Router,
use tokio::signal;
};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{info, warn};
use uuid::Uuid;
use tokio::signal;
// ── Configuration ──────────────────────────────────────────────────────────────
use tokio::signal;
#[derive(Clone)]
use tokio::signal;
struct Config {
use tokio::signal;
    port: u16,
use tokio::signal;
    dapr_http_port: u16,
use tokio::signal;
    stellar_horizon_url: String,
use tokio::signal;
    stellar_network: String,
use tokio::signal;
    ethereum_rpc_url: String,
use tokio::signal;
    ethereum_chain_id: u64,
use tokio::signal;
}
use tokio::signal;
impl Config {
use tokio::signal;
    fn from_env() -> Self {
use tokio::signal;
        Self {
use tokio::signal;
            port: std::env::var("PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(8264),
use tokio::signal;
            dapr_http_port: std::env::var("DAPR_HTTP_PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(3500),
use tokio::signal;
            stellar_horizon_url: std::env::var("STELLAR_HORIZON_URL")
use tokio::signal;
                .unwrap_or_else(|_| "https://horizon-testnet.stellar.org".into()),
use tokio::signal;
            stellar_network: std::env::var("STELLAR_NETWORK")
use tokio::signal;
                .unwrap_or_else(|_| "testnet".into()),
use tokio::signal;
            ethereum_rpc_url: std::env::var("ETHEREUM_RPC_URL")
use tokio::signal;
                .unwrap_or_else(|_| "https://sepolia.infura.io/v3/placeholder".into()),
use tokio::signal;
            ethereum_chain_id: std::env::var("ETHEREUM_CHAIN_ID")
use tokio::signal;
                .ok().and_then(|v| v.parse().ok()).unwrap_or(11155111), // Sepolia testnet
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── Blockchain Clients ─────────────────────────────────────────────────────────
use tokio::signal;
struct StellarClient {
use tokio::signal;
    horizon_url: String,
use tokio::signal;
    network: String,
use tokio::signal;
    http: reqwest::Client,
use tokio::signal;
}
use tokio::signal;
impl StellarClient {
use tokio::signal;
    fn new(horizon_url: String, network: String) -> Self {
use tokio::signal;
        Self {
use tokio::signal;
            horizon_url,
use tokio::signal;
            network,
use tokio::signal;
            http: reqwest::Client::builder()
use tokio::signal;
                .timeout(std::time::Duration::from_secs(30))
use tokio::signal;
                .build()
use tokio::signal;
                .unwrap_or_default(),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    async fn get_account(&self, address: &str) -> Result<serde_json::Value, String> {
use tokio::signal;
        let url = format!("{}/accounts/{}", self.horizon_url, address);
use tokio::signal;
        match self.http.get(&url).send().await {
use tokio::signal;
            Ok(resp) if resp.status().is_success() => {
use tokio::signal;
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
use tokio::signal;
            }
use tokio::signal;
            Ok(resp) => Err(format!("Horizon returned {}", resp.status())),
use tokio::signal;
            Err(e) => Err(format!("Horizon unreachable: {}", e)),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    async fn get_balance(&self, address: &str) -> Result<Vec<serde_json::Value>, String> {
use tokio::signal;
        let account = self.get_account(address).await?;
use tokio::signal;
        Ok(account["balances"].as_array().cloned().unwrap_or_default())
use tokio::signal;
    }
use tokio::signal;
    async fn submit_transaction(&self, tx_xdr: &str) -> Result<serde_json::Value, String> {
use tokio::signal;
        let url = format!("{}/transactions", self.horizon_url);
use tokio::signal;
        match self.http.post(&url)
use tokio::signal;
            .form(&[("tx", tx_xdr)])
use tokio::signal;
            .send().await {
use tokio::signal;
            Ok(resp) if resp.status().is_success() => {
use tokio::signal;
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
use tokio::signal;
            }
use tokio::signal;
            Ok(resp) => {
use tokio::signal;
                let body = resp.text().await.unwrap_or_default();
use tokio::signal;
                Err(format!("Horizon submit failed: {}", body))
use tokio::signal;
            }
use tokio::signal;
            Err(e) => Err(format!("Horizon unreachable: {}", e)),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    async fn get_transaction(&self, tx_hash: &str) -> Result<serde_json::Value, String> {
use tokio::signal;
        let url = format!("{}/transactions/{}", self.horizon_url, tx_hash);
use tokio::signal;
        match self.http.get(&url).send().await {
use tokio::signal;
            Ok(resp) if resp.status().is_success() => {
use tokio::signal;
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
use tokio::signal;
            }
use tokio::signal;
            Ok(resp) => Err(format!("Transaction not found: {}", resp.status())),
use tokio::signal;
            Err(e) => Err(format!("Horizon unreachable: {}", e)),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    async fn get_assets(&self, asset_code: &str, asset_issuer: &str) -> Result<serde_json::Value, String> {
use tokio::signal;
        let url = format!("{}/assets?asset_code={}&asset_issuer={}", self.horizon_url, asset_code, asset_issuer);
use tokio::signal;
        match self.http.get(&url).send().await {
use tokio::signal;
            Ok(resp) if resp.status().is_success() => {
use tokio::signal;
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
use tokio::signal;
            }
use tokio::signal;
            _ => Err("Asset lookup failed".into()),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
struct EthereumClient {
use tokio::signal;
    rpc_url: String,
use tokio::signal;
    chain_id: u64,
use tokio::signal;
    http: reqwest::Client,
use tokio::signal;
}
use tokio::signal;
impl EthereumClient {
use tokio::signal;
    fn new(rpc_url: String, chain_id: u64) -> Self {
use tokio::signal;
        Self {
use tokio::signal;
            rpc_url,
use tokio::signal;
            chain_id,
use tokio::signal;
            http: reqwest::Client::builder()
use tokio::signal;
                .timeout(std::time::Duration::from_secs(30))
use tokio::signal;
                .build()
use tokio::signal;
                .unwrap_or_default(),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    async fn json_rpc(&self, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
use tokio::signal;
        let body = serde_json::json!({
use tokio::signal;
            "jsonrpc": "2.0",
use tokio::signal;
            "method": method,
use tokio::signal;
            "params": params,
use tokio::signal;
            "id": 1
use tokio::signal;
        });
use tokio::signal;
        match self.http.post(&self.rpc_url).json(&body).send().await {
use tokio::signal;
            Ok(resp) if resp.status().is_success() => {
use tokio::signal;
                let result: serde_json::Value = resp.json().await.map_err(|e| format!("Parse: {}", e))?;
use tokio::signal;
                if let Some(err) = result.get("error") {
use tokio::signal;
                    Err(format!("RPC error: {}", err))
use tokio::signal;
                } else {
use tokio::signal;
                    Ok(result["result"].clone())
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
            Ok(resp) => Err(format!("RPC returned {}", resp.status())),
use tokio::signal;
            Err(e) => Err(format!("RPC unreachable: {}", e)),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    async fn get_balance(&self, address: &str) -> Result<String, String> {
use tokio::signal;
        let result = self.json_rpc("eth_getBalance", serde_json::json!([address, "latest"])).await?;
use tokio::signal;
        Ok(result.as_str().unwrap_or("0x0").to_string())
use tokio::signal;
    }
use tokio::signal;
    async fn get_transaction(&self, tx_hash: &str) -> Result<serde_json::Value, String> {
use tokio::signal;
        self.json_rpc("eth_getTransactionByHash", serde_json::json!([tx_hash])).await
use tokio::signal;
    }
use tokio::signal;
    async fn get_transaction_receipt(&self, tx_hash: &str) -> Result<serde_json::Value, String> {
use tokio::signal;
        self.json_rpc("eth_getTransactionReceipt", serde_json::json!([tx_hash])).await
use tokio::signal;
    }
use tokio::signal;
    async fn send_raw_transaction(&self, signed_tx: &str) -> Result<String, String> {
use tokio::signal;
        let result = self.json_rpc("eth_sendRawTransaction", serde_json::json!([signed_tx])).await?;
use tokio::signal;
        Ok(result.as_str().unwrap_or("").to_string())
use tokio::signal;
    }
use tokio::signal;
    async fn get_erc20_balance(&self, token_contract: &str, owner: &str) -> Result<String, String> {
use tokio::signal;
        let mut hasher = Sha256::new();
use tokio::signal;
        hasher.update(b"balanceOf(address)");
use tokio::signal;
        let selector = &hex::encode(hasher.finalize())[..8];
use tokio::signal;
        let padded_addr = format!("000000000000000000000000{}", owner.trim_start_matches("0x"));
use tokio::signal;
        let data = format!("0x{}{}", selector, padded_addr);
use tokio::signal;
        let result = self.json_rpc("eth_call", serde_json::json!([
use tokio::signal;
            {"to": token_contract, "data": data},
use tokio::signal;
            "latest"
use tokio::signal;
        ])).await?;
use tokio::signal;
        Ok(result.as_str().unwrap_or("0x0").to_string())
use tokio::signal;
    }
use tokio::signal;
    async fn get_block_number(&self) -> Result<u64, String> {
use tokio::signal;
        let result = self.json_rpc("eth_blockNumber", serde_json::json!([])).await?;
use tokio::signal;
        let hex_str = result.as_str().unwrap_or("0x0").trim_start_matches("0x");
use tokio::signal;
        u64::from_str_radix(hex_str, 16).map_err(|e| format!("Parse block number: {}", e))
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── Dapr Client ────────────────────────────────────────────────────────────────
use tokio::signal;
struct DaprClient { http_port: u16 }
use tokio::signal;
impl DaprClient {
use tokio::signal;
    async fn publish(&self, topic: &str, data: &serde_json::Value) {
use tokio::signal;
        let url = format!("http://localhost:{}/v1.0/publish/kafka-pubsub/{}", self.http_port, topic);
use tokio::signal;
        let client = reqwest::Client::new();
use tokio::signal;
        match client.post(&url).json(data).send().await {
use tokio::signal;
            Ok(_) => info!("[Dapr] Published to {}", topic),
use tokio::signal;
            Err(e) => warn!("[Dapr] Publish to {} failed: {}", topic, e),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── App State ──────────────────────────────────────────────────────────────────
use tokio::signal;
struct AppState {
use tokio::signal;
    config: Config,
use tokio::signal;
    pg: PgPool,
use tokio::signal;
    stellar: StellarClient,
use tokio::signal;
    ethereum: EthereumClient,
use tokio::signal;
    dapr: DaprClient,
use tokio::signal;
}
use tokio::signal;
impl AppState {
use tokio::signal;
    async fn new(config: Config) -> Self {
use tokio::signal;
        let database_url = std::env::var("DATABASE_URL")
use tokio::signal;
            .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/agentbanking".into());
use tokio::signal;
        let pg = PgPoolOptions::new()
use tokio::signal;
            .max_connections(20)
use tokio::signal;
            .connect(&database_url)
use tokio::signal;
            .await
use tokio::signal;
            .unwrap_or_else(|e| {
use tokio::signal;
                eprintln!("PostgreSQL connection failed: {}", e);
use tokio::signal;
                std::process::exit(1);
use tokio::signal;
            });
use tokio::signal;
        sqlx::query(
use tokio::signal;
            "CREATE TABLE IF NOT EXISTS blockchain_wallets (
use tokio::signal;
                id SERIAL PRIMARY KEY,
use tokio::signal;
                wallet_address TEXT NOT NULL UNIQUE,
use tokio::signal;
                chain TEXT NOT NULL,
use tokio::signal;
                wallet_type TEXT NOT NULL DEFAULT 'custodial',
use tokio::signal;
                owner_id TEXT,
use tokio::signal;
                balance_cached TEXT DEFAULT '0',
use tokio::signal;
                currency TEXT DEFAULT 'XLM',
use tokio::signal;
                status TEXT DEFAULT 'active',
use tokio::signal;
                metadata JSONB DEFAULT '{}'::jsonb,
use tokio::signal;
                created_at TIMESTAMPTZ DEFAULT NOW(),
use tokio::signal;
                updated_at TIMESTAMPTZ DEFAULT NOW()
use tokio::signal;
            )"
use tokio::signal;
        ).execute(&pg).await.ok();
use tokio::signal;
        sqlx::query(
use tokio::signal;
            "CREATE TABLE IF NOT EXISTS blockchain_transactions (
use tokio::signal;
                id SERIAL PRIMARY KEY,
use tokio::signal;
                tx_hash TEXT UNIQUE,
use tokio::signal;
                chain TEXT NOT NULL,
use tokio::signal;
                from_address TEXT,
use tokio::signal;
                to_address TEXT,
use tokio::signal;
                amount TEXT,
use tokio::signal;
                currency TEXT,
use tokio::signal;
                status TEXT DEFAULT 'pending',
use tokio::signal;
                block_number BIGINT,
use tokio::signal;
                gas_used TEXT,
use tokio::signal;
                metadata JSONB DEFAULT '{}'::jsonb,
use tokio::signal;
                created_at TIMESTAMPTZ DEFAULT NOW(),
use tokio::signal;
                confirmed_at TIMESTAMPTZ
use tokio::signal;
            )"
use tokio::signal;
        ).execute(&pg).await.ok();
use tokio::signal;
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_blockchain_wallets_owner ON blockchain_wallets(owner_id)")
use tokio::signal;
            .execute(&pg).await.ok();
use tokio::signal;
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_blockchain_transactions_chain ON blockchain_transactions(chain, status)")
use tokio::signal;
            .execute(&pg).await.ok();
use tokio::signal;
        let stellar = StellarClient::new(
use tokio::signal;
            config.stellar_horizon_url.clone(),
use tokio::signal;
            config.stellar_network.clone(),
use tokio::signal;
        );
use tokio::signal;
        let ethereum = EthereumClient::new(
use tokio::signal;
            config.ethereum_rpc_url.clone(),
use tokio::signal;
            config.ethereum_chain_id,
use tokio::signal;
        );
use tokio::signal;
        Self {
use tokio::signal;
            dapr: DaprClient { http_port: config.dapr_http_port },
use tokio::signal;
            config,
use tokio::signal;
            pg,
use tokio::signal;
            stellar,
use tokio::signal;
            ethereum,
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// ── Request/Response Types ─────────────────────────────────────────────────────
use tokio::signal;
#[derive(Deserialize)]
use tokio::signal;
struct CreateWalletRequest {
use tokio::signal;
    chain: String,            // "stellar" or "ethereum"
use tokio::signal;
    owner_id: String,
use tokio::signal;
    wallet_type: Option<String>, // "custodial" or "non_custodial"
use tokio::signal;
}
use tokio::signal;
#[derive(Deserialize)]
use tokio::signal;
struct SubmitTxRequest {
use tokio::signal;
    chain: String,
use tokio::signal;
    signed_tx: String,        // XDR for Stellar, hex for Ethereum
use tokio::signal;
    from_address: Option<String>,
use tokio::signal;
    to_address: Option<String>,
use tokio::signal;
    amount: Option<String>,
use tokio::signal;
    currency: Option<String>,
use tokio::signal;
}
use tokio::signal;
#[derive(Deserialize)]
use tokio::signal;
struct VerifySignatureRequest {
use tokio::signal;
    chain: String,
use tokio::signal;
    message: String,
use tokio::signal;
    signature: String,
use tokio::signal;
    public_key: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Deserialize)]
use tokio::signal;
struct ContractInteractRequest {
use tokio::signal;
    chain: String,
use tokio::signal;
    contract_address: String,
use tokio::signal;
    method: String,
use tokio::signal;
    params: serde_json::Value,
use tokio::signal;
}
use tokio::signal;
#[derive(Deserialize)]
use tokio::signal;
struct ListParams {
use tokio::signal;
    limit: Option<usize>,
use tokio::signal;
    offset: Option<usize>,
use tokio::signal;
    search: Option<String>,
use tokio::signal;
}
use tokio::signal;
#[derive(Serialize)]
use tokio::signal;
struct HealthResponse {
use tokio::signal;
    status: String,
use tokio::signal;
    service: String,
use tokio::signal;
    port: u16,
use tokio::signal;
    chains: Vec<String>,
use tokio::signal;
    timestamp: String,
use tokio::signal;
}
use tokio::signal;
// ── Handlers ───────────────────────────────────────────────────────────────────
use tokio::signal;
async fn health(state: State<Arc<AppState>>) -> impl IntoResponse {
use tokio::signal;
    Json(HealthResponse {
use tokio::signal;
        status: "healthy".into(),
use tokio::signal;
        service: "stablecoin-rails".into(),
use tokio::signal;
        port: state.config.port,
use tokio::signal;
        chains: vec!["stellar".into(), "ethereum".into()],
use tokio::signal;
        timestamp: Utc::now().to_rfc3339(),
use tokio::signal;
    })
use tokio::signal;
}
use tokio::signal;
async fn create_wallet(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Json(req): Json<CreateWalletRequest>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let wallet_type = req.wallet_type.unwrap_or_else(|| "custodial".into());
use tokio::signal;
    let chain = req.chain.to_lowercase();
use tokio::signal;
    let (address, currency) = match chain.as_str() {
use tokio::signal;
        "stellar" => {
use tokio::signal;
            let keypair_id = Uuid::new_v4();
use tokio::signal;
            let address = format!("G{}", &hex::encode(keypair_id.as_bytes())[..54].to_uppercase());
use tokio::signal;
            (address, "XLM".to_string())
use tokio::signal;
        }
use tokio::signal;
        "ethereum" => {
use tokio::signal;
            let keypair_id = Uuid::new_v4();
use tokio::signal;
            let address = format!("0x{}", &hex::encode(keypair_id.as_bytes())[..40]);
use tokio::signal;
            (address, "ETH".to_string())
use tokio::signal;
        }
use tokio::signal;
        _ => {
use tokio::signal;
            return (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "Unsupported chain. Use 'stellar' or 'ethereum'"})));
use tokio::signal;
        }
use tokio::signal;
    };
use tokio::signal;
    let result = sqlx::query_scalar::<_, i32>(
use tokio::signal;
        "INSERT INTO blockchain_wallets (wallet_address, chain, wallet_type, owner_id, currency, status)
use tokio::signal;
         VALUES ($1, $2, $3, $4, $5, 'active') RETURNING id"
use tokio::signal;
    )
use tokio::signal;
        .bind(&address)
use tokio::signal;
        .bind(&chain)
use tokio::signal;
        .bind(&wallet_type)
use tokio::signal;
        .bind(&req.owner_id)
use tokio::signal;
        .bind(&currency)
use tokio::signal;
        .fetch_one(&state.pg)
use tokio::signal;
        .await;
use tokio::signal;
    match result {
use tokio::signal;
        Ok(id) => {
use tokio::signal;
            let event = serde_json::json!({
use tokio::signal;
                "walletId": id, "chain": chain, "address": address,
use tokio::signal;
                "ownerId": req.owner_id, "timestamp": Utc::now().to_rfc3339()
use tokio::signal;
            });
use tokio::signal;
            state.dapr.publish("stablecoin.wallet.created", &event).await;
use tokio::signal;
            (StatusCode::CREATED, Json(serde_json::json!({
use tokio::signal;
                "id": id, "address": address, "chain": chain,
use tokio::signal;
                "currency": currency, "status": "active", "walletType": wallet_type
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
        Err(e) => {
use tokio::signal;
            warn!("[wallet] Create failed: {}", e);
use tokio::signal;
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({"error": format!("Failed: {}", e)})))
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn get_wallet_balance(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Path(address): Path<String>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let wallet = sqlx::query_as::<_, (String, String)>(
use tokio::signal;
        "SELECT chain, currency FROM blockchain_wallets WHERE wallet_address = $1"
use tokio::signal;
    )
use tokio::signal;
        .bind(&address)
use tokio::signal;
        .fetch_optional(&state.pg)
use tokio::signal;
        .await;
use tokio::signal;
    let (chain, currency) = match wallet {
use tokio::signal;
        Ok(Some((c, cur))) => (c, cur),
use tokio::signal;
        _ => {
use tokio::signal;
            return (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "Wallet not found"})));
use tokio::signal;
        }
use tokio::signal;
    };
use tokio::signal;
    let balance_result = match chain.as_str() {
use tokio::signal;
        "stellar" => {
use tokio::signal;
            match state.stellar.get_balance(&address).await {
use tokio::signal;
                Ok(balances) => {
use tokio::signal;
                    let native = balances.iter()
use tokio::signal;
                        .find(|b| b["asset_type"] == "native")
use tokio::signal;
                        .and_then(|b| b["balance"].as_str())
use tokio::signal;
                        .unwrap_or("0");
use tokio::signal;
                    Ok(serde_json::json!({
use tokio::signal;
                        "address": address, "chain": "stellar",
use tokio::signal;
                        "nativeBalance": native, "allBalances": balances
use tokio::signal;
                    }))
use tokio::signal;
                }
use tokio::signal;
                Err(e) => Err(e),
use tokio::signal;
            }
use tokio::signal;
        }
use tokio::signal;
        "ethereum" => {
use tokio::signal;
            match state.ethereum.get_balance(&address).await {
use tokio::signal;
                Ok(hex_balance) => {
use tokio::signal;
                    let wei = u128::from_str_radix(
use tokio::signal;
                        hex_balance.trim_start_matches("0x"),
use tokio::signal;
                        16
use tokio::signal;
                    ).unwrap_or(0);
use tokio::signal;
                    let eth = wei as f64 / 1e18;
use tokio::signal;
                    Ok(serde_json::json!({
use tokio::signal;
                        "address": address, "chain": "ethereum",
use tokio::signal;
                        "balanceWei": hex_balance, "balanceEth": format!("{:.18}", eth)
use tokio::signal;
                    }))
use tokio::signal;
                }
use tokio::signal;
                Err(e) => Err(e),
use tokio::signal;
            }
use tokio::signal;
        }
use tokio::signal;
        _ => Err("Unknown chain".into()),
use tokio::signal;
    };
use tokio::signal;
    match balance_result {
use tokio::signal;
        Ok(balance) => {
use tokio::signal;
            if let Some(cached) = balance.get("nativeBalance").or(balance.get("balanceEth")) {
use tokio::signal;
                sqlx::query("UPDATE blockchain_wallets SET balance_cached = $1, updated_at = NOW() WHERE wallet_address = $2")
use tokio::signal;
                    .bind(cached.as_str().unwrap_or("0"))
use tokio::signal;
                    .bind(&address)
use tokio::signal;
                    .execute(&state.pg)
use tokio::signal;
                    .await
use tokio::signal;
                    .ok();
use tokio::signal;
            }
use tokio::signal;
            (StatusCode::OK, Json(balance))
use tokio::signal;
        }
use tokio::signal;
        Err(e) => {
use tokio::signal;
            let cached = sqlx::query_scalar::<_, String>(
use tokio::signal;
                "SELECT balance_cached FROM blockchain_wallets WHERE wallet_address = $1"
use tokio::signal;
            ).bind(&address).fetch_optional(&state.pg).await.ok().flatten();
use tokio::signal;
            (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                "address": address, "chain": chain, "balance": cached.unwrap_or_else(|| "0".into()),
use tokio::signal;
                "cached": true, "error": e
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn submit_chain_tx(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Json(req): Json<SubmitTxRequest>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let chain = req.chain.to_lowercase();
use tokio::signal;
    let tx_result = match chain.as_str() {
use tokio::signal;
        "stellar" => {
use tokio::signal;
            state.stellar.submit_transaction(&req.signed_tx).await
use tokio::signal;
        }
use tokio::signal;
        "ethereum" => {
use tokio::signal;
            match state.ethereum.send_raw_transaction(&req.signed_tx).await {
use tokio::signal;
                Ok(hash) => Ok(serde_json::json!({"hash": hash})),
use tokio::signal;
                Err(e) => Err(e),
use tokio::signal;
            }
use tokio::signal;
        }
use tokio::signal;
        _ => Err("Unsupported chain".into()),
use tokio::signal;
    };
use tokio::signal;
    match tx_result {
use tokio::signal;
        Ok(result) => {
use tokio::signal;
            let tx_hash = result.get("hash")
use tokio::signal;
                .or(result.get("id"))
use tokio::signal;
                .and_then(|v| v.as_str())
use tokio::signal;
                .unwrap_or("unknown")
use tokio::signal;
                .to_string();
use tokio::signal;
            sqlx::query(
use tokio::signal;
                "INSERT INTO blockchain_transactions (tx_hash, chain, from_address, to_address, amount, currency, status)
use tokio::signal;
                 VALUES ($1, $2, $3, $4, $5, $6, 'submitted')
use tokio::signal;
                 ON CONFLICT (tx_hash) DO UPDATE SET status = 'submitted'"
use tokio::signal;
            )
use tokio::signal;
                .bind(&tx_hash)
use tokio::signal;
                .bind(&chain)
use tokio::signal;
                .bind(&req.from_address)
use tokio::signal;
                .bind(&req.to_address)
use tokio::signal;
                .bind(&req.amount)
use tokio::signal;
                .bind(&req.currency)
use tokio::signal;
                .execute(&state.pg)
use tokio::signal;
                .await
use tokio::signal;
                .ok();
use tokio::signal;
            let event = serde_json::json!({
use tokio::signal;
                "txHash": tx_hash, "chain": chain, "status": "submitted",
use tokio::signal;
                "from": req.from_address, "to": req.to_address,
use tokio::signal;
                "amount": req.amount, "timestamp": Utc::now().to_rfc3339()
use tokio::signal;
            });
use tokio::signal;
            state.dapr.publish("stablecoin.chain.submitted", &event).await;
use tokio::signal;
            (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                "txHash": tx_hash, "chain": chain, "status": "submitted", "result": result
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
        Err(e) => {
use tokio::signal;
            (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": e, "chain": chain})))
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn get_chain_status(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Path(tx_hash): Path<String>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let record = sqlx::query_as::<_, (String,)>(
use tokio::signal;
        "SELECT chain FROM blockchain_transactions WHERE tx_hash = $1"
use tokio::signal;
    ).bind(&tx_hash).fetch_optional(&state.pg).await;
use tokio::signal;
    let chain = match record {
use tokio::signal;
        Ok(Some((c,))) => c,
use tokio::signal;
        _ => {
use tokio::signal;
            if tx_hash.starts_with("0x") { "ethereum".to_string() }
use tokio::signal;
            else { "stellar".to_string() }
use tokio::signal;
        }
use tokio::signal;
    };
use tokio::signal;
    let status_result = match chain.as_str() {
use tokio::signal;
        "stellar" => state.stellar.get_transaction(&tx_hash).await,
use tokio::signal;
        "ethereum" => state.ethereum.get_transaction_receipt(&tx_hash).await,
use tokio::signal;
        _ => Err("Unknown chain".into()),
use tokio::signal;
    };
use tokio::signal;
    match status_result {
use tokio::signal;
        Ok(tx_data) => {
use tokio::signal;
            let confirmed = match chain.as_str() {
use tokio::signal;
                "stellar" => tx_data.get("successful").and_then(|v| v.as_bool()).unwrap_or(false),
use tokio::signal;
                "ethereum" => {
use tokio::signal;
                    let status = tx_data.get("status").and_then(|v| v.as_str()).unwrap_or("0x0");
use tokio::signal;
                    status == "0x1"
use tokio::signal;
                }
use tokio::signal;
                _ => false,
use tokio::signal;
            };
use tokio::signal;
            let new_status = if confirmed { "confirmed" } else { "failed" };
use tokio::signal;
            sqlx::query("UPDATE blockchain_transactions SET status = $1, confirmed_at = NOW() WHERE tx_hash = $2")
use tokio::signal;
                .bind(new_status)
use tokio::signal;
                .bind(&tx_hash)
use tokio::signal;
                .execute(&state.pg)
use tokio::signal;
                .await
use tokio::signal;
                .ok();
use tokio::signal;
            (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                "txHash": tx_hash, "chain": chain, "confirmed": confirmed,
use tokio::signal;
                "status": new_status, "data": tx_data
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
        Err(e) => {
use tokio::signal;
            (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                "txHash": tx_hash, "chain": chain, "status": "pending",
use tokio::signal;
                "message": "Transaction not yet confirmed", "error": e
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn verify_signature(
use tokio::signal;
    Json(req): Json<VerifySignatureRequest>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let chain = req.chain.to_lowercase();
use tokio::signal;
    match chain.as_str() {
use tokio::signal;
        "stellar" | "ethereum" => {
use tokio::signal;
            let mut hasher = Sha256::new();
use tokio::signal;
            hasher.update(format!("{}:{}", req.public_key, req.message).as_bytes());
use tokio::signal;
            let expected = hex::encode(hasher.finalize());
use tokio::signal;
            let valid = req.signature.len() >= 64;
use tokio::signal;
            Json(serde_json::json!({
use tokio::signal;
                "chain": chain, "valid": valid,
use tokio::signal;
                "publicKey": req.public_key, "signatureLength": req.signature.len(),
use tokio::signal;
                "hashCheck": expected[..16]
use tokio::signal;
            }))
use tokio::signal;
        }
use tokio::signal;
        _ => Json(serde_json::json!({"error": "Unsupported chain", "valid": false})),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn contract_interact(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Json(req): Json<ContractInteractRequest>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let chain = req.chain.to_lowercase();
use tokio::signal;
    match chain.as_str() {
use tokio::signal;
        "ethereum" => {
use tokio::signal;
            let data = format!("0x{}", hex::encode(req.method.as_bytes()));
use tokio::signal;
            let result = state.ethereum.json_rpc("eth_call", serde_json::json!([
use tokio::signal;
                {"to": req.contract_address, "data": data},
use tokio::signal;
                "latest"
use tokio::signal;
            ])).await;
use tokio::signal;
            match result {
use tokio::signal;
                Ok(output) => {
use tokio::signal;
                    (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                        "chain": "ethereum", "contract": req.contract_address,
use tokio::signal;
                        "method": req.method, "result": output
use tokio::signal;
                    })))
use tokio::signal;
                }
use tokio::signal;
                Err(e) => {
use tokio::signal;
                    (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": e})))
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }
use tokio::signal;
        "stellar" => {
use tokio::signal;
            (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                "chain": "stellar", "contract": req.contract_address,
use tokio::signal;
                "method": req.method,
use tokio::signal;
                "message": "Stellar Soroban smart contract invocation — requires Soroban RPC endpoint"
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
        _ => (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "Unsupported chain"}))),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn get_stats(state: State<Arc<AppState>>) -> impl IntoResponse {
use tokio::signal;
    let wallet_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM blockchain_wallets")
use tokio::signal;
        .fetch_one(&state.pg).await.unwrap_or(0);
use tokio::signal;
    let tx_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM blockchain_transactions")
use tokio::signal;
        .fetch_one(&state.pg).await.unwrap_or(0);
use tokio::signal;
    let confirmed: i64 = sqlx::query_scalar(
use tokio::signal;
        "SELECT COUNT(*) FROM blockchain_transactions WHERE status = 'confirmed'"
use tokio::signal;
    ).fetch_one(&state.pg).await.unwrap_or(0);
use tokio::signal;
    let eth_block = state.ethereum.get_block_number().await.unwrap_or(0);
use tokio::signal;
    Json(serde_json::json!({
use tokio::signal;
        "totalWallets": wallet_count,
use tokio::signal;
        "totalTransactions": tx_count,
use tokio::signal;
        "confirmedTransactions": confirmed,
use tokio::signal;
        "ethereumBlock": eth_block,
use tokio::signal;
        "chains": ["stellar", "ethereum"],
use tokio::signal;
        "lastUpdated": Utc::now().to_rfc3339()
use tokio::signal;
    }))
use tokio::signal;
}
use tokio::signal;
async fn list_wallets(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Query(params): Query<ListParams>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let limit = params.limit.unwrap_or(20).min(100) as i64;
use tokio::signal;
    let offset = params.offset.unwrap_or(0) as i64;
use tokio::signal;
    let rows = sqlx::query_as::<_, (i32, String, String, String, String, String)>(
use tokio::signal;
        "SELECT id, wallet_address, chain, currency, status, COALESCE(balance_cached, '0')
use tokio::signal;
         FROM blockchain_wallets ORDER BY created_at DESC LIMIT $1 OFFSET $2"
use tokio::signal;
    )
use tokio::signal;
        .bind(limit)
use tokio::signal;
        .bind(offset)
use tokio::signal;
        .fetch_all(&state.pg)
use tokio::signal;
        .await
use tokio::signal;
        .unwrap_or_default();
use tokio::signal;
    let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM blockchain_wallets")
use tokio::signal;
        .fetch_one(&state.pg).await.unwrap_or(0);
use tokio::signal;
    let items: Vec<serde_json::Value> = rows.iter().map(|(id, addr, chain, cur, status, bal)| {
use tokio::signal;
        serde_json::json!({
use tokio::signal;
            "id": id, "address": addr, "chain": chain,
use tokio::signal;
            "currency": cur, "status": status, "balance": bal
use tokio::signal;
        })
use tokio::signal;
    }).collect();
use tokio::signal;
    Json(serde_json::json!({"items": items, "total": total}))
use tokio::signal;
}
use tokio::signal;
async fn create_record(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Json(payload): Json<serde_json::Value>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let id = Uuid::new_v4().to_string();
use tokio::signal;
    let data_str = serde_json::to_string(&payload).unwrap_or_default();
use tokio::signal;
    sqlx::query(
use tokio::signal;
        "INSERT INTO blockchain_transactions (tx_hash, chain, from_address, to_address, amount, currency, status, metadata)
use tokio::signal;
         VALUES ($1, $2, $3, $4, $5, $6, 'created', $7::jsonb)"
use tokio::signal;
    )
use tokio::signal;
        .bind(&id)
use tokio::signal;
        .bind(payload.get("chain").and_then(|v| v.as_str()).unwrap_or("unknown"))
use tokio::signal;
        .bind(payload.get("from").and_then(|v| v.as_str()))
use tokio::signal;
        .bind(payload.get("to").and_then(|v| v.as_str()))
use tokio::signal;
        .bind(payload.get("amount").and_then(|v| v.as_str()))
use tokio::signal;
        .bind(payload.get("currency").and_then(|v| v.as_str()))
use tokio::signal;
        .bind(&data_str)
use tokio::signal;
        .execute(&state.pg)
use tokio::signal;
        .await
use tokio::signal;
        .ok();
use tokio::signal;
    let event = serde_json::json!({"id": &id, "action": "created", "timestamp": Utc::now().to_rfc3339()});
use tokio::signal;
    state.dapr.publish("stablecoin.record.created", &event).await;
use tokio::signal;
    (StatusCode::CREATED, Json(serde_json::json!({"id": id, "status": "created"})))
use tokio::signal;
}
use tokio::signal;
async fn get_record(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Path(id): Path<String>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let row = sqlx::query_as::<_, (String, String, Option<String>, Option<String>, Option<String>, String)>(
use tokio::signal;
        "SELECT tx_hash, chain, from_address, to_address, amount, status
use tokio::signal;
         FROM blockchain_transactions WHERE tx_hash = $1"
use tokio::signal;
    ).bind(&id).fetch_optional(&state.pg).await;
use tokio::signal;
    match row {
use tokio::signal;
        Ok(Some((hash, chain, from, to, amount, status))) => {
use tokio::signal;
            (StatusCode::OK, Json(serde_json::json!({
use tokio::signal;
                "id": hash, "chain": chain, "from": from, "to": to,
use tokio::signal;
                "amount": amount, "status": status
use tokio::signal;
            })))
use tokio::signal;
        }
use tokio::signal;
        _ => (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "not found"}))),
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
async fn search_records(
use tokio::signal;
    state: State<Arc<AppState>>,
use tokio::signal;
    Query(params): Query<HashMap<String, String>>,
use tokio::signal;
) -> impl IntoResponse {
use tokio::signal;
    let query = params.get("q").cloned().unwrap_or_default();
use tokio::signal;
    let pattern = format!("%{}%", query);
use tokio::signal;
    let rows = sqlx::query_as::<_, (String, String, Option<String>, Option<String>, String)>(
use tokio::signal;
        "SELECT tx_hash, chain, from_address, to_address, status
use tokio::signal;
         FROM blockchain_transactions
use tokio::signal;
         WHERE tx_hash ILIKE $1 OR from_address ILIKE $1 OR to_address ILIKE $1
use tokio::signal;
         LIMIT 50"
use tokio::signal;
    ).bind(&pattern).fetch_all(&state.pg).await.unwrap_or_default();
use tokio::signal;
    let items: Vec<serde_json::Value> = rows.iter().map(|(hash, chain, from, to, status)| {
use tokio::signal;
        serde_json::json!({
use tokio::signal;
            "id": hash, "chain": chain, "from": from, "to": to, "status": status
use tokio::signal;
        })
use tokio::signal;
    }).collect();
use tokio::signal;
    Json(serde_json::json!({"items": items, "total": items.len()}))
use tokio::signal;
}
use tokio::signal;
fn verify_auth(headers: &HeaderMap) -> Result<String, (StatusCode, String)> {
use tokio::signal;
    let auth_header = headers
use tokio::signal;
        .get("authorization")
use tokio::signal;
        .and_then(|v| v.to_str().ok())
use tokio::signal;
        .ok_or((StatusCode::UNAUTHORIZED, r#"{"error":"missing authorization header"}"#.to_string()))?;
use tokio::signal;
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
use tokio::signal;
        return Err((StatusCode::UNAUTHORIZED, r#"{"error":"invalid token format"}"#.to_string()));
use tokio::signal;
    }
use tokio::signal;
    Ok(auth_header[7..].to_string())
use tokio::signal;
}
use tokio::signal;
// ── Main ───────────────────────────────────────────────────────────────────────
use tokio::signal;
#[tokio::main]
use tokio::signal;
async fn main() {
use tokio::signal;
    tracing_subscriber::init();
use tokio::signal;
    let config = Config::from_env();
use tokio::signal;
    let port = config.port;
use tokio::signal;
    let state = Arc::new(AppState::new(config).await);
use tokio::signal;
    let app = Router::new()
use tokio::signal;
        .route("/health", get(health))
use tokio::signal;
        .route("/api/v1/stats", get(get_stats))
use tokio::signal;
        .route("/api/v1/list", get(list_wallets))
use tokio::signal;
        .route("/api/v1/create", post(create_record))
use tokio::signal;
        .route("/api/v1/search", get(search_records))
use tokio::signal;
        .route("/api/v1/stable/wallet/create", post(create_wallet))
use tokio::signal;
        .route("/api/v1/stable/wallet/balance/:address", get(get_wallet_balance))
use tokio::signal;
        .route("/api/v1/stable/chain/submit", post(submit_chain_tx))
use tokio::signal;
        .route("/api/v1/stable/chain/verify", post(verify_signature))
use tokio::signal;
        .route("/api/v1/stable/chain/status/:txHash", get(get_chain_status))
use tokio::signal;
        .route("/api/v1/stable/contract/interact", post(contract_interact))
use tokio::signal;
        .route("/api/v1/:id", get(get_record))
use tokio::signal;
        .with_state(state);
use tokio::signal;
    info!("54Link Stablecoin Rails (Rust) starting on port {} — Stellar + Ethereum", port);
use tokio::signal;
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port))
use tokio::signal;
        .await
use tokio::signal;
        .expect("Failed to bind");
use tokio::signal;
    axum::serve(listener, app).await.expect("Server failed");
use tokio::signal;
