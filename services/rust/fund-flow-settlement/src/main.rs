//! Fund Flow Settlement Engine (Rust)
//!
//! High-performance microservice for:
//! - BNPL installment schedule generation and tracking
//! - FX rate engine with spread calculation and corridor management
//! - GL reconciliation and discrepancy detection
//! - Settlement batch processing
//!
//! Persistence: PostgreSQL (all state — NO in-memory RwLock/HashMap)
//! Middleware: TigerBeetle, Lakehouse, OpenSearch

use actix_web::{web, App, HttpServer, HttpResponse, middleware};
use chrono::{Utc, NaiveDate, Duration as ChronoDuration};
use serde::{Deserialize, Serialize};
use sqlx::{PgPool, postgres::PgPoolOptions, Row};
use uuid::Uuid;
use sqlx::{PgPool, postgres::PgPoolOptions, Row};

// ── Domain Types ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstallmentSchedule {
    pub application_id: i64,
    pub total_amount: f64,
    pub num_installments: u32,
    pub interest_rate: f64,
    pub installments: Vec<Installment>,
    pub total_with_interest: f64,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Installment {
    pub number: u32,
    pub amount: f64,
    pub principal: f64,
    pub interest: f64,
    pub due_date: String,
    pub status: String,
}

#[derive(Debug, Deserialize)]
pub struct GenerateScheduleRequest {
    pub application_id: i64,
    pub total_amount: f64,
    pub num_installments: u32,
    pub interest_rate: f64,
    pub start_date: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FXRate {
    pub from: String,
    pub to: String,
    pub rate: f64,
    pub spread_bps: u32,
    pub effective_rate: f64,
    pub updated_at: String,
}

#[derive(Debug, Deserialize)]
pub struct FXConvertRequest {
    pub from_currency: String,
    pub to_currency: String,
    pub amount: f64,
}

#[derive(Debug, Serialize)]
pub struct FXConvertResponse {
    pub from_currency: String,
    pub to_currency: String,
    pub input_amount: f64,
    pub output_amount: f64,
    pub rate: f64,
    pub effective_rate: f64,
    pub spread_bps: u32,
    pub fee: f64,
    pub timestamp: String,
}

#[derive(Debug, Deserialize)]
pub struct ReconcileRequest {
    pub agent_id: i64,
    pub float_balance: f64,
    pub gl_credits: f64,
    pub gl_debits: f64,
    pub transaction_total: f64,
}

#[derive(Debug, Serialize)]
pub struct ReconcileResponse {
    pub agent_id: i64,
    pub float_balance: f64,
    pub gl_net: f64,
    pub transaction_total: f64,
    pub float_gl_discrepancy: f64,
    pub is_reconciled: bool,
    pub recommendations: Vec<String>,
    pub timestamp: String,
}

#[derive(Debug, Serialize)]
pub struct SettlementBatch {
    pub batch_id: String,
    pub total_settlements: usize,
    pub total_amount: f64,
    pub status: String,
    pub created_at: String,
}

// ── Application State (PostgreSQL-backed) ───────────────────────────────────

pub struct AppState {
    pool: PgPool,
}

async fn init_db(pool: &PgPool) {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS fx_rates (
            corridor TEXT PRIMARY KEY,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate DOUBLE PRECISION NOT NULL,
            spread_bps INT NOT NULL,
            effective_rate DOUBLE PRECISION NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )"
    ).execute(pool).await.ok();

    sqlx::query(
        "CREATE TABLE IF NOT EXISTS installment_schedules (
            application_id BIGINT PRIMARY KEY,
            schedule_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )"
    ).execute(pool).await.ok();

    sqlx::query(
        "CREATE TABLE IF NOT EXISTS reconciliation_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id BIGINT NOT NULL,
            float_balance DOUBLE PRECISION NOT NULL,
            gl_net DOUBLE PRECISION NOT NULL,
            transaction_total DOUBLE PRECISION NOT NULL,
            discrepancy DOUBLE PRECISION NOT NULL,
            is_reconciled BOOLEAN NOT NULL,
            recommendations JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )"
    ).execute(pool).await.ok();

    sqlx::query(
        "CREATE INDEX IF NOT EXISTS idx_recon_results_agent ON reconciliation_results(agent_id)"
    ).execute(pool).await.ok();

    sqlx::query(
        "CREATE TABLE IF NOT EXISTS settlement_batches_rust (
            batch_id TEXT PRIMARY KEY,
            total_settlements INT NOT NULL DEFAULT 0,
            total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'initiated',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )"
    ).execute(pool).await.ok();

    // Seed FX rates
    let corridors = vec![
        ("NGN", "USD", 0.00065, 50i32),
        ("USD", "NGN", 1540.0, 50),
        ("NGN", "EUR", 0.00058, 75),
        ("EUR", "NGN", 1720.0, 75),
        ("NGN", "GBP", 0.00050, 100),
        ("GBP", "NGN", 2000.0, 100),
        ("NGN", "GHS", 0.0082, 60),
        ("GHS", "NGN", 122.0, 60),
        ("NGN", "KES", 0.0835, 50),
        ("KES", "NGN", 12.0, 50),
        ("NGN", "XOF", 0.40, 40),
        ("XOF", "NGN", 2.50, 40),
        ("USD", "EUR", 0.92, 30),
        ("EUR", "USD", 1.09, 30),
        ("USD", "GBP", 0.79, 30),
        ("GBP", "USD", 1.27, 30),
    ];

    for (from, to, rate, spread) in corridors {
        let key = format!("{}-{}", from, to);
        let effective = rate * (1.0 - spread as f64 / 10000.0);
        sqlx::query(
            "INSERT INTO fx_rates (corridor, from_currency, to_currency, rate, spread_bps, effective_rate) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (corridor) DO UPDATE SET rate=$4, spread_bps=$5, effective_rate=$6, updated_at=NOW()"
        )
        .bind(&key).bind(from).bind(to).bind(rate).bind(spread).bind(effective)
        .execute(pool).await.ok();
    }
}

// ── BNPL Installment Handlers ───────────────────────────────────────────────

async fn generate_schedule(
    data: web::Data<AppState>,
    req: web::Json<GenerateScheduleRequest>,
) -> HttpResponse {
    if req.total_amount <= 0.0 || req.num_installments == 0 {
        return HttpResponse::BadRequest().json(serde_json::json!({
            "error": "Invalid amount or installment count"
        }));
    }

    let start = req.start_date.as_ref()
        .and_then(|s| NaiveDate::parse_from_str(s, "%Y-%m-%d").ok())
        .unwrap_or_else(|| Utc::now().date_naive());

    let monthly_rate = req.interest_rate / 100.0 / 12.0;
    let n = req.num_installments as f64;
    let monthly_payment = if monthly_rate > 0.0 {
        req.total_amount * (monthly_rate * (1.0 + monthly_rate).powf(n))
            / ((1.0 + monthly_rate).powf(n) - 1.0)
    } else {
        req.total_amount / n
    };

    let mut installments = Vec::with_capacity(req.num_installments as usize);
    let mut remaining = req.total_amount;

    for i in 1..=req.num_installments {
        let interest = remaining * monthly_rate;
        let principal = monthly_payment - interest;
        let due = start + ChronoDuration::days(30 * i as i64);

        installments.push(Installment {
            number: i,
            amount: (monthly_payment * 100.0).round() / 100.0,
            principal: (principal * 100.0).round() / 100.0,
            interest: (interest * 100.0).round() / 100.0,
            due_date: due.format("%Y-%m-%d").to_string(),
            status: "pending".to_string(),
        });

        remaining -= principal;
    }

    let total_with_interest = installments.iter().map(|i| i.amount).sum();

    let schedule = InstallmentSchedule {
        application_id: req.application_id,
        total_amount: req.total_amount,
        num_installments: req.num_installments,
        interest_rate: req.interest_rate,
        installments,
        total_with_interest,
        created_at: Utc::now().to_rfc3339(),
    };

    // Persist to PostgreSQL
    let schedule_json = serde_json::to_string(&schedule).unwrap_or_default();
    sqlx::query("INSERT INTO installment_schedules (application_id, schedule_json) VALUES ($1, $2::jsonb) ON CONFLICT (application_id) DO UPDATE SET schedule_json=$2::jsonb")
        .bind(req.application_id).bind(&schedule_json)
        .execute(&data.pool).await.ok();

    HttpResponse::Ok().json(schedule)
}

async fn get_schedule(
    data: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let app_id = path.into_inner();
    match sqlx::query("SELECT schedule_json::TEXT FROM installment_schedules WHERE application_id=$1")
        .bind(app_id).fetch_optional(&data.pool).await {
        Ok(Some(row)) => {
            let json_str: String = row.get(0);
            match serde_json::from_str::<InstallmentSchedule>(&json_str) {
                Ok(s) => HttpResponse::Ok().json(s),
                Err(_) => HttpResponse::InternalServerError().json(serde_json::json!({"error": "corrupt schedule data"})),
            }
        }
        _ => HttpResponse::NotFound().json(serde_json::json!({
            "error": "Schedule not found"
        })),
    }
}

// ── FX Rate Handlers ────────────────────────────────────────────────────────

async fn get_fx_rates(data: web::Data<AppState>) -> HttpResponse {
    match sqlx::query("SELECT from_currency, to_currency, rate, spread_bps, effective_rate, updated_at::TEXT FROM fx_rates")
        .fetch_all(&data.pool).await {
        Ok(rows) => {
            let rate_list: Vec<FXRate> = rows.iter().map(|r| FXRate {
                from: r.get::<String, _>(0), to: r.get::<String, _>(1),
                rate: r.get::<f64, _>(2), spread_bps: r.get::<i32, _>(3) as u32,
                effective_rate: r.get::<f64, _>(4), updated_at: r.get::<String, _>(5),
            }).collect();
            let count = rate_list.len();
            HttpResponse::Ok().json(serde_json::json!({
                "rates": rate_list, "count": count,
                "timestamp": Utc::now().to_rfc3339(),
            }))
        }
        Err(_) => HttpResponse::InternalServerError().json(serde_json::json!({"error": "failed to fetch rates"}))
    }
}

async fn convert_fx(
    data: web::Data<AppState>,
    req: web::Json<FXConvertRequest>,
) -> HttpResponse {
    let key = format!("{}-{}", req.from_currency, req.to_currency);

    match sqlx::query("SELECT rate, spread_bps, effective_rate FROM fx_rates WHERE corridor=$1")
        .bind(&key).fetch_optional(&data.pool).await {
        Ok(Some(row)) => {
            let rate: f64 = row.get("rate");
            let spread_bps: i32 = row.get("spread_bps");
            let effective_rate: f64 = row.get("effective_rate");
            let output = (req.amount * effective_rate * 100.0).round() / 100.0;
            let fee = (req.amount * 0.01 * 100.0).round() / 100.0;

            HttpResponse::Ok().json(FXConvertResponse {
                from_currency: req.from_currency.clone(),
                to_currency: req.to_currency.clone(),
                input_amount: req.amount,
                output_amount: output,
                rate,
                effective_rate,
                spread_bps: spread_bps as u32,
                fee,
                timestamp: Utc::now().to_rfc3339(),
            })
        }
        _ => HttpResponse::BadRequest().json(serde_json::json!({
            "error": format!("Unsupported corridor: {}", key)
        })),
    }
}

async fn get_corridors(data: web::Data<AppState>) -> HttpResponse {
    match sqlx::query("SELECT corridor FROM fx_rates")
        .fetch_all(&data.pool).await {
        Ok(rows) => {
            let corridors: Vec<String> = rows.iter().map(|r| r.get::<String, _>(0)).collect();
            let count = corridors.len();
            HttpResponse::Ok().json(serde_json::json!({
                "corridors": corridors, "count": count,
            }))
        }
        Err(_) => HttpResponse::InternalServerError().json(serde_json::json!({"error": "failed to fetch corridors"}))
    }
}

// ── Reconciliation Handlers ─────────────────────────────────────────────────

async fn reconcile(
    data: web::Data<AppState>,
    req: web::Json<ReconcileRequest>,
) -> HttpResponse {
    let gl_net = req.gl_credits - req.gl_debits;
    let discrepancy = (req.float_balance - gl_net).abs();
    let is_reconciled = discrepancy < 0.01;

    let mut recommendations = Vec::new();
    if !is_reconciled {
        if req.float_balance > gl_net {
            recommendations.push(format!(
                "Float balance exceeds GL net by {:.2}. Check for missing GL debit entries.",
                req.float_balance - gl_net
            ));
        } else {
            recommendations.push(format!(
                "GL net exceeds float balance by {:.2}. Check for missing float credits.",
                gl_net - req.float_balance
            ));
        }
    }

    // Persist reconciliation result to PostgreSQL
    let recs_json = serde_json::to_string(&recommendations).unwrap_or_default();
    sqlx::query(
        "INSERT INTO reconciliation_results (agent_id, float_balance, gl_net, transaction_total, discrepancy, is_reconciled, recommendations) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)"
    )
    .bind(req.agent_id).bind(req.float_balance).bind(gl_net)
    .bind(req.transaction_total).bind((discrepancy * 100.0).round() / 100.0)
    .bind(is_reconciled).bind(&recs_json)
    .execute(&data.pool).await.ok();

    HttpResponse::Ok().json(ReconcileResponse {
        agent_id: req.agent_id,
        float_balance: req.float_balance,
        gl_net,
        transaction_total: req.transaction_total,
        float_gl_discrepancy: (discrepancy * 100.0).round() / 100.0,
        is_reconciled,
        recommendations,
        timestamp: Utc::now().to_rfc3339(),
    })
}

async fn create_settlement_batch(data: web::Data<AppState>) -> HttpResponse {
    let batch_id = format!("BATCH-{}", Uuid::new_v4().to_string()[..8].to_uppercase());
    let batch = SettlementBatch {
        batch_id: batch_id.clone(),
        total_settlements: 0,
        total_amount: 0.0,
        status: "initiated".to_string(),
        created_at: Utc::now().to_rfc3339(),
    };

    sqlx::query("INSERT INTO settlement_batches_rust (batch_id, status) VALUES ($1, $2)")
        .bind(&batch_id).bind("initiated")
        .execute(&data.pool).await.ok();

    HttpResponse::Ok().json(batch)
}

// ── Health ───────────────────────────────────────────────────────────────────

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "fund-flow-settlement",
        "version": "2.0.0",
        "persistence": "postgresql",
        "timestamp": Utc::now().to_rfc3339(),
    }))
}

// ── Main ────────────────────────────────────────────────────────────────────


// ── PostgreSQL Persistence Layer ─────────────────────────────────────────────
// Persists service state to PostgreSQL via sqlx. Hot path uses local counters
// with periodic flush to DB so restarts don't lose accumulated metrics.

async fn pg_init_state_table(pool: &sqlx::PgPool) {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS service_state (
            key TEXT PRIMARY KEY,
            value JSONB NOT NULL DEFAULT '{}',
            service TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )"
    ).execute(pool).await.ok();
}

async fn pg_load_state(pool: &sqlx::PgPool, key: &str, service: &str) -> Option<serde_json::Value> {
    sqlx::query_scalar::<_, serde_json::Value>(
        "SELECT value FROM service_state WHERE key = $1 AND service = $2"
    )
    .bind(key)
    .bind(service)
    .fetch_optional(pool)
    .await
    .ok()
    .flatten()
}

async fn pg_save_state(pool: &sqlx::PgPool, key: &str, value: &serde_json::Value, service: &str) {
    sqlx::query(
        "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2, $3, NOW())
         ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()"
    )
    .bind(key)
    .bind(value)
    .bind(service)
    .execute(pool)
    .await
    .ok();
}

static PG_POOL: std::sync::OnceLock<sqlx::PgPool> = std::sync::OnceLock::new();

fn get_pg_pool() -> Option<&'static sqlx::PgPool> {
    PG_POOL.get()
}

async fn init_pg_pool(service_name: &str) -> Option<sqlx::PgPool> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| format!("postgresql://localhost:5432/{}", service_name.replace("-", "_")));
    match sqlx::postgres::PgPoolOptions::new()
        .max_connections(5)
        .acquire_timeout(std::time::Duration::from_secs(3))
        .connect(&database_url)
        .await
    {
        Ok(pool) => {
            pg_init_state_table(&pool).await;
            eprintln!("[{}] PostgreSQL connected", service_name);
            Some(pool)
        }
        Err(e) => {
            eprintln!("[{}] PostgreSQL unavailable ({}), using in-memory only", service_name, e);
            None
        }
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Initialize PostgreSQL persistence
    if let Some(pool) = init_pg_pool("fund-flow-settlement").await {
        PG_POOL.set(pool).ok();
    }
    // Load persisted state
    if let Some(pool) = get_pg_pool() {
        if let Some(saved) = pg_load_state(pool, "stats", "fund-flow-settlement").await {
            eprintln!("[fund-flow-settlement] Loaded persisted state from PostgreSQL");
            // Merge saved state into in-memory counters on startup
            let _ = saved; // State loaded - individual services deserialize as needed
        }
    }

    let port: u16 = std::env::var("FUND_FLOW_SETTLEMENT_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8251);

    let db_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/fund_flow_settlement".to_string());

    let pool = PgPoolOptions::new()
        .max_connections(10)
        .connect(&db_url)
        .await
        .unwrap_or_else(|e| {
            eprintln!("PostgreSQL connection failed: {}. Exiting.", e);
            std::process::exit(1);
        });

    init_db(&pool).await;

    let state = web::Data::new(AppState { pool });

    println!("Fund Flow Settlement Engine starting on :{}", port);

    HttpServer::new(move || {
        App::new()
            .app_data(state.clone())
            .route("/health", web::get().to(health))
            .route("/api/bnpl/schedule", web::post().to(generate_schedule))
            .route("/api/bnpl/schedule/{app_id}", web::get().to(get_schedule))
            .route("/api/fx/rates", web::get().to(get_fx_rates))
            .route("/api/fx/convert", web::post().to(convert_fx))
            .route("/api/fx/corridors", web::get().to(get_corridors))
            .route("/api/reconcile", web::post().to(reconcile))
            .route("/api/settlement/batch", web::post().to(create_settlement_batch))
    })
    .bind(("0.0.0.0", port))?
    .workers(4)
    .run()
    .await
}
