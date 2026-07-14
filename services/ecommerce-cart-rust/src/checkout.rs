use actix_web::{web, HttpResponse};
use chrono::{Duration, Utc};
use dashmap::DashMap;
use uuid::Uuid;

use crate::cart::CartStore;
use crate::models::{CheckoutConfirmRequest, CheckoutSession, CheckoutStatus};

pub struct CheckoutEngine {
    sessions: DashMap<String, CheckoutSession>,
}

impl CheckoutEngine {
    pub fn new() -> Self {
        CheckoutEngine {
            sessions: DashMap::new(),
        }
    }
}

/// Initiate a checkout session from the current cart
pub async fn initiate(
    cart_store: web::Data<CartStore>,
    checkout: web::Data<CheckoutEngine>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();

    // Get cart — fail if empty
    let cart = match cart_store.carts.get(&customer_id) {
        Some(c) => c.clone(),
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "Cart is empty or not found"}));
        }
    };

    if cart.items.is_empty() {
        return HttpResponse::BadRequest()
            .json(serde_json::json!({"error": "Cannot checkout with empty cart"}));
    }

    let session_id = Uuid::new_v4().to_string();
    let tax = cart.sub_total * 0.075; // 7.5% VAT (Nigeria)
    let shipping_fee = calculate_shipping(&cart);
    let total = cart.sub_total + tax + shipping_fee;

    let session = CheckoutSession {
        session_id: session_id.clone(),
        customer_id,
        cart: cart.clone(),
        shipping_fee,
        tax,
        total,
        payment_method: None,
        shipping_address: None,
        status: CheckoutStatus::Initiated,
        created_at: Utc::now(),
        expires_at: Utc::now() + Duration::minutes(30),
    };

    checkout.sessions.insert(session_id.clone(), session.clone());

    HttpResponse::Ok().json(session)
}

/// Calculate totals without creating a session
pub async fn calculate_totals(
    cart_store: web::Data<CartStore>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();

    let cart = match cart_store.carts.get(&customer_id) {
        Some(c) => c.clone(),
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "Cart not found"}));
        }
    };

    let tax = cart.sub_total * 0.075;
    let shipping_fee = calculate_shipping(&cart);
    let total = cart.sub_total + tax + shipping_fee;

    HttpResponse::Ok().json(serde_json::json!({
        "subTotal": cart.sub_total,
        "tax": tax,
        "taxRate": 0.075,
        "shippingFee": shipping_fee,
        "discount": cart.discount_amount,
        "total": total,
        "currency": cart.currency,
        "itemCount": cart.item_count,
    }))
}

/// Confirm checkout — triggers payment and order creation via Go catalog service
pub async fn confirm(
    cart_store: web::Data<CartStore>,
    checkout: web::Data<CheckoutEngine>,
    path: web::Path<i64>,
    body: web::Json<CheckoutConfirmRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    // Find the active session for this customer
    let session_id = {
        let mut found: Option<String> = None;
        for entry in checkout.sessions.iter() {
            if entry.customer_id == customer_id {
                match entry.status {
                    CheckoutStatus::Initiated | CheckoutStatus::PaymentPending => {
                        found = Some(entry.session_id.clone());
                        break;
                    }
                    _ => {}
                }
            }
        }
        match found {
            Some(id) => id,
            None => {
                return HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": "No active checkout session"}));
            }
        }
    };

    // Update session with payment details
    if let Some(mut session) = checkout.sessions.get_mut(&session_id) {
        session.payment_method = Some(req.payment_method.clone());
        session.shipping_address = Some(req.shipping_address);
        session.status = CheckoutStatus::Confirmed;
    }

    // Clear the cart after successful checkout
    cart_store.carts.remove(&customer_id);

    let session = checkout.sessions.get(&session_id).unwrap().clone();

    HttpResponse::Ok().json(serde_json::json!({
        "status": "confirmed",
        "sessionId": session.session_id,
        "total": session.total,
        "currency": session.cart.currency,
        "paymentMethod": req.payment_method,
        "orderCreationPending": true,
        "message": "Order will be created via catalog service"
    }))
}

/// Get checkout session by ID
pub async fn get_session(
    checkout: web::Data<CheckoutEngine>,
    path: web::Path<String>,
) -> HttpResponse {
    let session_id = path.into_inner();

    match checkout.sessions.get(&session_id) {
        Some(session) => {
            let s = session.clone();
            // Check expiration
            if Utc::now() > s.expires_at {
                return HttpResponse::Gone()
                    .json(serde_json::json!({"error": "Checkout session expired"}));
            }
            HttpResponse::Ok().json(s)
        }
        None => HttpResponse::NotFound()
            .json(serde_json::json!({"error": "Session not found"})),
    }
}

/// Calculate shipping based on cart contents
fn calculate_shipping(cart: &crate::models::Cart) -> f64 {
    let base_fee = 500.0; // ₦500 base shipping
    let per_item = 100.0; // ₦100 per additional item
    let item_count = cart.item_count as f64;

    if item_count == 0.0 {
        return 0.0;
    }

    // Free shipping above ₦50,000
    if cart.sub_total >= 50000.0 {
        return 0.0;
    }

    base_fee + (item_count - 1.0) * per_item
}
