//! Fund Flow Settlement Engine (Rust)
//!
//! High-performance microservice for:
//! - BNPL installment schedule generation and tracking
//! - FX rate engine with spread calculation and corridor management
//! - GL reconciliation and discrepancy detection
//! - Settlement batch processing
//!
//! Designed for sub-millisecond latency on hot paths.

use actix_web::{web, App, HttpServer, HttpResponse, middleware};
use chrono::{Utc, NaiveDate, Duration as ChronoDuration};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::RwLock;
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

// ── Application State ───────────────────────────────────────────────────────

pub struct AppState {
    pool: PgPool,
}

impl AppState {
    fn new() -> Self {
        let mut rates = HashMap::new();
        let corridors = vec![
            ("NGN", "USD", 0.00065, 50u32),
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
            rates.insert(key, FXRate {
                from: from.to_string(),
                to: to.to_string(),
                rate,
                spread_bps: spread,
                effective_rate: effective,
                updated_at: Utc::now().to_rfc3339(),
            });
        }

        AppState {
            fx_rates: RwLock::new(rates),
            schedules: RwLock::new(HashMap::new()),
        }
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

    // Amortization calculation
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

    let mut schedules = data.schedules.write().unwrap();
    schedules.insert(req.application_id, schedule.clone());

    HttpResponse::Ok().json(schedule)
}

async fn get_schedule(
    data: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let app_id = path.into_inner();
    let schedules = data.schedules.read().unwrap();
    match schedules.get(&app_id) {
        Some(s) => HttpResponse::Ok().json(s),
        None => HttpResponse::NotFound().json(serde_json::json!({
            "error": "Schedule not found"
        })),
    }
}

// ── FX Rate Handlers ────────────────────────────────────────────────────────

async fn get_fx_rates(data: web::Data<AppState>) -> HttpResponse {
    let rates = data.fx_rates.read().unwrap();
    let rate_list: Vec<&FXRate> = rates.values().collect();
    HttpResponse::Ok().json(serde_json::json!({
        "rates": rate_list,
        "count": rate_list.len(),
        "timestamp": Utc::now().to_rfc3339(),
    }))
}

async fn convert_fx(
    data: web::Data<AppState>,
    req: web::Json<FXConvertRequest>,
) -> HttpResponse {
    let key = format!("{}-{}", req.from_currency, req.to_currency);
    let rates = data.fx_rates.read().unwrap();

    match rates.get(&key) {
        Some(rate_info) => {
            let output = (req.amount * rate_info.effective_rate * 100.0).round() / 100.0;
            let fee = (req.amount * 0.01 * 100.0).round() / 100.0;

            HttpResponse::Ok().json(FXConvertResponse {
                from_currency: req.from_currency.clone(),
                to_currency: req.to_currency.clone(),
                input_amount: req.amount,
                output_amount: output,
                rate: rate_info.rate,
                effective_rate: rate_info.effective_rate,
                spread_bps: rate_info.spread_bps,
                fee,
                timestamp: Utc::now().to_rfc3339(),
            })
        }
        None => HttpResponse::BadRequest().json(serde_json::json!({
            "error": format!("Unsupported corridor: {}", key)
        })),
    }
}

async fn get_corridors(data: web::Data<AppState>) -> HttpResponse {
    let rates = data.fx_rates.read().unwrap();
    let corridors: Vec<String> = rates.keys().cloned().collect();
    HttpResponse::Ok().json(serde_json::json!({
        "corridors": corridors,
        "count": corridors.len(),
    }))
}

// ── Reconciliation Handlers ─────────────────────────────────────────────────

async fn reconcile(req: web::Json<ReconcileRequest>) -> HttpResponse {
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

async fn create_settlement_batch() -> HttpResponse {
    let batch = SettlementBatch {
        batch_id: format!("BATCH-{}", Uuid::new_v4().to_string()[..8].to_uppercase()),
        total_settlements: 0,
        total_amount: 0.0,
        status: "initiated".to_string(),
        created_at: Utc::now().to_rfc3339(),
    };
    HttpResponse::Ok().json(batch)
}

// ── Health ───────────────────────────────────────────────────────────────────

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "fund-flow-settlement",
        "version": "1.0.0",
        "timestamp": Utc::now().to_rfc3339(),
    }))
}

// ── Main ────────────────────────────────────────────────────────────────────

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let port: u16 = std::env::var("FUND_FLOW_SETTLEMENT_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8251);

    let state = web::Data::new(AppState::new());

    println!("Fund Flow Settlement Engine starting on :{}", port);

    HttpServer::new(move || {
        App::new()
            .app_data(state.clone())
            .route("/health", web::get().to(health))
            // BNPL installment scheduling
            .route("/api/bnpl/schedule", web::post().to(generate_schedule))
            .route("/api/bnpl/schedule/{app_id}", web::get().to(get_schedule))
            // FX rate engine
            .route("/api/fx/rates", web::get().to(get_fx_rates))
            .route("/api/fx/convert", web::post().to(convert_fx))
            .route("/api/fx/corridors", web::get().to(get_corridors))
            // Reconciliation
            .route("/api/reconcile", web::post().to(reconcile))
            .route("/api/settlement/batch", web::post().to(create_settlement_batch))
    })
    .bind(("0.0.0.0", port))?
    .workers(4)
    .run()
    .await
}
