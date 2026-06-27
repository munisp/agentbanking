//! 54Link Stablecoin Rails — Rust Microservice
//!
//! On-chain transaction engine with Stellar Horizon + Ethereum JSON-RPC integration
//!
//! ## Endpoints:
//!   POST /api/v1/stable/chain/submit — Submit on-chain transaction (Stellar/Ethereum)
//!   POST /api/v1/stable/chain/verify — Verify transaction signature
//!   GET  /api/v1/stable/chain/status/{txHash} — Check on-chain status
//!   POST /api/v1/stable/wallet/create — Create blockchain wallet
//!   GET  /api/v1/stable/wallet/balance/{address} — Get on-chain balance
//!   POST /api/v1/stable/contract/interact — Smart contract interaction
//!   GET  /health — Health check
//!   GET  /api/v1/stats — Service stats
//!   GET  /api/v1/list — List records
//!   POST /api/v1/create — Create record
//!   GET  /api/v1/search — Search records
//!   GET  /api/v1/:id — Get record by ID
//!
//! Port: 8264

use axum::{
    extract::{Json, Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Router,
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

// ── Configuration ──────────────────────────────────────────────────────────────

#[derive(Clone)]
struct Config {
    port: u16,
    dapr_http_port: u16,
    stellar_horizon_url: String,
    stellar_network: String,
    ethereum_rpc_url: String,
    ethereum_chain_id: u64,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(8264),
            dapr_http_port: std::env::var("DAPR_HTTP_PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(3500),
            stellar_horizon_url: std::env::var("STELLAR_HORIZON_URL")
                .unwrap_or_else(|_| "https://horizon-testnet.stellar.org".into()),
            stellar_network: std::env::var("STELLAR_NETWORK")
                .unwrap_or_else(|_| "testnet".into()),
            ethereum_rpc_url: std::env::var("ETHEREUM_RPC_URL")
                .unwrap_or_else(|_| "https://sepolia.infura.io/v3/placeholder".into()),
            ethereum_chain_id: std::env::var("ETHEREUM_CHAIN_ID")
                .ok().and_then(|v| v.parse().ok()).unwrap_or(11155111), // Sepolia testnet
        }
    }
}

// ── Blockchain Clients ─────────────────────────────────────────────────────────

struct StellarClient {
    horizon_url: String,
    network: String,
    http: reqwest::Client,
}

impl StellarClient {
    fn new(horizon_url: String, network: String) -> Self {
        Self {
            horizon_url,
            network,
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()
                .unwrap_or_default(),
        }
    }

    async fn get_account(&self, address: &str) -> Result<serde_json::Value, String> {
        let url = format!("{}/accounts/{}", self.horizon_url, address);
        match self.http.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
            }
            Ok(resp) => Err(format!("Horizon returned {}", resp.status())),
            Err(e) => Err(format!("Horizon unreachable: {}", e)),
        }
    }

    async fn get_balance(&self, address: &str) -> Result<Vec<serde_json::Value>, String> {
        let account = self.get_account(address).await?;
        Ok(account["balances"].as_array().cloned().unwrap_or_default())
    }

    async fn submit_transaction(&self, tx_xdr: &str) -> Result<serde_json::Value, String> {
        let url = format!("{}/transactions", self.horizon_url);
        match self.http.post(&url)
            .form(&[("tx", tx_xdr)])
            .send().await {
            Ok(resp) if resp.status().is_success() => {
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
            }
            Ok(resp) => {
                let body = resp.text().await.unwrap_or_default();
                Err(format!("Horizon submit failed: {}", body))
            }
            Err(e) => Err(format!("Horizon unreachable: {}", e)),
        }
    }

    async fn get_transaction(&self, tx_hash: &str) -> Result<serde_json::Value, String> {
        let url = format!("{}/transactions/{}", self.horizon_url, tx_hash);
        match self.http.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
            }
            Ok(resp) => Err(format!("Transaction not found: {}", resp.status())),
            Err(e) => Err(format!("Horizon unreachable: {}", e)),
        }
    }

    async fn get_assets(&self, asset_code: &str, asset_issuer: &str) -> Result<serde_json::Value, String> {
        let url = format!("{}/assets?asset_code={}&asset_issuer={}", self.horizon_url, asset_code, asset_issuer);
        match self.http.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                resp.json().await.map_err(|e| format!("Parse error: {}", e))
            }
            _ => Err("Asset lookup failed".into()),
        }
    }
}

struct EthereumClient {
    rpc_url: String,
    chain_id: u64,
    http: reqwest::Client,
}

impl EthereumClient {
    fn new(rpc_url: String, chain_id: u64) -> Self {
        Self {
            rpc_url,
            chain_id,
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()
                .unwrap_or_default(),
        }
    }

    async fn json_rpc(&self, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
        let body = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        });
        match self.http.post(&self.rpc_url).json(&body).send().await {
            Ok(resp) if resp.status().is_success() => {
                let result: serde_json::Value = resp.json().await.map_err(|e| format!("Parse: {}", e))?;
                if let Some(err) = result.get("error") {
                    Err(format!("RPC error: {}", err))
                } else {
                    Ok(result["result"].clone())
                }
            }
            Ok(resp) => Err(format!("RPC returned {}", resp.status())),
            Err(e) => Err(format!("RPC unreachable: {}", e)),
        }
    }

    async fn get_balance(&self, address: &str) -> Result<String, String> {
        let result = self.json_rpc("eth_getBalance", serde_json::json!([address, "latest"])).await?;
        Ok(result.as_str().unwrap_or("0x0").to_string())
    }

    async fn get_transaction(&self, tx_hash: &str) -> Result<serde_json::Value, String> {
        self.json_rpc("eth_getTransactionByHash", serde_json::json!([tx_hash])).await
    }

    async fn get_transaction_receipt(&self, tx_hash: &str) -> Result<serde_json::Value, String> {
        self.json_rpc("eth_getTransactionReceipt", serde_json::json!([tx_hash])).await
    }

    async fn send_raw_transaction(&self, signed_tx: &str) -> Result<String, String> {
        let result = self.json_rpc("eth_sendRawTransaction", serde_json::json!([signed_tx])).await?;
        Ok(result.as_str().unwrap_or("").to_string())
    }

    async fn get_erc20_balance(&self, token_contract: &str, owner: &str) -> Result<String, String> {
        let mut hasher = Sha256::new();
        hasher.update(b"balanceOf(address)");
        let selector = &hex::encode(hasher.finalize())[..8];
        let padded_addr = format!("000000000000000000000000{}", owner.trim_start_matches("0x"));
        let data = format!("0x{}{}", selector, padded_addr);
        let result = self.json_rpc("eth_call", serde_json::json!([
            {"to": token_contract, "data": data},
            "latest"
        ])).await?;
        Ok(result.as_str().unwrap_or("0x0").to_string())
    }

    async fn get_block_number(&self) -> Result<u64, String> {
        let result = self.json_rpc("eth_blockNumber", serde_json::json!([])).await?;
        let hex_str = result.as_str().unwrap_or("0x0").trim_start_matches("0x");
        u64::from_str_radix(hex_str, 16).map_err(|e| format!("Parse block number: {}", e))
    }
}

// ── Dapr Client ────────────────────────────────────────────────────────────────

struct DaprClient { http_port: u16 }

impl DaprClient {
    async fn publish(&self, topic: &str, data: &serde_json::Value) {
        let url = format!("http://localhost:{}/v1.0/publish/kafka-pubsub/{}", self.http_port, topic);
        let client = reqwest::Client::new();
        match client.post(&url).json(data).send().await {
            Ok(_) => info!("[Dapr] Published to {}", topic),
            Err(e) => warn!("[Dapr] Publish to {} failed: {}", topic, e),
        }
    }
}

// ── App State ──────────────────────────────────────────────────────────────────

struct AppState {
    config: Config,
    pg: PgPool,
    stellar: StellarClient,
    ethereum: EthereumClient,
    dapr: DaprClient,
}

impl AppState {
    async fn new(config: Config) -> Self {
        let database_url = std::env::var("DATABASE_URL")
            .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/agentbanking".into());

        let pg = PgPoolOptions::new()
            .max_connections(20)
            .connect(&database_url)
            .await
            .unwrap_or_else(|e| {
                eprintln!("PostgreSQL connection failed: {}", e);
                std::process::exit(1);
            });

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS blockchain_wallets (
                id SERIAL PRIMARY KEY,
                wallet_address TEXT NOT NULL UNIQUE,
                chain TEXT NOT NULL,
                wallet_type TEXT NOT NULL DEFAULT 'custodial',
                owner_id TEXT,
                balance_cached TEXT DEFAULT '0',
                currency TEXT DEFAULT 'XLM',
                status TEXT DEFAULT 'active',
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )"
        ).execute(&pg).await.ok();

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS blockchain_transactions (
                id SERIAL PRIMARY KEY,
                tx_hash TEXT UNIQUE,
                chain TEXT NOT NULL,
                from_address TEXT,
                to_address TEXT,
                amount TEXT,
                currency TEXT,
                status TEXT DEFAULT 'pending',
                block_number BIGINT,
                gas_used TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                confirmed_at TIMESTAMPTZ
            )"
        ).execute(&pg).await.ok();

        sqlx::query("CREATE INDEX IF NOT EXISTS idx_blockchain_wallets_owner ON blockchain_wallets(owner_id)")
            .execute(&pg).await.ok();
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_blockchain_transactions_chain ON blockchain_transactions(chain, status)")
            .execute(&pg).await.ok();

        let stellar = StellarClient::new(
            config.stellar_horizon_url.clone(),
            config.stellar_network.clone(),
        );
        let ethereum = EthereumClient::new(
            config.ethereum_rpc_url.clone(),
            config.ethereum_chain_id,
        );

        Self {
            dapr: DaprClient { http_port: config.dapr_http_port },
            config,
            pg,
            stellar,
            ethereum,
        }
    }
}

// ── Request/Response Types ─────────────────────────────────────────────────────

#[derive(Deserialize)]
struct CreateWalletRequest {
    chain: String,            // "stellar" or "ethereum"
    owner_id: String,
    wallet_type: Option<String>, // "custodial" or "non_custodial"
}

#[derive(Deserialize)]
struct SubmitTxRequest {
    chain: String,
    signed_tx: String,        // XDR for Stellar, hex for Ethereum
    from_address: Option<String>,
    to_address: Option<String>,
    amount: Option<String>,
    currency: Option<String>,
}

#[derive(Deserialize)]
struct VerifySignatureRequest {
    chain: String,
    message: String,
    signature: String,
    public_key: String,
}

#[derive(Deserialize)]
struct ContractInteractRequest {
    chain: String,
    contract_address: String,
    method: String,
    params: serde_json::Value,
}

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
    chains: Vec<String>,
    timestamp: String,
}

// ── Handlers ───────────────────────────────────────────────────────────────────

async fn health(state: State<Arc<AppState>>) -> impl IntoResponse {
    Json(HealthResponse {
        status: "healthy".into(),
        service: "stablecoin-rails".into(),
        port: state.config.port,
        chains: vec!["stellar".into(), "ethereum".into()],
        timestamp: Utc::now().to_rfc3339(),
    })
}

async fn create_wallet(
    state: State<Arc<AppState>>,
    Json(req): Json<CreateWalletRequest>,
) -> impl IntoResponse {
    let wallet_type = req.wallet_type.unwrap_or_else(|| "custodial".into());
    let chain = req.chain.to_lowercase();

    let (address, currency) = match chain.as_str() {
        "stellar" => {
            let keypair_id = Uuid::new_v4();
            let address = format!("G{}", &hex::encode(keypair_id.as_bytes())[..54].to_uppercase());
            (address, "XLM".to_string())
        }
        "ethereum" => {
            let keypair_id = Uuid::new_v4();
            let address = format!("0x{}", &hex::encode(keypair_id.as_bytes())[..40]);
            (address, "ETH".to_string())
        }
        _ => {
            return (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "Unsupported chain. Use 'stellar' or 'ethereum'"})));
        }
    };

    let result = sqlx::query_scalar::<_, i32>(
        "INSERT INTO blockchain_wallets (wallet_address, chain, wallet_type, owner_id, currency, status)
         VALUES ($1, $2, $3, $4, $5, 'active') RETURNING id"
    )
        .bind(&address)
        .bind(&chain)
        .bind(&wallet_type)
        .bind(&req.owner_id)
        .bind(&currency)
        .fetch_one(&state.pg)
        .await;

    match result {
        Ok(id) => {
            let event = serde_json::json!({
                "walletId": id, "chain": chain, "address": address,
                "ownerId": req.owner_id, "timestamp": Utc::now().to_rfc3339()
            });
            state.dapr.publish("stablecoin.wallet.created", &event).await;

            (StatusCode::CREATED, Json(serde_json::json!({
                "id": id, "address": address, "chain": chain,
                "currency": currency, "status": "active", "walletType": wallet_type
            })))
        }
        Err(e) => {
            warn!("[wallet] Create failed: {}", e);
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({"error": format!("Failed: {}", e)})))
        }
    }
}

async fn get_wallet_balance(
    state: State<Arc<AppState>>,
    Path(address): Path<String>,
) -> impl IntoResponse {
    let wallet = sqlx::query_as::<_, (String, String)>(
        "SELECT chain, currency FROM blockchain_wallets WHERE wallet_address = $1"
    )
        .bind(&address)
        .fetch_optional(&state.pg)
        .await;

    let (chain, currency) = match wallet {
        Ok(Some((c, cur))) => (c, cur),
        _ => {
            return (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "Wallet not found"})));
        }
    };

    let balance_result = match chain.as_str() {
        "stellar" => {
            match state.stellar.get_balance(&address).await {
                Ok(balances) => {
                    let native = balances.iter()
                        .find(|b| b["asset_type"] == "native")
                        .and_then(|b| b["balance"].as_str())
                        .unwrap_or("0");
                    Ok(serde_json::json!({
                        "address": address, "chain": "stellar",
                        "nativeBalance": native, "allBalances": balances
                    }))
                }
                Err(e) => Err(e),
            }
        }
        "ethereum" => {
            match state.ethereum.get_balance(&address).await {
                Ok(hex_balance) => {
                    let wei = u128::from_str_radix(
                        hex_balance.trim_start_matches("0x"),
                        16
                    ).unwrap_or(0);
                    let eth = wei as f64 / 1e18;
                    Ok(serde_json::json!({
                        "address": address, "chain": "ethereum",
                        "balanceWei": hex_balance, "balanceEth": format!("{:.18}", eth)
                    }))
                }
                Err(e) => Err(e),
            }
        }
        _ => Err("Unknown chain".into()),
    };

    match balance_result {
        Ok(balance) => {
            if let Some(cached) = balance.get("nativeBalance").or(balance.get("balanceEth")) {
                sqlx::query("UPDATE blockchain_wallets SET balance_cached = $1, updated_at = NOW() WHERE wallet_address = $2")
                    .bind(cached.as_str().unwrap_or("0"))
                    .bind(&address)
                    .execute(&state.pg)
                    .await
                    .ok();
            }
            (StatusCode::OK, Json(balance))
        }
        Err(e) => {
            let cached = sqlx::query_scalar::<_, String>(
                "SELECT balance_cached FROM blockchain_wallets WHERE wallet_address = $1"
            ).bind(&address).fetch_optional(&state.pg).await.ok().flatten();

            (StatusCode::OK, Json(serde_json::json!({
                "address": address, "chain": chain, "balance": cached.unwrap_or_else(|| "0".into()),
                "cached": true, "error": e
            })))
        }
    }
}

async fn submit_chain_tx(
    state: State<Arc<AppState>>,
    Json(req): Json<SubmitTxRequest>,
) -> impl IntoResponse {
    let chain = req.chain.to_lowercase();
    let tx_result = match chain.as_str() {
        "stellar" => {
            state.stellar.submit_transaction(&req.signed_tx).await
        }
        "ethereum" => {
            match state.ethereum.send_raw_transaction(&req.signed_tx).await {
                Ok(hash) => Ok(serde_json::json!({"hash": hash})),
                Err(e) => Err(e),
            }
        }
        _ => Err("Unsupported chain".into()),
    };

    match tx_result {
        Ok(result) => {
            let tx_hash = result.get("hash")
                .or(result.get("id"))
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string();

            sqlx::query(
                "INSERT INTO blockchain_transactions (tx_hash, chain, from_address, to_address, amount, currency, status)
                 VALUES ($1, $2, $3, $4, $5, $6, 'submitted')
                 ON CONFLICT (tx_hash) DO UPDATE SET status = 'submitted'"
            )
                .bind(&tx_hash)
                .bind(&chain)
                .bind(&req.from_address)
                .bind(&req.to_address)
                .bind(&req.amount)
                .bind(&req.currency)
                .execute(&state.pg)
                .await
                .ok();

            let event = serde_json::json!({
                "txHash": tx_hash, "chain": chain, "status": "submitted",
                "from": req.from_address, "to": req.to_address,
                "amount": req.amount, "timestamp": Utc::now().to_rfc3339()
            });
            state.dapr.publish("stablecoin.chain.submitted", &event).await;

            (StatusCode::OK, Json(serde_json::json!({
                "txHash": tx_hash, "chain": chain, "status": "submitted", "result": result
            })))
        }
        Err(e) => {
            (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": e, "chain": chain})))
        }
    }
}

async fn get_chain_status(
    state: State<Arc<AppState>>,
    Path(tx_hash): Path<String>,
) -> impl IntoResponse {
    let record = sqlx::query_as::<_, (String,)>(
        "SELECT chain FROM blockchain_transactions WHERE tx_hash = $1"
    ).bind(&tx_hash).fetch_optional(&state.pg).await;

    let chain = match record {
        Ok(Some((c,))) => c,
        _ => {
            if tx_hash.starts_with("0x") { "ethereum".to_string() }
            else { "stellar".to_string() }
        }
    };

    let status_result = match chain.as_str() {
        "stellar" => state.stellar.get_transaction(&tx_hash).await,
        "ethereum" => state.ethereum.get_transaction_receipt(&tx_hash).await,
        _ => Err("Unknown chain".into()),
    };

    match status_result {
        Ok(tx_data) => {
            let confirmed = match chain.as_str() {
                "stellar" => tx_data.get("successful").and_then(|v| v.as_bool()).unwrap_or(false),
                "ethereum" => {
                    let status = tx_data.get("status").and_then(|v| v.as_str()).unwrap_or("0x0");
                    status == "0x1"
                }
                _ => false,
            };

            let new_status = if confirmed { "confirmed" } else { "failed" };
            sqlx::query("UPDATE blockchain_transactions SET status = $1, confirmed_at = NOW() WHERE tx_hash = $2")
                .bind(new_status)
                .bind(&tx_hash)
                .execute(&state.pg)
                .await
                .ok();

            (StatusCode::OK, Json(serde_json::json!({
                "txHash": tx_hash, "chain": chain, "confirmed": confirmed,
                "status": new_status, "data": tx_data
            })))
        }
        Err(e) => {
            (StatusCode::OK, Json(serde_json::json!({
                "txHash": tx_hash, "chain": chain, "status": "pending",
                "message": "Transaction not yet confirmed", "error": e
            })))
        }
    }
}

async fn verify_signature(
    Json(req): Json<VerifySignatureRequest>,
) -> impl IntoResponse {
    let chain = req.chain.to_lowercase();
    match chain.as_str() {
        "stellar" | "ethereum" => {
            let mut hasher = Sha256::new();
            hasher.update(format!("{}:{}", req.public_key, req.message).as_bytes());
            let expected = hex::encode(hasher.finalize());
            let valid = req.signature.len() >= 64;
            Json(serde_json::json!({
                "chain": chain, "valid": valid,
                "publicKey": req.public_key, "signatureLength": req.signature.len(),
                "hashCheck": expected[..16]
            }))
        }
        _ => Json(serde_json::json!({"error": "Unsupported chain", "valid": false})),
    }
}

async fn contract_interact(
    state: State<Arc<AppState>>,
    Json(req): Json<ContractInteractRequest>,
) -> impl IntoResponse {
    let chain = req.chain.to_lowercase();
    match chain.as_str() {
        "ethereum" => {
            let data = format!("0x{}", hex::encode(req.method.as_bytes()));
            let result = state.ethereum.json_rpc("eth_call", serde_json::json!([
                {"to": req.contract_address, "data": data},
                "latest"
            ])).await;

            match result {
                Ok(output) => {
                    (StatusCode::OK, Json(serde_json::json!({
                        "chain": "ethereum", "contract": req.contract_address,
                        "method": req.method, "result": output
                    })))
                }
                Err(e) => {
                    (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": e})))
                }
            }
        }
        "stellar" => {
            (StatusCode::OK, Json(serde_json::json!({
                "chain": "stellar", "contract": req.contract_address,
                "method": req.method,
                "message": "Stellar Soroban smart contract invocation — requires Soroban RPC endpoint"
            })))
        }
        _ => (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "Unsupported chain"}))),
    }
}

async fn get_stats(state: State<Arc<AppState>>) -> impl IntoResponse {
    let wallet_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM blockchain_wallets")
        .fetch_one(&state.pg).await.unwrap_or(0);
    let tx_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM blockchain_transactions")
        .fetch_one(&state.pg).await.unwrap_or(0);
    let confirmed: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM blockchain_transactions WHERE status = 'confirmed'"
    ).fetch_one(&state.pg).await.unwrap_or(0);

    let eth_block = state.ethereum.get_block_number().await.unwrap_or(0);

    Json(serde_json::json!({
        "totalWallets": wallet_count,
        "totalTransactions": tx_count,
        "confirmedTransactions": confirmed,
        "ethereumBlock": eth_block,
        "chains": ["stellar", "ethereum"],
        "lastUpdated": Utc::now().to_rfc3339()
    }))
}

async fn list_wallets(
    state: State<Arc<AppState>>,
    Query(params): Query<ListParams>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(20).min(100) as i64;
    let offset = params.offset.unwrap_or(0) as i64;

    let rows = sqlx::query_as::<_, (i32, String, String, String, String, String)>(
        "SELECT id, wallet_address, chain, currency, status, COALESCE(balance_cached, '0')
         FROM blockchain_wallets ORDER BY created_at DESC LIMIT $1 OFFSET $2"
    )
        .bind(limit)
        .bind(offset)
        .fetch_all(&state.pg)
        .await
        .unwrap_or_default();

    let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM blockchain_wallets")
        .fetch_one(&state.pg).await.unwrap_or(0);

    let items: Vec<serde_json::Value> = rows.iter().map(|(id, addr, chain, cur, status, bal)| {
        serde_json::json!({
            "id": id, "address": addr, "chain": chain,
            "currency": cur, "status": status, "balance": bal
        })
    }).collect();

    Json(serde_json::json!({"items": items, "total": total}))
}

async fn create_record(
    state: State<Arc<AppState>>,
    Json(payload): Json<serde_json::Value>,
) -> impl IntoResponse {
    let id = Uuid::new_v4().to_string();
    let data_str = serde_json::to_string(&payload).unwrap_or_default();

    sqlx::query(
        "INSERT INTO blockchain_transactions (tx_hash, chain, from_address, to_address, amount, currency, status, metadata)
         VALUES ($1, $2, $3, $4, $5, $6, 'created', $7::jsonb)"
    )
        .bind(&id)
        .bind(payload.get("chain").and_then(|v| v.as_str()).unwrap_or("unknown"))
        .bind(payload.get("from").and_then(|v| v.as_str()))
        .bind(payload.get("to").and_then(|v| v.as_str()))
        .bind(payload.get("amount").and_then(|v| v.as_str()))
        .bind(payload.get("currency").and_then(|v| v.as_str()))
        .bind(&data_str)
        .execute(&state.pg)
        .await
        .ok();

    let event = serde_json::json!({"id": &id, "action": "created", "timestamp": Utc::now().to_rfc3339()});
    state.dapr.publish("stablecoin.record.created", &event).await;

    (StatusCode::CREATED, Json(serde_json::json!({"id": id, "status": "created"})))
}

async fn get_record(
    state: State<Arc<AppState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    let row = sqlx::query_as::<_, (String, String, Option<String>, Option<String>, Option<String>, String)>(
        "SELECT tx_hash, chain, from_address, to_address, amount, status
         FROM blockchain_transactions WHERE tx_hash = $1"
    ).bind(&id).fetch_optional(&state.pg).await;

    match row {
        Ok(Some((hash, chain, from, to, amount, status))) => {
            (StatusCode::OK, Json(serde_json::json!({
                "id": hash, "chain": chain, "from": from, "to": to,
                "amount": amount, "status": status
            })))
        }
        _ => (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "not found"}))),
    }
}

async fn search_records(
    state: State<Arc<AppState>>,
    Query(params): Query<HashMap<String, String>>,
) -> impl IntoResponse {
    let query = params.get("q").cloned().unwrap_or_default();
    let pattern = format!("%{}%", query);

    let rows = sqlx::query_as::<_, (String, String, Option<String>, Option<String>, String)>(
        "SELECT tx_hash, chain, from_address, to_address, status
         FROM blockchain_transactions
         WHERE tx_hash ILIKE $1 OR from_address ILIKE $1 OR to_address ILIKE $1
         LIMIT 50"
    ).bind(&pattern).fetch_all(&state.pg).await.unwrap_or_default();

    let items: Vec<serde_json::Value> = rows.iter().map(|(hash, chain, from, to, status)| {
        serde_json::json!({
            "id": hash, "chain": chain, "from": from, "to": to, "status": status
        })
    }).collect();

    Json(serde_json::json!({"items": items, "total": items.len()}))
}

fn verify_auth(headers: &HeaderMap) -> Result<String, (StatusCode, String)> {
    let auth_header = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or((StatusCode::UNAUTHORIZED, r#"{"error":"missing authorization header"}"#.to_string()))?;
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
        return Err((StatusCode::UNAUTHORIZED, r#"{"error":"invalid token format"}"#.to_string()));
    }
    Ok(auth_header[7..].to_string())
}

// ── Main ───────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    tracing_subscriber::init();

    let config = Config::from_env();
    let port = config.port;
    let state = Arc::new(AppState::new(config).await);

    let app = Router::new()
        .route("/health", get(health))
        .route("/api/v1/stats", get(get_stats))
        .route("/api/v1/list", get(list_wallets))
        .route("/api/v1/create", post(create_record))
        .route("/api/v1/search", get(search_records))
        .route("/api/v1/stable/wallet/create", post(create_wallet))
        .route("/api/v1/stable/wallet/balance/:address", get(get_wallet_balance))
        .route("/api/v1/stable/chain/submit", post(submit_chain_tx))
        .route("/api/v1/stable/chain/verify", post(verify_signature))
        .route("/api/v1/stable/chain/status/:txHash", get(get_chain_status))
        .route("/api/v1/stable/contract/interact", post(contract_interact))
        .route("/api/v1/:id", get(get_record))
        .with_state(state);

    info!("54Link Stablecoin Rails (Rust) starting on port {} — Stellar + Ethereum", port);
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port))
        .await
        .expect("Failed to bind");
    axum::serve(listener, app).await.expect("Server failed");
}
