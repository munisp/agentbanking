use actix_cors::Cors;
use actix_web::{web, App, HttpServer, HttpResponse, middleware};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::env;
use std::sync::Arc;

mod models;
mod cart;
mod checkout;
mod offline;

pub struct AppState {
    pub pool: PgPool,
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));

    let port: u16 = env::var("CART_PORT")
        .unwrap_or_else(|_| "8102".to_string())
        .parse()
        .unwrap_or(8102);

    let database_url = env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/agentbanking".to_string());

    let pool = PgPoolOptions::new()
        .max_connections(20)
        .connect(&database_url)
        .await
        .expect("Failed to connect to PostgreSQL");

    init_tables(&pool).await;

    let state = web::Data::new(AppState { pool });

    log::info!("[ecommerce-cart-rust] Starting on port {} with PostgreSQL persistence", port);

    HttpServer::new(move || {
        let cors = Cors::default()
            .allow_any_origin()
            .allow_any_method()
            .allow_any_header()
            .max_age(86400);

        App::new()
            .wrap(cors)
            .wrap(middleware::Logger::default())
            .wrap(middleware::Compress::default())
            .app_data(state.clone())
            // Health
            .route("/health", web::get().to(health))
            // Cart operations
            .route("/api/v1/cart/{customer_id}", web::get().to(cart::get_cart))
            .route("/api/v1/cart/{customer_id}/add", web::post().to(cart::add_item))
            .route("/api/v1/cart/{customer_id}/update", web::put().to(cart::update_item))
            .route("/api/v1/cart/{customer_id}/remove/{sku}", web::delete().to(cart::remove_item))
            .route("/api/v1/cart/{customer_id}/clear", web::delete().to(cart::clear_cart))
            .route("/api/v1/cart/{customer_id}/apply-coupon", web::post().to(cart::apply_coupon))
            // Checkout
            .route("/api/v1/checkout/{customer_id}/initiate", web::post().to(checkout::initiate))
            .route("/api/v1/checkout/{customer_id}/calculate", web::get().to(checkout::calculate_totals))
            .route("/api/v1/checkout/{customer_id}/confirm", web::post().to(checkout::confirm))
            .route("/api/v1/checkout/session/{session_id}", web::get().to(checkout::get_session))
            // Abandoned cart
            .route("/api/v1/carts/abandoned", web::get().to(cart::list_abandoned))
            .route("/api/v1/carts/cleanup-expired", web::post().to(cart::cleanup_expired))
            // Offline cart sync
            .route("/api/v1/cart/sync", web::post().to(offline::sync_carts))
            .route("/api/v1/cart/merge", web::post().to(offline::merge_carts))
            // Metrics
            .route("/metrics", web::get().to(metrics))
    })
    .bind(("0.0.0.0", port))?
    .workers(num_cpus())
    .run()
    .await
}

async fn init_tables(pool: &PgPool) {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS ecom_carts (
            customer_id BIGINT PRIMARY KEY,
            coupon_code TEXT,
            discount_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            sub_total DOUBLE PRECISION NOT NULL DEFAULT 0,
            item_count INT NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'NGN',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
        )"
    ).execute(pool).await.ok();

    sqlx::query(
        "CREATE TABLE IF NOT EXISTS ecom_cart_items (
            id SERIAL PRIMARY KEY,
            customer_id BIGINT NOT NULL REFERENCES ecom_carts(customer_id) ON DELETE CASCADE,
            sku TEXT NOT NULL,
            product_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            quantity INT NOT NULL DEFAULT 1,
            unit_price DOUBLE PRECISION NOT NULL,
            currency TEXT NOT NULL DEFAULT 'NGN',
            image_url TEXT,
            merchant_id BIGINT NOT NULL,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(customer_id, sku)
        )"
    ).execute(pool).await.ok();

    sqlx::query(
        "CREATE TABLE IF NOT EXISTS ecom_checkout_sessions (
            session_id TEXT PRIMARY KEY,
            customer_id BIGINT NOT NULL,
            cart_snapshot JSONB NOT NULL,
            shipping_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
            tax DOUBLE PRECISION NOT NULL DEFAULT 0,
            total DOUBLE PRECISION NOT NULL DEFAULT 0,
            payment_method TEXT,
            shipping_address JSONB,
            status TEXT NOT NULL DEFAULT 'initiated',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 minutes'
        )"
    ).execute(pool).await.ok();

    sqlx::query("CREATE INDEX IF NOT EXISTS idx_ecom_ci_cust ON ecom_cart_items(customer_id)")
        .execute(pool).await.ok();
    sqlx::query("CREATE INDEX IF NOT EXISTS idx_ecom_cs_cust ON ecom_checkout_sessions(customer_id)")
        .execute(pool).await.ok();
    sqlx::query("CREATE INDEX IF NOT EXISTS idx_ecom_carts_exp ON ecom_carts(expires_at)")
        .execute(pool).await.ok();

    log::info!("[ecommerce-cart-rust] PostgreSQL tables initialized");
}

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "ecommerce-cart-rust",
        "version": "2.0.0",
        "persistence": "postgresql"
    }))
}

async fn metrics(state: web::Data<AppState>) -> HttpResponse {
    let cart_count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM ecom_carts")
        .fetch_one(&state.pool).await.unwrap_or((0,));
    let session_count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM ecom_checkout_sessions WHERE status='initiated'")
        .fetch_one(&state.pool).await.unwrap_or((0,));
    let abandoned: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM ecom_carts WHERE expires_at < NOW()")
        .fetch_one(&state.pool).await.unwrap_or((0,));

    HttpResponse::Ok().json(serde_json::json!({
        "active_carts": cart_count.0,
        "active_sessions": session_count.0,
        "abandoned_carts": abandoned.0,
        "persistence": "postgresql"
    }))
}

fn num_cpus() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4)
}
