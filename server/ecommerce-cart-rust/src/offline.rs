use actix_web::{web, HttpResponse};
use sha2::{Digest, Sha256};
use sqlx::Row;

use crate::AppState;
use crate::models::{MergeRequest, MergeStrategy, OfflineCart};

pub async fn sync_carts(
    state: web::Data<AppState>,
    body: web::Json<Vec<OfflineCart>>,
) -> HttpResponse {
    let offline_carts = body.into_inner();
    let mut results = Vec::new();

    for offline in &offline_carts {
        let computed = compute_checksum(&offline.items);
        if computed != offline.checksum {
            results.push(serde_json::json!({
                "clientId": offline.client_id,
                "status": "rejected",
                "reason": "checksum_mismatch",
            }));
            continue;
        }

        let has_online = sqlx::query("SELECT 1 FROM ecom_carts WHERE customer_id = $1")
            .bind(offline.customer_id)
            .fetch_optional(&state.pool).await
            .ok().flatten().is_some();

        // Ensure cart row exists
        sqlx::query(
            "INSERT INTO ecom_carts (customer_id, currency, expires_at)
             VALUES ($1, 'NGN', NOW() + INTERVAL '24 hours')
             ON CONFLICT (customer_id) DO UPDATE SET updated_at = NOW()"
        ).bind(offline.customer_id).execute(&state.pool).await.ok();

        for item in &offline.items {
            if has_online {
                sqlx::query(
                    "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (customer_id, sku) DO UPDATE SET quantity = GREATEST(ecom_cart_items.quantity, $5)"
                )
                .bind(offline.customer_id).bind(&item.sku).bind(item.product_id)
                .bind(&item.name).bind(item.quantity as i32).bind(item.unit_price)
                .bind(&item.currency).bind(&item.image_url).bind(item.merchant_id)
                .execute(&state.pool).await.ok();
            } else {
                sqlx::query(
                    "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (customer_id, sku) DO NOTHING"
                )
                .bind(offline.customer_id).bind(&item.sku).bind(item.product_id)
                .bind(&item.name).bind(item.quantity as i32).bind(item.unit_price)
                .bind(&item.currency).bind(&item.image_url).bind(item.merchant_id)
                .execute(&state.pool).await.ok();
            }
        }

        recalculate(&state.pool, offline.customer_id).await;

        results.push(serde_json::json!({
            "clientId": offline.client_id,
            "status": if has_online { "merged" } else { "synced" },
            "strategy": if has_online { "max_quantity" } else { "created" },
        }));
    }

    let synced = results.iter().filter(|r| r["status"] == "synced" || r["status"] == "merged").count();

    HttpResponse::Ok().json(serde_json::json!({
        "results": results,
        "total": offline_carts.len(),
        "synced": synced,
        "rejected": offline_carts.len() - synced,
    }))
}

pub async fn merge_carts(
    state: web::Data<AppState>,
    body: web::Json<MergeRequest>,
) -> HttpResponse {
    let req = body.into_inner();
    let customer_id = req.customer_id;

    sqlx::query(
        "INSERT INTO ecom_carts (customer_id, currency, expires_at)
         VALUES ($1, 'NGN', NOW() + INTERVAL '24 hours')
         ON CONFLICT (customer_id) DO UPDATE SET updated_at = NOW()"
    ).bind(customer_id).execute(&state.pool).await.ok();

    for item in &req.offline_items {
        match req.strategy {
            MergeStrategy::PreferOnline => {
                sqlx::query(
                    "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (customer_id, sku) DO NOTHING"
                )
                .bind(customer_id).bind(&item.sku).bind(item.product_id)
                .bind(&item.name).bind(item.quantity as i32).bind(item.unit_price)
                .bind(&item.currency).bind(&item.image_url).bind(item.merchant_id)
                .execute(&state.pool).await.ok();
            }
            MergeStrategy::PreferOffline => {
                sqlx::query(
                    "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (customer_id, sku) DO UPDATE SET quantity = $5, unit_price = $6"
                )
                .bind(customer_id).bind(&item.sku).bind(item.product_id)
                .bind(&item.name).bind(item.quantity as i32).bind(item.unit_price)
                .bind(&item.currency).bind(&item.image_url).bind(item.merchant_id)
                .execute(&state.pool).await.ok();
            }
            MergeStrategy::SumQuantities => {
                sqlx::query(
                    "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (customer_id, sku) DO UPDATE SET quantity = ecom_cart_items.quantity + $5"
                )
                .bind(customer_id).bind(&item.sku).bind(item.product_id)
                .bind(&item.name).bind(item.quantity as i32).bind(item.unit_price)
                .bind(&item.currency).bind(&item.image_url).bind(item.merchant_id)
                .execute(&state.pool).await.ok();
            }
            MergeStrategy::MaxQuantity => {
                sqlx::query(
                    "INSERT INTO ecom_cart_items (customer_id, sku, product_id, name, quantity, unit_price, currency, image_url, merchant_id)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (customer_id, sku) DO UPDATE SET quantity = GREATEST(ecom_cart_items.quantity, $5)"
                )
                .bind(customer_id).bind(&item.sku).bind(item.product_id)
                .bind(&item.name).bind(item.quantity as i32).bind(item.unit_price)
                .bind(&item.currency).bind(&item.image_url).bind(item.merchant_id)
                .execute(&state.pool).await.ok();
            }
        }
    }

    recalculate(&state.pool, customer_id).await;

    HttpResponse::Ok().json(serde_json::json!({
        "status": "merged",
        "strategy": format!("{:?}", req.strategy),
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

fn compute_checksum(items: &[crate::models::CartItem]) -> String {
    let mut hasher = Sha256::new();
    for item in items {
        hasher.update(format!("{}:{}:{}", item.sku, item.quantity, item.unit_price));
    }
    hex::encode(hasher.finalize())
}
