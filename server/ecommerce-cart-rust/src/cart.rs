use actix_web::{web, HttpResponse};
use chrono::Utc;
use sqlx::Row;

use crate::AppState;
use crate::models::{AddItemRequest, UpdateItemRequest, CouponRequest};

pub async fn get_cart(
    state: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    match load_cart(&state.pool, customer_id).await {
        Some(cart) => HttpResponse::Ok().json(cart),
        None => HttpResponse::Ok().json(serde_json::json!({
            "customer_id": customer_id,
            "items": [],
            "sub_total": 0.0,
            "item_count": 0,
            "currency": "NGN"
        })),
    }
}

pub async fn add_item(
    state: web::Data<AppState>,
    path: web::Path<i64>,
    body: web::Json<AddItemRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();
    let currency = req.currency.clone().unwrap_or_else(|| "NGN".to_string());

    // Ensure cart exists
    sqlx::query(
        "INSERT INTO ecom_carts (customer_id, currency, expires_at)
         VALUES ($1, $2, NOW() + INTERVAL '24 hours')
         ON CONFLICT (customer_id) DO UPDATE SET updated_at = NOW()"
    )
    .bind(customer_id).bind(&currency)
    .execute(&state.pool).await.ok();

    // Upsert item
    sqlx::query(
        "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         ON CONFLICT (customer_id, sku) DO UPDATE SET quantity = ecom_cart_items.quantity + $5, updated_at = NOW()"
    )
    .bind(customer_id).bind(&req.sku).bind(req.product_id)
    .bind(&req.name).bind(req.quantity as i32).bind(req.unit_price)
    .bind(&currency).bind(&req.image_url).bind(req.merchant_id)
    .execute(&state.pool).await.ok();

    recalculate(&state.pool, customer_id).await;

    match load_cart(&state.pool, customer_id).await {
        Some(cart) => HttpResponse::Ok().json(cart),
        None => HttpResponse::InternalServerError().json(serde_json::json!({"error": "Failed to load cart"})),
    }
}

pub async fn update_item(
    state: web::Data<AppState>,
    path: web::Path<i64>,
    body: web::Json<UpdateItemRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    if req.quantity == 0 {
        sqlx::query("DELETE FROM ecom_cart_items WHERE customer_id = $1 AND sku = $2")
            .bind(customer_id).bind(&req.sku)
            .execute(&state.pool).await.ok();
    } else {
        let result = sqlx::query("UPDATE ecom_cart_items SET quantity = $3 WHERE customer_id = $1 AND sku = $2")
            .bind(customer_id).bind(&req.sku).bind(req.quantity as i32)
            .execute(&state.pool).await;
        if let Ok(r) = result {
            if r.rows_affected() == 0 {
                return HttpResponse::NotFound().json(serde_json::json!({"error": "Item not in cart"}));
            }
        }
    }

    recalculate(&state.pool, customer_id).await;

    match load_cart(&state.pool, customer_id).await {
        Some(cart) => HttpResponse::Ok().json(cart),
        None => HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"})),
    }
}

pub async fn remove_item(
    state: web::Data<AppState>,
    path: web::Path<(i64, String)>,
) -> HttpResponse {
    let (customer_id, sku) = path.into_inner();

    sqlx::query("DELETE FROM ecom_cart_items WHERE customer_id = $1 AND sku = $2")
        .bind(customer_id).bind(&sku)
        .execute(&state.pool).await.ok();

    recalculate(&state.pool, customer_id).await;

    match load_cart(&state.pool, customer_id).await {
        Some(cart) => HttpResponse::Ok().json(cart),
        None => HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"})),
    }
}

pub async fn clear_cart(
    state: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    sqlx::query("DELETE FROM ecom_cart_items WHERE customer_id = $1")
        .bind(customer_id).execute(&state.pool).await.ok();
    sqlx::query("DELETE FROM ecom_carts WHERE customer_id = $1")
        .bind(customer_id).execute(&state.pool).await.ok();
    HttpResponse::Ok().json(serde_json::json!({"status": "cleared"}))
}

pub async fn apply_coupon(
    state: web::Data<AppState>,
    path: web::Path<i64>,
    body: web::Json<CouponRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    let cart_row = sqlx::query("SELECT sub_total FROM ecom_carts WHERE customer_id = $1")
        .bind(customer_id).fetch_optional(&state.pool).await;

    let sub_total: f64 = match cart_row {
        Ok(Some(row)) => row.get("sub_total"),
        _ => return HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"})),
    };

    let discount = sub_total * 0.10;
    sqlx::query("UPDATE ecom_carts SET coupon_code = $2, discount_amount = $3, sub_total = sub_total - $3, updated_at = NOW() WHERE customer_id = $1")
        .bind(customer_id).bind(&req.code).bind(discount)
        .execute(&state.pool).await.ok();

    match load_cart(&state.pool, customer_id).await {
        Some(cart) => HttpResponse::Ok().json(serde_json::json!({
            "status": "applied",
            "discount": discount,
            "cart": cart
        })),
        None => HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"})),
    }
}

pub async fn list_abandoned(state: web::Data<AppState>) -> HttpResponse {
    let rows = sqlx::query(
        "SELECT c.customer_id, c.sub_total, c.item_count, c.currency, c.expires_at, c.updated_at
         FROM ecom_carts c WHERE c.expires_at < NOW() ORDER BY c.updated_at DESC LIMIT 100"
    ).fetch_all(&state.pool).await.unwrap_or_default();

    let carts: Vec<serde_json::Value> = rows.iter().map(|r| {
        serde_json::json!({
            "customer_id": r.get::<i64, _>("customer_id"),
            "sub_total": r.get::<f64, _>("sub_total"),
            "item_count": r.get::<i32, _>("item_count"),
            "currency": r.get::<String, _>("currency"),
            "expired_at": r.get::<chrono::DateTime<Utc>, _>("expires_at").to_rfc3339(),
            "last_activity": r.get::<chrono::DateTime<Utc>, _>("updated_at").to_rfc3339(),
        })
    }).collect();

    HttpResponse::Ok().json(serde_json::json!({
        "abandoned_carts": carts,
        "count": carts.len()
    }))
}

pub async fn cleanup_expired(state: web::Data<AppState>) -> HttpResponse {
    let result = sqlx::query("DELETE FROM ecom_carts WHERE expires_at < NOW() - INTERVAL '7 days'")
        .execute(&state.pool).await;
    let deleted = result.map(|r| r.rows_affected()).unwrap_or(0);

    HttpResponse::Ok().json(serde_json::json!({
        "status": "cleaned",
        "deleted": deleted
    }))
}

async fn load_cart(pool: &sqlx::PgPool, customer_id: i64) -> Option<serde_json::Value> {
    let cart_row = sqlx::query(
        "SELECT customer_id, coupon_code, discount_amount, sub_total, item_count, currency, created_at, updated_at, expires_at
         FROM ecom_carts WHERE customer_id = $1"
    ).bind(customer_id).fetch_optional(pool).await.ok()??;

    let items = sqlx::query(
        "SELECT sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id, added_at
         FROM ecom_cart_items WHERE customer_id = $1 ORDER BY added_at"
    ).bind(customer_id).fetch_all(pool).await.unwrap_or_default();

    let item_list: Vec<serde_json::Value> = items.iter().map(|r| {
        serde_json::json!({
            "sku": r.get::<String, _>("sku"),
            "product_id": r.get::<i64, _>("product_id"),
            "name": r.get::<String, _>("name"),
            "quantity": r.get::<i32, _>("quantity"),
            "unit_price": r.get::<f64, _>("unit_price"),
            "currency": r.get::<String, _>("currency"),
            "image_url": r.get::<Option<String>, _>("image_url"),
            "merchant_id": r.get::<i64, _>("merchant_id"),
            "added_at": r.get::<chrono::DateTime<Utc>, _>("added_at").to_rfc3339(),
        })
    }).collect();

    Some(serde_json::json!({
        "customer_id": cart_row.get::<i64, _>("customer_id"),
        "items": item_list,
        "coupon_code": cart_row.get::<Option<String>, _>("coupon_code"),
        "discount_amount": cart_row.get::<f64, _>("discount_amount"),
        "sub_total": cart_row.get::<f64, _>("sub_total"),
        "item_count": cart_row.get::<i32, _>("item_count"),
        "currency": cart_row.get::<String, _>("currency"),
        "created_at": cart_row.get::<chrono::DateTime<Utc>, _>("created_at").to_rfc3339(),
        "updated_at": cart_row.get::<chrono::DateTime<Utc>, _>("updated_at").to_rfc3339(),
        "expires_at": cart_row.get::<chrono::DateTime<Utc>, _>("expires_at").to_rfc3339(),
    }))
}

async fn recalculate(pool: &sqlx::PgPool, customer_id: i64) {
    sqlx::query(
        "UPDATE ecom_carts SET
            sub_total = COALESCE((SELECT SUM(unit_price * quantity) FROM ecom_cart_items WHERE customer_id = $1), 0) - discount_amount,
            item_count = COALESCE((SELECT SUM(quantity) FROM ecom_cart_items WHERE customer_id = $1), 0),
            updated_at = NOW()
         WHERE customer_id = $1"
    ).bind(customer_id).execute(pool).await.ok();
}
