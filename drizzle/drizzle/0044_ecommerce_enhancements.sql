-- E-Commerce Enhancements Migration
-- Gaps 1-15 + Enhancements + Innovations

-- ─── Rust Cart Service (PG persistence, replacing DashMap) ──────────────────
CREATE TABLE IF NOT EXISTS ecom_carts (
    customer_id BIGINT PRIMARY KEY,
    coupon_code TEXT,
    discount_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    sub_total DOUBLE PRECISION NOT NULL DEFAULT 0,
    item_count INT NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'NGN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE TABLE IF NOT EXISTS ecom_cart_items (
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
);

CREATE TABLE IF NOT EXISTS ecom_checkout_sessions (
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
);

-- ─── Social Commerce ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS social_commerce_connections (
    id SERIAL PRIMARY KEY,
    store_id INT NOT NULL,
    platform TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    platform_store_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(store_id, platform)
);

CREATE TABLE IF NOT EXISTS social_commerce_orders (
    id SERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    external_order_id TEXT NOT NULL,
    internal_order_id TEXT,
    store_id INT NOT NULL,
    customer_name TEXT,
    customer_phone TEXT,
    customer_address TEXT,
    total_amount NUMERIC(12,2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'NGN',
    status TEXT NOT NULL DEFAULT 'pending',
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, external_order_id)
);

-- ─── Flash Sales ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS flash_sales (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    inventory_cap INT,
    sold_count INT NOT NULL DEFAULT 0,
    discount_percent NUMERIC(5,2),
    discount_amount NUMERIC(12,2),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flash_sale_products (
    id SERIAL PRIMARY KEY,
    flash_sale_id INT NOT NULL REFERENCES flash_sales(id),
    product_id INT NOT NULL,
    original_price NUMERIC(12,2) NOT NULL,
    sale_price NUMERIC(12,2) NOT NULL,
    quantity_limit INT,
    sold INT NOT NULL DEFAULT 0
);

-- ─── Order Notifications ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_notifications (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    notification_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Multi-Currency Pricing ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS currency_rates (
    id SERIAL PRIMARY KEY,
    base_currency TEXT NOT NULL DEFAULT 'NGN',
    target_currency TEXT NOT NULL,
    rate NUMERIC(18,8) NOT NULL,
    source TEXT NOT NULL DEFAULT 'cbn',
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(base_currency, target_currency, source)
);

-- ─── Delivery GPS Tracking ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS delivery_gps_tracking (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    rider_id INT,
    latitude NUMERIC(10,7) NOT NULL,
    longitude NUMERIC(10,7) NOT NULL,
    speed NUMERIC(6,2),
    heading NUMERIC(5,2),
    eta_minutes INT,
    status TEXT NOT NULL DEFAULT 'in_transit',
    proof_of_delivery_url TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Voice Commerce ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS voice_orders (
    id SERIAL PRIMARY KEY,
    agent_id INT NOT NULL,
    customer_phone TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    audio_url TEXT,
    transcript TEXT,
    parsed_items JSONB,
    order_id INT,
    confidence NUMERIC(5,4),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Merchant Analytics ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS merchant_analytics_daily (
    id SERIAL PRIMARY KEY,
    store_id INT NOT NULL,
    date DATE NOT NULL,
    revenue NUMERIC(12,2) NOT NULL DEFAULT 0,
    order_count INT NOT NULL DEFAULT 0,
    avg_order_value NUMERIC(12,2) NOT NULL DEFAULT 0,
    unique_customers INT NOT NULL DEFAULT 0,
    repeat_customers INT NOT NULL DEFAULT 0,
    top_products JSONB,
    conversion_rate NUMERIC(5,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(store_id, date)
);

-- ─── Indexes ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ecom_ci_cust ON ecom_cart_items(customer_id);
CREATE INDEX IF NOT EXISTS idx_ecom_cs_cust ON ecom_checkout_sessions(customer_id);
CREATE INDEX IF NOT EXISTS idx_ecom_carts_exp ON ecom_carts(expires_at);
CREATE INDEX IF NOT EXISTS idx_social_conn_store ON social_commerce_connections(store_id);
CREATE INDEX IF NOT EXISTS idx_social_orders_store ON social_commerce_orders(store_id);
CREATE INDEX IF NOT EXISTS idx_flash_sales_time ON flash_sales(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_order_notif_order ON order_notifications(order_id);
CREATE INDEX IF NOT EXISTS idx_delivery_gps_order ON delivery_gps_tracking(order_id);
CREATE INDEX IF NOT EXISTS idx_voice_orders_agent ON voice_orders(agent_id);
CREATE INDEX IF NOT EXISTS idx_merchant_analytics ON merchant_analytics_daily(store_id, date);
CREATE INDEX IF NOT EXISTS idx_currency_rates ON currency_rates(base_currency, target_currency);
