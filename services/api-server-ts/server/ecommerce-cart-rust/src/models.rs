use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CartItem {
    pub sku: String,
    pub product_id: i64,
    pub name: String,
    pub quantity: u32,
    pub unit_price: f64,
    pub currency: String,
    pub image_url: Option<String>,
    pub merchant_id: i64,
    pub added_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Cart {
    pub customer_id: i64,
    pub items: Vec<CartItem>,
    pub coupon_code: Option<String>,
    pub discount_amount: f64,
    pub sub_total: f64,
    pub item_count: u32,
    pub currency: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AddItemRequest {
    pub sku: String,
    pub product_id: i64,
    pub name: String,
    pub quantity: u32,
    pub unit_price: f64,
    pub currency: Option<String>,
    pub image_url: Option<String>,
    pub merchant_id: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateItemRequest {
    pub sku: String,
    pub quantity: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CouponRequest {
    pub code: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckoutSession {
    pub session_id: String,
    pub customer_id: i64,
    pub cart: Cart,
    pub shipping_fee: f64,
    pub tax: f64,
    pub total: f64,
    pub payment_method: Option<String>,
    pub shipping_address: Option<ShippingAddress>,
    pub status: CheckoutStatus,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShippingAddress {
    pub street: String,
    pub city: String,
    pub state: String,
    pub country: String,
    pub zip_code: String,
    pub phone: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CheckoutStatus {
    #[serde(rename = "initiated")]
    Initiated,
    #[serde(rename = "payment_pending")]
    PaymentPending,
    #[serde(rename = "confirmed")]
    Confirmed,
    #[serde(rename = "expired")]
    Expired,
    #[serde(rename = "cancelled")]
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckoutConfirmRequest {
    pub payment_method: String,
    pub payment_ref: String,
    pub shipping_address: ShippingAddress,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OfflineCart {
    pub client_id: String,
    pub customer_id: i64,
    pub items: Vec<CartItem>,
    pub device_id: String,
    pub created_at: DateTime<Utc>,
    pub checksum: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MergeRequest {
    pub customer_id: i64,
    pub offline_items: Vec<CartItem>,
    pub strategy: MergeStrategy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MergeStrategy {
    #[serde(rename = "prefer_online")]
    PreferOnline,
    #[serde(rename = "prefer_offline")]
    PreferOffline,
    #[serde(rename = "sum_quantities")]
    SumQuantities,
    #[serde(rename = "max_quantity")]
    MaxQuantity,
}
