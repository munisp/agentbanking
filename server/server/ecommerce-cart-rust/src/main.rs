use actix_cors::Cors;
use actix_web::{web, App, HttpServer, HttpResponse, middleware};
use std::env;

mod models;
mod cart;
mod checkout;
mod offline;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));

    let port: u16 = env::var("CART_PORT")
        .unwrap_or_else(|_| "8102".to_string())
        .parse()
        .unwrap_or(8102);

    let cart_store = web::Data::new(cart::CartStore::new());
    let checkout_engine = web::Data::new(checkout::CheckoutEngine::new());

    log::info!("[ecommerce-cart-rust] Starting on port {}", port);

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
            .app_data(cart_store.clone())
            .app_data(checkout_engine.clone())
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
            // Offline cart sync
            .route("/api/v1/cart/sync", web::post().to(offline::sync_carts))
            .route("/api/v1/cart/merge", web::post().to(offline::merge_carts))
    })
    .bind(("0.0.0.0", port))?
    .workers(num_cpus())
    .run()
    .await
}

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "ecommerce-cart-rust",
        "version": "1.0.0"
    }))
}

fn num_cpus() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4)
}
