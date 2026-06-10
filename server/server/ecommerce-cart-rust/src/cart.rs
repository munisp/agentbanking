use actix_web::{web, HttpResponse};
use chrono::{Duration, Utc};
use dashmap::DashMap;

use crate::models::{AddItemRequest, Cart, CartItem, CouponRequest, UpdateItemRequest};

/// High-performance concurrent cart store using DashMap (lock-free reads)
pub struct CartStore {
    pub carts: DashMap<i64, Cart>,
}

impl CartStore {
    pub fn new() -> Self {
        CartStore {
            carts: DashMap::new(),
        }
    }

    fn get_or_create(&self, customer_id: i64) -> Cart {
        self.carts
            .entry(customer_id)
            .or_insert_with(|| Cart {
                customer_id,
                items: Vec::new(),
                coupon_code: None,
                discount_amount: 0.0,
                sub_total: 0.0,
                item_count: 0,
                currency: "NGN".to_string(),
                created_at: Utc::now(),
                updated_at: Utc::now(),
                expires_at: Utc::now() + Duration::hours(24),
            })
            .clone()
    }

    fn recalculate(cart: &mut Cart) {
        let mut sub_total = 0.0;
        let mut item_count = 0u32;
        for item in &cart.items {
            sub_total += item.unit_price * item.quantity as f64;
            item_count += item.quantity;
        }
        cart.sub_total = sub_total - cart.discount_amount;
        cart.item_count = item_count;
        cart.updated_at = Utc::now();
    }
}

pub async fn get_cart(
    store: web::Data<CartStore>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let cart = store.get_or_create(customer_id);
    HttpResponse::Ok().json(cart)
}

pub async fn add_item(
    store: web::Data<CartStore>,
    path: web::Path<i64>,
    body: web::Json<AddItemRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    let mut cart = store.carts.entry(customer_id).or_insert_with(|| Cart {
        customer_id,
        items: Vec::new(),
        coupon_code: None,
        discount_amount: 0.0,
        sub_total: 0.0,
        item_count: 0,
        currency: req.currency.clone().unwrap_or_else(|| "NGN".to_string()),
        created_at: Utc::now(),
        updated_at: Utc::now(),
        expires_at: Utc::now() + Duration::hours(24),
    });

    // Check if item already exists, update quantity
    if let Some(existing) = cart.items.iter_mut().find(|i| i.sku == req.sku) {
        existing.quantity += req.quantity;
    } else {
        cart.items.push(CartItem {
            sku: req.sku,
            product_id: req.product_id,
            name: req.name,
            quantity: req.quantity,
            unit_price: req.unit_price,
            currency: req.currency.unwrap_or_else(|| "NGN".to_string()),
            image_url: req.image_url,
            merchant_id: req.merchant_id,
            added_at: Utc::now(),
        });
    }

    CartStore::recalculate(&mut cart);
    let result = cart.clone();
    HttpResponse::Ok().json(result)
}

pub async fn update_item(
    store: web::Data<CartStore>,
    path: web::Path<i64>,
    body: web::Json<UpdateItemRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    if let Some(mut cart) = store.carts.get_mut(&customer_id) {
        if let Some(item) = cart.items.iter_mut().find(|i| i.sku == req.sku) {
            if req.quantity == 0 {
                cart.items.retain(|i| i.sku != req.sku);
            } else {
                item.quantity = req.quantity;
            }
            CartStore::recalculate(&mut cart);
            return HttpResponse::Ok().json(cart.clone());
        }
        return HttpResponse::NotFound().json(serde_json::json!({"error": "Item not in cart"}));
    }
    HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"}))
}

pub async fn remove_item(
    store: web::Data<CartStore>,
    path: web::Path<(i64, String)>,
) -> HttpResponse {
    let (customer_id, sku) = path.into_inner();

    if let Some(mut cart) = store.carts.get_mut(&customer_id) {
        cart.items.retain(|i| i.sku != sku);
        CartStore::recalculate(&mut cart);
        return HttpResponse::Ok().json(cart.clone());
    }
    HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"}))
}

pub async fn clear_cart(
    store: web::Data<CartStore>,
    path: web::Path<i64>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    store.carts.remove(&customer_id);
    HttpResponse::Ok().json(serde_json::json!({"status": "cleared"}))
}

pub async fn apply_coupon(
    store: web::Data<CartStore>,
    path: web::Path<i64>,
    body: web::Json<CouponRequest>,
) -> HttpResponse {
    let customer_id = path.into_inner();
    let req = body.into_inner();

    if let Some(mut cart) = store.carts.get_mut(&customer_id) {
        // Coupon validation would call external service
        // For now: 10% discount for valid codes
        let discount = cart.sub_total * 0.10;
        cart.coupon_code = Some(req.code);
        cart.discount_amount = discount;
        CartStore::recalculate(&mut cart);
        return HttpResponse::Ok().json(serde_json::json!({
            "status": "applied",
            "discount": discount,
            "cart": cart.clone()
        }));
    }
    HttpResponse::NotFound().json(serde_json::json!({"error": "Cart not found"}))
}
