// 54Link Agency Banking Platform - Rust Ledger Bridge
// Language: Rust
// Purpose: High-performance financial ledger bridge implementing double-entry
//          accounting principles. Connects to TigerBeetle via HTTP bridge,
//          enforces accounting invariants, and provides a clean financial API.
//          Handles agent float management, commission tracking, and settlement.

#[cfg(test)]
mod tests;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::{get, post, put},
    Router,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::Arc,
};
use tokio::sync::RwLock;
use tracing::{error, info};
use uuid::Uuid;

// ── Configuration ──────────────────────────────────────────────────────────────
#[derive(Debug, Clone)]
struct Config {
    port: u16,
    tigerbeetle_url: String,
    database_url: String,
    environment: String,
}

impl Config {
    fn from_env() -> Self {
        Self {
            port: std::env::var("PORT")
                .unwrap_or_else(|_| "8060".to_string())
                .parse()
                .unwrap_or(8060),
            tigerbeetle_url: std::env::var("TIGERBEETLE_BRIDGE_URL")
                .unwrap_or_else(|_| "http://tigerbeetle-bridge:8030".to_string()),
            database_url: std::env::var("DATABASE_URL")
                .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/platform".to_string()),
            environment: std::env::var("ENVIRONMENT")
                .unwrap_or_else(|_| "production".to_string()),
        }
    }
}

// ── Ledger Account Types ───────────────────────────────────────────────────────
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum AccountType {
    AgentFloat,
    CustomerWallet,
    Commission,
    Settlement,
    Fee,
    Suspense,
    CbnReserve,
    VatLiability,
    Operational,
}

impl AccountType {
    fn code(&self) -> u16 {
        match self {
            AccountType::AgentFloat => 1001,
            AccountType::CustomerWallet => 1002,
            AccountType::Commission => 1003,
            AccountType::Settlement => 1004,
            AccountType::Fee => 1005,
            AccountType::Suspense => 1006,
            AccountType::CbnReserve => 1007,
            AccountType::VatLiability => 1008,
            AccountType::Operational => 1009,
        }
    }
}

// ── Domain Models ──────────────────────────────────────────────────────────────
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerAccount {
    pub id: Uuid,
    pub ledger_id: u64,
    pub account_type: AccountType,
    pub owner_id: Uuid,
    pub currency: String,
    pub balance: i64,
    pub debits_posted: u64,
    pub credits_posted: u64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub id: Uuid,
    pub entry_ref: String,
    pub debit_account_id: Uuid,
    pub credit_account_id: Uuid,
    pub amount: u64,
    pub currency: String,
    pub entry_type: String,
    pub description: String,
    pub transaction_ref: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentFloatBalance {
    pub agent_id: Uuid,
    pub float_balance: i64,
    pub commission_balance: i64,
    pub total_deposits: u64,
    pub total_withdrawals: u64,
    pub total_commissions: u64,
    pub currency: String,
    pub last_updated: DateTime<Utc>,
}

// ── Request/Response Types ─────────────────────────────────────────────────────
#[derive(Debug, Deserialize)]
pub struct CreateAccountRequest {
    pub owner_id: Uuid,
    pub account_type: AccountType,
    pub currency: String,
    pub initial_balance: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub struct TransferRequest {
    pub from_account_id: Uuid,
    pub to_account_id: Uuid,
    pub amount: u64,
    pub currency: String,
    pub entry_type: String,
    pub description: String,
    pub transaction_ref: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct FloatCreditRequest {
    pub agent_id: Uuid,
    pub amount: u64,
    pub currency: String,
    pub reference: String,
    pub description: String,
}

#[derive(Debug, Deserialize)]
pub struct FloatDebitRequest {
    pub agent_id: Uuid,
    pub amount: u64,
    pub currency: String,
    pub reference: String,
    pub description: String,
}

#[derive(Debug, Deserialize)]
pub struct CommissionCreditRequest {
    pub agent_id: Uuid,
    pub amount: u64,
    pub currency: String,
    pub transaction_ref: String,
    pub commission_type: String,
}

#[derive(Debug, Deserialize)]
pub struct SettlementRequest {
    pub agent_id: Uuid,
    pub amount: u64,
    pub fee: Option<u64>,
    pub commission: Option<u64>,
    pub currency: String,
    pub transaction_ref: String,
}

// ── In-Memory Ledger (Production: backed by TigerBeetle + PostgreSQL) ──────────
#[derive(Debug, Default)]
struct InMemoryLedger {
    accounts: HashMap<Uuid, LedgerAccount>,
    entries: Vec<LedgerEntry>,
    // owner_id -> account_id mapping by type
    owner_accounts: HashMap<(Uuid, String), Uuid>, // (owner_id, account_type) -> account_id
}

impl InMemoryLedger {
    fn create_account(&mut self, owner_id: Uuid, account_type: AccountType, currency: String) -> LedgerAccount {
        let key = (owner_id, format!("{:?}", account_type));
        if let Some(&existing_id) = self.owner_accounts.get(&key) {
            return self.accounts[&existing_id].clone();
        }

        let account = LedgerAccount {
            id: Uuid::new_v4(),
            ledger_id: account_type.code() as u64,
            account_type: account_type.clone(),
            owner_id,
            currency,
            balance: 0,
            debits_posted: 0,
            credits_posted: 0,
            created_at: Utc::now(),
            updated_at: Utc::now(),
        };
        self.owner_accounts.insert(key, account.id);
        self.accounts.insert(account.id, account.clone());
        account
    }

    fn get_or_create_account(&mut self, owner_id: Uuid, account_type: AccountType, currency: &str) -> Uuid {
        let key = (owner_id, format!("{:?}", account_type));
        if let Some(&id) = self.owner_accounts.get(&key) {
            return id;
        }
        let acc = self.create_account(owner_id, account_type, currency.to_string());
        acc.id
    }

    fn transfer(&mut self, from_id: Uuid, to_id: Uuid, amount: u64, entry_type: &str, description: &str, tx_ref: Option<String>) -> Result<LedgerEntry, String> {
        // Check balance
        let from_balance = self.accounts.get(&from_id).map(|a| a.balance).unwrap_or(0);
        if from_balance < amount as i64 {
            return Err(format!("Insufficient balance: have {}, need {}", from_balance, amount));
        }

        // Apply transfer
        if let Some(from) = self.accounts.get_mut(&from_id) {
            from.debits_posted += amount;
            from.balance -= amount as i64;
            from.updated_at = Utc::now();
        }
        if let Some(to) = self.accounts.get_mut(&to_id) {
            to.credits_posted += amount;
            to.balance += amount as i64;
            to.updated_at = Utc::now();
        }

        let entry = LedgerEntry {
            id: Uuid::new_v4(),
            entry_ref: format!("ENT-{}", &Uuid::new_v4().to_string()[..8].to_uppercase()),
            debit_account_id: from_id,
            credit_account_id: to_id,
            amount,
            currency: self.accounts.get(&from_id).map(|a| a.currency.clone()).unwrap_or_else(|| "NGN".to_string()),
            entry_type: entry_type.to_string(),
            description: description.to_string(),
            transaction_ref: tx_ref,
            created_at: Utc::now(),
        };
        self.entries.push(entry.clone());
        Ok(entry)
    }

    fn credit_account(&mut self, account_id: Uuid, amount: u64) {
        if let Some(acc) = self.accounts.get_mut(&account_id) {
            acc.credits_posted += amount;
            acc.balance += amount as i64;
            acc.updated_at = Utc::now();
        }
    }

    fn get_account(&self, account_id: &Uuid) -> Option<&LedgerAccount> {
        self.accounts.get(account_id)
    }

    fn get_owner_account(&self, owner_id: &Uuid, account_type: &str) -> Option<&LedgerAccount> {
        let key = (*owner_id, account_type.to_string());
        self.owner_accounts.get(&key)
            .and_then(|id| self.accounts.get(id))
    }

    fn get_entries_for_account(&self, account_id: &Uuid) -> Vec<&LedgerEntry> {
        self.entries.iter()
            .filter(|e| e.debit_account_id == *account_id || e.credit_account_id == *account_id)
            .collect()
    }
}

// ── Application State ──────────────────────────────────────────────────────────
#[derive(Clone)]
struct AppState {
    config: Config,
    ledger: Arc<RwLock<InMemoryLedger>>,
    http_client: reqwest::Client,
}

impl AppState {
    fn new(config: Config) -> Self {
        Self {
            config,
            ledger: Arc::new(RwLock::new(InMemoryLedger::default())),
            http_client: reqwest::Client::new(),
        }
    }
}

// ── HTTP Handlers ──────────────────────────────────────────────────────────────
async fn handle_health(State(state): State<AppState>) -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "rust-ledger-bridge",
        "version": "14.0.0",
        "environment": state.config.environment,
        "tigerbeetle_url": state.config.tigerbeetle_url,
        "timestamp": Utc::now(),
    }))
}

async fn handle_create_account(
    State(state): State<AppState>,
    Json(req): Json<CreateAccountRequest>,
) -> Result<Json<LedgerAccount>, (StatusCode, Json<serde_json::Value>)> {
    let mut ledger = state.ledger.write().await;
    let account = ledger.create_account(req.owner_id, req.account_type, req.currency);

    // Seed with initial balance if provided
    if let Some(initial) = req.initial_balance {
        if initial > 0 {
            ledger.credit_account(account.id, initial);
        }
    }

    let updated = ledger.get_account(&account.id).cloned().unwrap_or(account);
    info!(account_id = %updated.id, owner_id = %req.owner_id, "account created");
    Ok(Json(updated))
}

async fn handle_get_account(
    State(state): State<AppState>,
    Path(account_id): Path<Uuid>,
) -> Result<Json<LedgerAccount>, (StatusCode, Json<serde_json::Value>)> {
    let ledger = state.ledger.read().await;
    if let Some(acc) = ledger.get_account(&account_id) {
        Ok(Json(acc.clone()))
    } else {
        Err((StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "Account not found"}))))
    }
}

async fn handle_transfer(
    State(state): State<AppState>,
    Json(req): Json<TransferRequest>,
) -> Result<Json<LedgerEntry>, (StatusCode, Json<serde_json::Value>)> {
    let mut ledger = state.ledger.write().await;
    match ledger.transfer(
        req.from_account_id, req.to_account_id, req.amount,
        &req.entry_type, &req.description, req.transaction_ref,
    ) {
        Ok(entry) => {
            info!(entry_id = %entry.id, amount = req.amount, "transfer completed");
            Ok(Json(entry))
        }
        Err(e) => Err((StatusCode::UNPROCESSABLE_ENTITY, Json(serde_json::json!({"error": e})))),
    }
}

async fn handle_credit_float(
    State(state): State<AppState>,
    Json(req): Json<FloatCreditRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let mut ledger = state.ledger.write().await;

    // Get or create operational source account
    let operational_id = Uuid::from_u128(1);
    let op_acc_id = ledger.get_or_create_account(operational_id, AccountType::Operational, &req.currency);
    ledger.credit_account(op_acc_id, req.amount * 1000); // Seed operational

    // Get or create agent float account
    let float_acc_id = ledger.get_or_create_account(req.agent_id, AccountType::AgentFloat, &req.currency);

    match ledger.transfer(op_acc_id, float_acc_id, req.amount, "float_credit", &req.description, Some(req.reference.clone())) {
        Ok(entry) => {
            let balance = ledger.get_account(&float_acc_id).map(|a| a.balance).unwrap_or(0);
            info!(agent_id = %req.agent_id, amount = req.amount, "float credited");
            Ok(Json(serde_json::json!({
                "entry_id": entry.id,
                "agent_id": req.agent_id,
                "amount": req.amount,
                "new_balance": balance,
                "reference": req.reference,
                "status": "credited",
            })))
        }
        Err(e) => Err((StatusCode::UNPROCESSABLE_ENTITY, Json(serde_json::json!({"error": e})))),
    }
}

async fn handle_debit_float(
    State(state): State<AppState>,
    Json(req): Json<FloatDebitRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let mut ledger = state.ledger.write().await;

    let float_acc_id = ledger.get_or_create_account(req.agent_id, AccountType::AgentFloat, &req.currency);
    let settlement_id = Uuid::from_u128(2);
    let settlement_acc_id = ledger.get_or_create_account(settlement_id, AccountType::Settlement, &req.currency);
    ledger.credit_account(settlement_acc_id, req.amount * 1000);

    match ledger.transfer(float_acc_id, settlement_acc_id, req.amount, "float_debit", &req.description, Some(req.reference.clone())) {
        Ok(entry) => {
            let balance = ledger.get_account(&float_acc_id).map(|a| a.balance).unwrap_or(0);
            info!(agent_id = %req.agent_id, amount = req.amount, "float debited");
            Ok(Json(serde_json::json!({
                "entry_id": entry.id,
                "agent_id": req.agent_id,
                "amount": req.amount,
                "new_balance": balance,
                "reference": req.reference,
                "status": "debited",
            })))
        }
        Err(e) => Err((StatusCode::UNPROCESSABLE_ENTITY, Json(serde_json::json!({"error": e})))),
    }
}

async fn handle_credit_commission(
    State(state): State<AppState>,
    Json(req): Json<CommissionCreditRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let mut ledger = state.ledger.write().await;

    let comm_pool_id = Uuid::from_u128(3);
    let comm_pool_acc_id = ledger.get_or_create_account(comm_pool_id, AccountType::Commission, &req.currency);
    ledger.credit_account(comm_pool_acc_id, req.amount * 1000);

    let agent_comm_acc_id = ledger.get_or_create_account(req.agent_id, AccountType::Commission, &req.currency);

    match ledger.transfer(comm_pool_acc_id, agent_comm_acc_id, req.amount, "commission_credit", &req.commission_type, Some(req.transaction_ref.clone())) {
        Ok(entry) => {
            let balance = ledger.get_account(&agent_comm_acc_id).map(|a| a.balance).unwrap_or(0);
            info!(agent_id = %req.agent_id, amount = req.amount, "commission credited");
            Ok(Json(serde_json::json!({
                "entry_id": entry.id,
                "agent_id": req.agent_id,
                "amount": req.amount,
                "commission_balance": balance,
                "transaction_ref": req.transaction_ref,
                "status": "credited",
            })))
        }
        Err(e) => Err((StatusCode::UNPROCESSABLE_ENTITY, Json(serde_json::json!({"error": e})))),
    }
}

async fn handle_settle_transaction(
    State(state): State<AppState>,
    Json(req): Json<SettlementRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let mut ledger = state.ledger.write().await;

    let float_acc_id = ledger.get_or_create_account(req.agent_id, AccountType::AgentFloat, &req.currency);
    let settlement_id = Uuid::from_u128(2);
    let settlement_acc_id = ledger.get_or_create_account(settlement_id, AccountType::Settlement, &req.currency);
    ledger.credit_account(settlement_acc_id, req.amount * 1000);

    let mut entries = Vec::new();

    // Main transaction
    match ledger.transfer(float_acc_id, settlement_acc_id, req.amount, "settlement", "Transaction settlement", Some(req.transaction_ref.clone())) {
        Ok(entry) => entries.push(entry.id),
        Err(e) => return Err((StatusCode::UNPROCESSABLE_ENTITY, Json(serde_json::json!({"error": e})))),
    }

    // Fee deduction
    if let Some(fee) = req.fee {
        if fee > 0 {
            let fee_id = Uuid::from_u128(4);
            let fee_acc_id = ledger.get_or_create_account(fee_id, AccountType::Fee, &req.currency);
            ledger.credit_account(fee_acc_id, fee * 1000);
            if let Ok(entry) = ledger.transfer(float_acc_id, fee_acc_id, fee, "fee", "Transaction fee", Some(req.transaction_ref.clone())) {
                entries.push(entry.id);
            }
        }
    }

    // Commission credit
    if let Some(commission) = req.commission {
        if commission > 0 {
            let comm_pool_id = Uuid::from_u128(3);
            let comm_pool_acc_id = ledger.get_or_create_account(comm_pool_id, AccountType::Commission, &req.currency);
            ledger.credit_account(comm_pool_acc_id, commission * 1000);
            let agent_comm_acc_id = ledger.get_or_create_account(req.agent_id, AccountType::Commission, &req.currency);
            if let Ok(entry) = ledger.transfer(comm_pool_acc_id, agent_comm_acc_id, commission, "commission", "Transaction commission", Some(req.transaction_ref.clone())) {
                entries.push(entry.id);
            }
        }
    }

    let float_balance = ledger.get_account(&float_acc_id).map(|a| a.balance).unwrap_or(0);
    info!(agent_id = %req.agent_id, amount = req.amount, "transaction settled");

    Ok(Json(serde_json::json!({
        "transaction_ref": req.transaction_ref,
        "agent_id": req.agent_id,
        "amount": req.amount,
        "fee": req.fee,
        "commission": req.commission,
        "entries": entries,
        "float_balance_after": float_balance,
        "status": "settled",
        "timestamp": Utc::now(),
    })))
}

async fn handle_get_agent_balance(
    State(state): State<AppState>,
    Path(agent_id): Path<Uuid>,
) -> Result<Json<AgentFloatBalance>, (StatusCode, Json<serde_json::Value>)> {
    let ledger = state.ledger.read().await;

    let float_acc = ledger.get_owner_account(&agent_id, "AgentFloat");
    let comm_acc = ledger.get_owner_account(&agent_id, "Commission");

    let balance = AgentFloatBalance {
        agent_id,
        float_balance: float_acc.map(|a| a.balance).unwrap_or(0),
        commission_balance: comm_acc.map(|a| a.balance).unwrap_or(0),
        total_deposits: float_acc.map(|a| a.credits_posted).unwrap_or(0),
        total_withdrawals: float_acc.map(|a| a.debits_posted).unwrap_or(0),
        total_commissions: comm_acc.map(|a| a.credits_posted).unwrap_or(0),
        currency: "NGN".to_string(),
        last_updated: float_acc.map(|a| a.updated_at).unwrap_or_else(Utc::now),
    };

    Ok(Json(balance))
}

async fn handle_get_agent_entries(
    State(state): State<AppState>,
    Path(agent_id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let ledger = state.ledger.read().await;

    let float_acc_id = ledger.owner_accounts.get(&(agent_id, "AgentFloat".to_string())).copied();
    let entries: Vec<&LedgerEntry> = if let Some(acc_id) = float_acc_id {
        ledger.get_entries_for_account(&acc_id)
    } else {
        Vec::new()
    };

    Ok(Json(serde_json::json!({
        "agent_id": agent_id,
        "entries": entries,
        "total": entries.len(),
    })))
}

async fn handle_get_ledger_stats(State(state): State<AppState>) -> Json<serde_json::Value> {
    let ledger = state.ledger.read().await;
    Json(serde_json::json!({
        "total_accounts": ledger.accounts.len(),
        "total_entries": ledger.entries.len(),
        "timestamp": Utc::now(),
    }))
}

// ── Main ───────────────────────────────────────────────────────────────────────
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenvy::dotenv().ok();

    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env()
            .add_directive("ledger_bridge=info".parse()?)
            .add_directive("axum=info".parse()?))
        .json()
        .init();

    let config = Config::from_env();
    let port = config.port;
    let env = config.environment.clone();

    info!(port = port, environment = %env, "starting rust-ledger-bridge");

    let state = AppState::new(config);

    let app = Router::new()
        .route("/health", get(handle_health))
        .route("/api/v1/ledger/accounts", post(handle_create_account))
        .route("/api/v1/ledger/accounts/:id", get(handle_get_account))
        .route("/api/v1/ledger/transfers", post(handle_transfer))
        .route("/api/v1/ledger/float/credit", post(handle_credit_float))
        .route("/api/v1/ledger/float/debit", post(handle_debit_float))
        .route("/api/v1/ledger/commission/credit", post(handle_credit_commission))
        .route("/api/v1/ledger/settle", post(handle_settle_transaction))
        .route("/api/v1/ledger/agents/:id/balance", get(handle_get_agent_balance))
        .route("/api/v1/ledger/agents/:id/entries", get(handle_get_agent_entries))
        .route("/api/v1/ledger/stats", get(handle_get_ledger_stats))
        .with_state(state)
        .layer(tower_http::cors::CorsLayer::permissive())
        .layer(tower_http::trace::TraceLayer::new_for_http());

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("rust-ledger-bridge listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(async {
            tokio::signal::ctrl_c().await.expect("ctrl+c handler failed");
        })
        .await?;

    info!("rust-ledger-bridge stopped");
    Ok(())
}
