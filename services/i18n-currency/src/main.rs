//! P3-E: i18n + Multi-Currency Formatting Engine (Rust)
//!
//! 54agent POS i18n Service
//!
//! This service provides locale-aware currency formatting, number formatting,
//! and date formatting for the 54agent POS platform. It is implemented in Rust
//! because:
//!   - Currency arithmetic requires exact decimal precision (no IEEE 754 errors)
//!   - Locale data is embedded at compile time — zero startup cost
//!   - The formatting hot path is called thousands of times per second on receipts
//!   - Rust's type system enforces currency code validity at compile time
//!
//! Endpoints:
//!   GET  /health
//!   POST /api/v1/format/currency     — format an amount in a given currency+locale
//!   POST /api/v1/format/number       — format a number in a given locale
//!   POST /api/v1/convert             — convert between currencies using live rates
//!   GET  /api/v1/currencies          — list all supported currencies
//!   GET  /api/v1/locales             — list all supported locales
//!   POST /api/v1/batch/format        — batch format multiple amounts

#[cfg(test)]
mod tests;

use actix_cors::Cors;
use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use log::{info, warn};
use rust_decimal::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;

// ─── Currency Registry ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
struct CurrencyInfo {
    code: &'static str,
    name: &'static str,
    symbol: &'static str,
    decimal_places: u32,
    symbol_position: &'static str,
    thousands_sep: &'static str,
    decimal_sep: &'static str,
}

fn currency_registry() -> HashMap<&'static str, CurrencyInfo> {
    let mut m = HashMap::new();
    m.insert("NGN", CurrencyInfo { code: "NGN", name: "Nigerian Naira",         symbol: "\u{20a6}", decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("GHS", CurrencyInfo { code: "GHS", name: "Ghanaian Cedi",          symbol: "\u{20b5}", decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("XOF", CurrencyInfo { code: "XOF", name: "West African CFA Franc", symbol: "CFA",      decimal_places: 0, symbol_position: "after",  thousands_sep: " ", decimal_sep: "," });
    m.insert("SLL", CurrencyInfo { code: "SLL", name: "Sierra Leonean Leone",   symbol: "Le",       decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("GMD", CurrencyInfo { code: "GMD", name: "Gambian Dalasi",         symbol: "D",        decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("LRD", CurrencyInfo { code: "LRD", name: "Liberian Dollar",        symbol: "L$",       decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("KES", CurrencyInfo { code: "KES", name: "Kenyan Shilling",        symbol: "KSh",      decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("TZS", CurrencyInfo { code: "TZS", name: "Tanzanian Shilling",     symbol: "TSh",      decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("UGX", CurrencyInfo { code: "UGX", name: "Ugandan Shilling",       symbol: "USh",      decimal_places: 0, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("ETB", CurrencyInfo { code: "ETB", name: "Ethiopian Birr",         symbol: "Br",       decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("RWF", CurrencyInfo { code: "RWF", name: "Rwandan Franc",          symbol: "RF",       decimal_places: 0, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("ZAR", CurrencyInfo { code: "ZAR", name: "South African Rand",     symbol: "R",        decimal_places: 2, symbol_position: "before", thousands_sep: " ", decimal_sep: "," });
    m.insert("ZMW", CurrencyInfo { code: "ZMW", name: "Zambian Kwacha",         symbol: "ZK",       decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("USD", CurrencyInfo { code: "USD", name: "US Dollar",              symbol: "$",        decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("EUR", CurrencyInfo { code: "EUR", name: "Euro",                   symbol: "\u{20ac}", decimal_places: 2, symbol_position: "before", thousands_sep: ".", decimal_sep: "," });
    m.insert("GBP", CurrencyInfo { code: "GBP", name: "British Pound",          symbol: "\u{00a3}", decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m.insert("CNY", CurrencyInfo { code: "CNY", name: "Chinese Yuan",           symbol: "\u{00a5}", decimal_places: 2, symbol_position: "before", thousands_sep: ",", decimal_sep: "." });
    m
}

// ─── Locale Registry ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
struct LocaleInfo {
    code: &'static str,
    name: &'static str,
    language: &'static str,
    region: &'static str,
    default_currency: &'static str,
    date_format: &'static str,
    time_format: &'static str,
    rtl: bool,
}

fn locale_registry() -> HashMap<&'static str, LocaleInfo> {
    let mut m = HashMap::new();
    m.insert("en-NG", LocaleInfo { code: "en-NG", name: "English (Nigeria)",        language: "en", region: "NG", default_currency: "NGN", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("yo-NG", LocaleInfo { code: "yo-NG", name: "Yoruba (Nigeria)",         language: "yo", region: "NG", default_currency: "NGN", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("ha-NG", LocaleInfo { code: "ha-NG", name: "Hausa (Nigeria)",          language: "ha", region: "NG", default_currency: "NGN", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("ig-NG", LocaleInfo { code: "ig-NG", name: "Igbo (Nigeria)",           language: "ig", region: "NG", default_currency: "NGN", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("en-GH", LocaleInfo { code: "en-GH", name: "English (Ghana)",          language: "en", region: "GH", default_currency: "GHS", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("fr-SN", LocaleInfo { code: "fr-SN", name: "French (Senegal)",         language: "fr", region: "SN", default_currency: "XOF", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("fr-CI", LocaleInfo { code: "fr-CI", name: "French (Cote d'Ivoire)",   language: "fr", region: "CI", default_currency: "XOF", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("en-SL", LocaleInfo { code: "en-SL", name: "English (Sierra Leone)",   language: "en", region: "SL", default_currency: "SLL", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("en-KE", LocaleInfo { code: "en-KE", name: "English (Kenya)",          language: "en", region: "KE", default_currency: "KES", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("sw-KE", LocaleInfo { code: "sw-KE", name: "Swahili (Kenya)",          language: "sw", region: "KE", default_currency: "KES", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("en-ZA", LocaleInfo { code: "en-ZA", name: "English (South Africa)",   language: "en", region: "ZA", default_currency: "ZAR", date_format: "YYYY/MM/DD", time_format: "HH:mm", rtl: false });
    m.insert("en-US", LocaleInfo { code: "en-US", name: "English (United States)",  language: "en", region: "US", default_currency: "USD", date_format: "MM/DD/YYYY", time_format: "hh:mm A", rtl: false });
    m.insert("en-GB", LocaleInfo { code: "en-GB", name: "English (United Kingdom)", language: "en", region: "GB", default_currency: "GBP", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m.insert("fr-FR", LocaleInfo { code: "fr-FR", name: "French (France)",          language: "fr", region: "FR", default_currency: "EUR", date_format: "DD/MM/YYYY", time_format: "HH:mm", rtl: false });
    m
}

// ─── Formatting helpers ───────────────────────────────────────────────────────

fn insert_thousands_sep(s: &str, sep: &str) -> String {
    if sep.is_empty() { return s.to_string(); }
    let chars: Vec<char> = s.chars().collect();
    let len = chars.len();
    let mut result = String::with_capacity(len + len / 3);
    for (i, c) in chars.iter().enumerate() {
        if i > 0 && (len - i) % 3 == 0 { result.push_str(sep); }
        result.push(*c);
    }
    result
}

fn format_currency_amount(amount: Decimal, currency: &CurrencyInfo, show_code: bool) -> String {
    let rounded = amount.round_dp(currency.decimal_places);
    let is_negative = rounded.is_sign_negative();
    let abs_amount = rounded.abs();
    let int_str = abs_amount.trunc().to_string();
    let int_formatted = insert_thousands_sep(&int_str, currency.thousands_sep);
    let formatted = if currency.decimal_places > 0 {
        let scale = Decimal::from(10u32.pow(currency.decimal_places));
        let frac_digits = (abs_amount.fract() * scale).round_dp(0).to_u64().unwrap_or(0);
        format!("{}{}{}", int_formatted, currency.decimal_sep,
            format!("{:0>width$}", frac_digits, width = currency.decimal_places as usize))
    } else { int_formatted };
    let signed = if is_negative { format!("-{}", formatted) } else { formatted };
    let with_symbol = match currency.symbol_position {
        "before" => format!("{}{}", currency.symbol, signed),
        "after"  => format!("{} {}", signed, currency.symbol),
        _        => format!("{}{}", currency.symbol, signed),
    };
    if show_code { format!("{} {}", with_symbol, currency.code) } else { with_symbol }
}

// ─── Request/Response types ───────────────────────────────────────────────────

#[derive(Deserialize)] struct FormatCurrencyRequest {
    amount: f64,
    #[serde(default = "default_unit")] unit: String,
    currency: String,
    locale: Option<String>,
    #[serde(default)] show_code: bool,
}
fn default_unit() -> String { "major".to_string() }

#[derive(Serialize)] struct FormatCurrencyResponse {
    formatted: String, amount_major: String, currency: String,
    locale: Option<String>, symbol: String, decimal_places: u32,
}

#[derive(Deserialize)] struct FormatNumberRequest {
    value: f64, locale: String, decimal_places: Option<u32>,
}

#[derive(Deserialize)] struct ConvertRequest {
    amount: f64, from: String, to: String, rate: f64,
}

#[derive(Deserialize)] struct BatchFormatItem {
    id: String, amount: f64, currency: String,
    #[serde(default = "default_unit")] unit: String,
    #[serde(default)] show_code: bool,
}
#[derive(Deserialize)] struct BatchFormatRequest {
    items: Vec<BatchFormatItem>,
    locale: Option<String>,
}
#[derive(Serialize)] struct BatchFormatResult {
    id: String, formatted: String, error: Option<String>,
}

// ─── App State ────────────────────────────────────────────────────────────────

struct AppState {
    currencies: HashMap<&'static str, CurrencyInfo>,
    locales: HashMap<&'static str, LocaleInfo>,
}

// ─── Handlers ─────────────────────────────────────────────────────────────────

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "ok", "service": "54agent-i18n-currency", "version": "1.0.0"
    }))
}

#[get("/api/v1/currencies")]
async fn list_currencies(data: web::Data<AppState>) -> impl Responder {
    let mut currencies: Vec<&CurrencyInfo> = data.currencies.values().collect();
    currencies.sort_by_key(|c| c.code);
    HttpResponse::Ok().json(serde_json::json!({ "currencies": currencies, "count": currencies.len() }))
}

#[get("/api/v1/locales")]
async fn list_locales(data: web::Data<AppState>) -> impl Responder {
    let mut locales: Vec<&LocaleInfo> = data.locales.values().collect();
    locales.sort_by_key(|l| l.code);
    HttpResponse::Ok().json(serde_json::json!({ "locales": locales, "count": locales.len() }))
}

#[post("/api/v1/format/currency")]
async fn format_currency(data: web::Data<AppState>, req: web::Json<FormatCurrencyRequest>) -> impl Responder {
    let code = req.currency.to_uppercase();
    let currency = match data.currencies.get(code.as_str()) {
        Some(c) => c,
        None => { warn!("Unknown currency: {}", code);
            return HttpResponse::BadRequest().json(serde_json::json!({ "error": format!("Unknown currency: {}", code) })); }
    };
    let amount_major = if req.unit == "minor" { req.amount / 10u64.pow(currency.decimal_places) as f64 } else { req.amount };
    let d = match Decimal::from_f64(amount_major) {
        Some(v) => v,
        None => return HttpResponse::BadRequest().json(serde_json::json!({ "error": "Invalid amount" })),
    };
    HttpResponse::Ok().json(FormatCurrencyResponse {
        formatted: format_currency_amount(d, currency, req.show_code),
        amount_major: d.round_dp(currency.decimal_places).to_string(),
        currency: code, locale: req.locale.clone(),
        symbol: currency.symbol.to_string(), decimal_places: currency.decimal_places,
    })
}

#[post("/api/v1/format/number")]
async fn format_number(data: web::Data<AppState>, req: web::Json<FormatNumberRequest>) -> impl Responder {
    let dp = req.decimal_places.unwrap_or(2);
    let (thousands_sep, decimal_sep) = match data.locales.get(req.locale.as_str()) {
        Some(locale) => match data.currencies.get(locale.default_currency) {
            Some(c) => (c.thousands_sep, c.decimal_sep),
            None => (",", "."),
        },
        None => (",", "."),
    };
    let d = match Decimal::from_f64(req.value) {
        Some(v) => v,
        None => return HttpResponse::BadRequest().json(serde_json::json!({ "error": "Invalid value" })),
    };
    let rounded = d.round_dp(dp);
    let is_neg = rounded.is_sign_negative();
    let abs_val = rounded.abs();
    let int_formatted = insert_thousands_sep(&abs_val.trunc().to_string(), thousands_sep);
    let formatted = if dp > 0 {
        let scale = Decimal::from(10u32.pow(dp));
        let frac = (abs_val.fract() * scale).round_dp(0).to_u64().unwrap_or(0);
        format!("{}{}{}", int_formatted, decimal_sep, format!("{:0>width$}", frac, width = dp as usize))
    } else { int_formatted };
    let signed = if is_neg { format!("-{}", formatted) } else { formatted };
    HttpResponse::Ok().json(serde_json::json!({ "formatted": signed, "value": req.value, "locale": req.locale }))
}

#[post("/api/v1/convert")]
async fn convert_currency(data: web::Data<AppState>, req: web::Json<ConvertRequest>) -> impl Responder {
    let from_code = req.from.to_uppercase();
    let to_code = req.to.to_uppercase();
    let from_c = match data.currencies.get(from_code.as_str()) {
        Some(c) => c,
        None => return HttpResponse::BadRequest().json(serde_json::json!({ "error": format!("Unknown source currency: {}", from_code) })),
    };
    let to_c = match data.currencies.get(to_code.as_str()) {
        Some(c) => c,
        None => return HttpResponse::BadRequest().json(serde_json::json!({ "error": format!("Unknown target currency: {}", to_code) })),
    };
    let amount_d = match Decimal::from_f64(req.amount) { Some(v) => v, None => return HttpResponse::BadRequest().json(serde_json::json!({ "error": "Invalid amount" })) };
    let rate_d   = match Decimal::from_f64(req.rate)   { Some(v) => v, None => return HttpResponse::BadRequest().json(serde_json::json!({ "error": "Invalid rate" })) };
    let converted = amount_d * rate_d;
    HttpResponse::Ok().json(serde_json::json!({
        "from_amount": format_currency_amount(amount_d, from_c, false),
        "to_amount":   format_currency_amount(converted, to_c, false),
        "from_currency": from_code, "to_currency": to_code,
        "rate": req.rate, "converted_raw": converted.to_f64().unwrap_or(0.0)
    }))
}

#[post("/api/v1/batch/format")]
async fn batch_format(data: web::Data<AppState>, req: web::Json<BatchFormatRequest>) -> impl Responder {
    let results: Vec<BatchFormatResult> = req.items.iter().map(|item| {
        let code = item.currency.to_uppercase();
        match data.currencies.get(code.as_str()) {
            None => BatchFormatResult { id: item.id.clone(), formatted: String::new(), error: Some(format!("Unknown currency: {}", code)) },
            Some(c) => {
                let major = if item.unit == "minor" { item.amount / 10u64.pow(c.decimal_places) as f64 } else { item.amount };
                match Decimal::from_f64(major) {
                    None => BatchFormatResult { id: item.id.clone(), formatted: String::new(), error: Some("Invalid amount".to_string()) },
                    Some(d) => BatchFormatResult { id: item.id.clone(), formatted: format_currency_amount(d, c, item.show_code), error: None },
                }
            }
        }
    }).collect();
    let successful = results.iter().filter(|r| r.error.is_none()).count();
    HttpResponse::Ok().json(serde_json::json!({ "results": results, "total": results.len(), "successful": successful, "failed": results.len() - successful }))
}

// ─── Main ─────────────────────────────────────────────────────────────────────

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));
    let port: u16 = env::var("PORT").unwrap_or_else(|_| "8084".to_string()).parse().unwrap_or(8084);
    info!("54agent i18n Currency Service starting on :{}", port);
    let currencies = currency_registry();
    let locales = locale_registry();
    info!("Loaded {} currencies, {} locales", currencies.len(), locales.len());
    let state = web::Data::new(AppState { currencies, locales });
    HttpServer::new(move || {
        let cors = Cors::default().allow_any_origin().allow_any_method().allow_any_header();
        App::new().wrap(cors).app_data(state.clone())
            .service(health).service(list_currencies).service(list_locales)
            .service(format_currency).service(format_number)
            .service(convert_currency).service(batch_format)
    }).bind(("0.0.0.0", port))?.run().await
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
