use actix_web::{web, HttpResponse};
use chrono::Utc;
use sqlx::Row;
use uuid::Uuid;

use crate::AppState;
use crate::models::CheckoutConfirmRequest;

pub async fn initiate(
    state: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();

    let cart_row = sqlx::query(
        "SELECT sub_total, item_count, currency, discount_amount FROM ecom_carts WHERE customer_id = $1"
    ).bind(customer_id).fetch_optional(&state.pool).await;

    let cart = match cart_row {
        Ok(Some(r)) => r,
        _ => return HttpResponse::BadRequest().json(serde_json::json!({"error": "Cart is empty or not found"})),
    };

    let item_count: i32 = cart.get("item_count");
    if item_count == 0 {
        return HttpResponse::BadRequest().json(serde_json::json!({"error": "Cannot checkout with empty cart"}));
    }

    let sub_total: f64 = cart.get("sub_total");
    let currency: String = cart.get("currency");
    let tax = sub_total * 0.075;
    let shipping_fee = calculate_shipping(sub_total, item_count);
    let total = sub_total + tax + shipping_fee;
    let session_id = Uuid::new_v4().to_string();

    // Load items for snapshot
    let items = sqlx::query(
        "SELECT sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id
         FROM ecom_cart_items WHERE customer_id = $1"
    ).bind(customer_id).fetch_all(&state.pool).await.unwrap_or_default();

    let item_list: Vec<serde_json::Value> = items.iter().map(|r| {
        serde_json::json!({
            "sku": r.get::<String, _>("sku"),
            "product_id": r.get::<i64, _>("product_id"),
            "name": r.get::<String, _>("name"),
            "quantity": r.get::<i32, _>("quantity"),
            "unit_price": r.get::<f64, _>("unit_price"),
            "merchant_id": r.get::<i64, _>("merchant_id"),
        })
    }).collect();

    let cart_snapshot = serde_json::json!({
        "customer_id": customer_id,
        "items": item_list,
        "sub_total": sub_total,
        "item_count": item_count,
        "currency": currency,
    });

    sqlx::query(
        "INSERT INTO ecom_checkout_sessions (session_id, customer_id, cart_snapshot, shipping_fee, tax, total, status, expires_at)
         VALUES ($1, $2, $3, $4, $5, $6, 'initiated', NOW() + INTERVAL '30 minutes')"
    )
    .bind(&session_id).bind(customer_id).bind(&cart_snapshot)
    .bind(shipping_fee).bind(tax).bind(total)
    .execute(&state.pool).await.ok();

    HttpResponse::Ok().json(serde_json::json!({
        "session_id": session_id,
        "customer_id": customer_id,
        "sub_total": sub_total,
        "tax": tax,
        "shipping_fee": shipping_fee,
        "total": total,
        "currency": currency,
        "status": "initiated",
        "items": item_list,
    }))
}

pub async fn calculate_totals(
    state: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();

    let cart_row = sqlx::query(
        "SELECT sub_total, item_count, discount_amount, currency FROM ecom_carts WHERE customer_id = $1"
    ).bind(customer_id).fetch_optional(&state.pool).await;

    let cart = match cart_row {
        Ok(Some(r)) => r,
        _ => return HttpResponse::BadRequest().json(serde_json::json!({"error": "Cart not found"})),
    };

    let sub_total: f64 = cart.get("sub_total");
    let item_count: i32 = cart.get("item_count");
    let discount: f64 = cart.get("discount_amount");
    let currency: String = cart.get("currency");
    let tax = sub_total * 0.075;
    let shipping_fee = calculate_shipping(sub_total, item_count);
    let total = sub_total + tax + shipping_fee;

    HttpResponse::Ok().json(serde_json::json!({
        "subTotal": sub_total,
        "tax": tax,
        "taxRate": 0.075,
        "shippingFee": shipping_fee,
        "discount": discount,
        "total": total,
        "currency": currency,
        "itemCount": item_count,
    }))
}

pub async fn confirm(
    state: web::Data<AppState>,
    path: web::Path<i64>,
    body: web::Json<CheckoutConfirmRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    let session_row = sqlx::query(
        "SELECT session_id, total, cart_snapshot FROM ecom_checkout_sessions
         WHERE customer_id = $1 AND status = 'initiated' AND expires_at > NOW()
         ORDER BY created_at DESC LIMIT 1"
    ).bind(customer_id).fetch_optional(&state.pool).await;

    let session = match session_row {
        Ok(Some(r)) => r,
        _ => return HttpResponse::BadRequest().json(serde_json::json!({"error": "No active checkout session"})),
    };

    let session_id: String = session.get("session_id");
    let total: f64 = session.get("total");
    let shipping_addr = serde_json::to_value(&req.shipping_address).unwrap_or_default();

    sqlx::query(
        "UPDATE ecom_checkout_sessions SET status = 'confirmed', payment_method = $2, shipping_address = $3
         WHERE session_id = $1"
    )
    .bind(&session_id).bind(&req.payment_method).bind(&shipping_addr)
    .execute(&state.pool).await.ok();

    // Clear cart after checkout
    sqlx::query("DELETE FROM ecom_cart_items WHERE customer_id = $1")
        .bind(customer_id).execute(&state.pool).await.ok();
    sqlx::query("DELETE FROM ecom_carts WHERE customer_id = $1")
        .bind(customer_id).execute(&state.pool).await.ok();

    HttpResponse::Ok().json(serde_json::json!({
        "status": "confirmed",
        "sessionId": session_id,
        "total": total,
        "paymentMethod": req.payment_method,
        "orderCreationPending": true,
    }))
}

pub async fn get_session(
    state: web::Data<AppState>,
    path: web::Path<String>,
) -> HttpResponse {
    let session_id = path.into_inner();

    let row = sqlx::query(
        "SELECT session_id, customer_id, cart_snapshot, shipping_fee, tax, total, payment_method, shipping_address, status, created_at, expires_at
         FROM ecom_checkout_sessions WHERE session_id = $1"
    ).bind(&session_id).fetch_optional(&state.pool).await;

    match row {
        Ok(Some(r)) => {
            let expires_at: chrono::DateTime<Utc> = r.get("expires_at");
            if Utc::now() > expires_at {
                return HttpResponse::Gone().json(serde_json::json!({"error": "Checkout session expired"}));
            }
            HttpResponse::Ok().json(serde_json::json!({
                "session_id": r.get::<String, _>("session_id"),
                "customer_id": r.get::<i64, _>("customer_id"),
                "cart": r.get::<serde_json::Value, _>("cart_snapshot"),
                "shipping_fee": r.get::<f64, _>("shipping_fee"),
                "tax": r.get::<f64, _>("tax"),
                "total": r.get::<f64, _>("total"),
                "payment_method": r.get::<Option<String>, _>("payment_method"),
                "shipping_address": r.get::<Option<serde_json::Value>, _>("shipping_address"),
                "status": r.get::<String, _>("status"),
                "created_at": r.get::<chrono::DateTime<Utc>, _>("created_at").to_rfc3339(),
                "expires_at": expires_at.to_rfc3339(),
            }))
        }
        _ => HttpResponse::NotFound().json(serde_json::json!({"error": "Session not found"})),
    }
}

fn calculate_shipping(sub_total: f64, item_count: i32) -> f64 {
    if item_count == 0 { return 0.0; }
    if sub_total >= 50000.0 { return 0.0; }
    500.0 + (item_count as f64 - 1.0) * 100.0
}
