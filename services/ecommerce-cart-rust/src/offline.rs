use actix_web::{web, HttpResponse};
use chrono::Utc;
use sha2::{Digest, Sha256};

use crate::cart::CartStore;
use crate::models::{Cart, MergeRequest, MergeStrategy, OfflineCart};

/// Sync offline carts back to server when connectivity is restored
pub async fn sync_carts(
    store: web::Data<CartStore>,
    body: web::Json<Vec<OfflineCart>>,
) -> HttpResponse {
    let offline_carts = body.into_inner();
    let mut results = Vec::new();

    for offline in &offline_carts {
        // Verify checksum integrity
        let computed = compute_checksum(&offline.items);
        if computed != offline.checksum {
            results.push(serde_json::json!({
                "clientId": offline.client_id,
                "status": "rejected",
                "reason": "checksum_mismatch",
            }));
            continue;
        }

        // Check if online cart exists
        let has_online = store.carts.contains_key(&offline.customer_id);

        if has_online {
            // Merge with existing online cart (sum quantities)
            if let Some(mut cart) = store.carts.get_mut(&offline.customer_id) {
                for offline_item in &offline.items {
                    if let Some(existing) = cart.items.iter_mut().find(|i| i.sku == offline_item.sku)
                    {
                        existing.quantity = existing.quantity.max(offline_item.quantity);
                    } else {
                        cart.items.push(offline_item.clone());
                    }
                }
                recalculate_cart(&mut cart);
            }
            results.push(serde_json::json!({
                "clientId": offline.client_id,
                "status": "merged",
                "strategy": "max_quantity",
            }));
        } else {
            // Create new cart from offline data
            let mut cart = Cart {
                customer_id: offline.customer_id,
                items: offline.items.clone(),
                coupon_code: None,
                discount_amount: 0.0,
                sub_total: 0.0,
                item_count: 0,
                currency: "NGN".to_string(),
                created_at: offline.created_at,
                updated_at: Utc::now(),
                expires_at: Utc::now() + chrono::Duration::hours(24),
            };
            recalculate_cart(&mut cart);
            store.carts.insert(offline.customer_id, cart);

            results.push(serde_json::json!({
                "clientId": offline.client_id,
                "status": "synced",
            }));
        }
    }

    let synced = results
        .iter()
        .filter(|r| r["status"] == "synced" || r["status"] == "merged")
        .count();

    HttpResponse::Ok().json(serde_json::json!({
        "results": results,
        "total": offline_carts.len(),
        "synced": synced,
        "rejected": offline_carts.len() - synced,
    }))
}

/// Merge offline cart items with online cart using specified strategy
pub async fn merge_carts(
    store: web::Data<CartStore>,
    body: web::Json<MergeRequest>,
) -> HttpResponse {
    let req = body.into_inner();
    let customer_id = req.customer_id;

    let mut cart = store
        .carts
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
            expires_at: Utc::now() + chrono::Duration::hours(24),
        })
        .clone();

    for offline_item in &req.offline_items {
        if let Some(existing) = cart.items.iter_mut().find(|i| i.sku == offline_item.sku) {
            match req.strategy {
                MergeStrategy::PreferOnline => {
                    // Keep online version — no change
                }
                MergeStrategy::PreferOffline => {
                    existing.quantity = offline_item.quantity;
                    existing.unit_price = offline_item.unit_price;
                }
                MergeStrategy::SumQuantities => {
                    existing.quantity += offline_item.quantity;
                }
                MergeStrategy::MaxQuantity => {
                    existing.quantity = existing.quantity.max(offline_item.quantity);
                }
            }
        } else {
            cart.items.push(offline_item.clone());
        }
    }

    recalculate_cart(&mut cart);
    store.carts.insert(customer_id, cart.clone());

    HttpResponse::Ok().json(serde_json::json!({
        "status": "merged",
        "strategy": format!("{:?}", req.strategy),
        "cart": cart,
    }))
}

fn recalculate_cart(cart: &mut Cart) {
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

fn compute_checksum(items: &[crate::models::CartItem]) -> String {
    let mut hasher = Sha256::new();
    for item in items {
        hasher.update(format!("{}:{}:{}", item.sku, item.quantity, item.unit_price));
    }
    hex::encode(hasher.finalize())
}
