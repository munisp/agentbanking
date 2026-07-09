"""
POS-54Link E-Commerce Intelligence Service (Python)
- Product recommendations (collaborative filtering)
- Dynamic pricing engine (demand/inventory/competitor-aware)
- Sales analytics and forecasting
- Offline pricing sync
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from recommendations import RecommendationEngine
from pricing import DynamicPricingEngine
from analytics import SalesAnalytics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ecommerce-intelligence")

recommendation_engine: RecommendationEngine
pricing_engine: DynamicPricingEngine
sales_analytics: SalesAnalytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    global recommendation_engine, pricing_engine, sales_analytics
    db_url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    recommendation_engine = RecommendationEngine(db_url, redis_url)
    pricing_engine = DynamicPricingEngine(db_url, redis_url)
    sales_analytics = SalesAnalytics(db_url)

    logger.info("[ecommerce-intelligence-py] Service started")
    yield
    logger.info("[ecommerce-intelligence-py] Shutting down")


app = FastAPI(
    title="E-Commerce Intelligence Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "ecommerce-intelligence-py",
        "version": "1.0.0",
    }


# ── Recommendations ──────────────────────────────────────────────────────────


@app.get("/api/v1/recommendations/{customer_id}")
async def get_recommendations(customer_id: int, limit: int = 10):
    """Get personalized product recommendations for a customer."""
    recs = recommendation_engine.get_for_customer(customer_id, limit)
    return {"customerId": customer_id, "recommendations": recs, "count": len(recs)}


@app.get("/api/v1/recommendations/similar/{product_id}")
async def get_similar_products(product_id: int, limit: int = 8):
    """Get similar products based on item-item collaborative filtering."""
    similar = recommendation_engine.get_similar_products(product_id, limit)
    return {"productId": product_id, "similar": similar, "count": len(similar)}


@app.get("/api/v1/recommendations/trending")
async def get_trending(category_id: int = 0, limit: int = 20):
    """Get trending products (most purchased in last 7 days)."""
    trending = recommendation_engine.get_trending(category_id, limit)
    return {"trending": trending, "count": len(trending)}


@app.post("/api/v1/recommendations/record-interaction")
async def record_interaction(data: dict):
    """Record a customer-product interaction for model training."""
    recommendation_engine.record_interaction(
        customer_id=data["customerId"],
        product_id=data["productId"],
        interaction_type=data.get("type", "view"),
        metadata=data.get("metadata", {}),
    )
    return {"status": "recorded"}


# ── Dynamic Pricing ──────────────────────────────────────────────────────────


@app.get("/api/v1/pricing/{product_id}")
async def get_dynamic_price(product_id: int, customer_id: int = 0, quantity: int = 1):
    """Calculate dynamic price based on demand, inventory, customer segment."""
    price = pricing_engine.calculate(product_id, customer_id, quantity)
    return price


@app.get("/api/v1/pricing/bulk")
async def get_bulk_prices(product_ids: str, customer_id: int = 0):
    """Get prices for multiple products at once."""
    ids = [int(x) for x in product_ids.split(",") if x.strip()]
    prices = [pricing_engine.calculate(pid, customer_id, 1) for pid in ids]
    return {"prices": prices, "count": len(prices)}


@app.post("/api/v1/pricing/rules")
async def create_pricing_rule(data: dict):
    """Create a dynamic pricing rule."""
    rule_id = pricing_engine.add_rule(data)
    return {"ruleId": rule_id, "status": "created"}


@app.get("/api/v1/pricing/offline-cache")
async def get_offline_price_cache(category_id: int = 0, limit: int = 500):
    """Get price cache for offline use — agents download this periodically."""
    cache = pricing_engine.get_offline_cache(category_id, limit)
    return {
        "prices": cache,
        "count": len(cache),
        "generatedAt": pricing_engine.last_cache_time(),
        "validFor": "4h",
    }


# ── Sales Analytics ──────────────────────────────────────────────────────────


@app.get("/api/v1/analytics/sales/summary")
async def sales_summary(period: str = "7d"):
    """Get sales summary for a given period."""
    return sales_analytics.get_summary(period)


@app.get("/api/v1/analytics/sales/by-category")
async def sales_by_category(period: str = "30d", limit: int = 10):
    """Get sales breakdown by product category."""
    return sales_analytics.by_category(period, limit)


@app.get("/api/v1/analytics/sales/by-agent")
async def sales_by_agent(period: str = "30d", limit: int = 20):
    """Get sales performance by agent."""
    return sales_analytics.by_agent(period, limit)


@app.get("/api/v1/analytics/sales/forecast")
async def sales_forecast(horizon_days: int = 30):
    """Predict sales for the next N days using time-series model."""
    forecast = sales_analytics.forecast(horizon_days)
    return {"forecast": forecast, "horizonDays": horizon_days}


@app.get("/api/v1/analytics/inventory/velocity")
async def inventory_velocity(limit: int = 50):
    """Calculate inventory velocity (units sold per day per SKU)."""
    velocity = sales_analytics.inventory_velocity(limit)
    return {"items": velocity, "count": len(velocity)}


@app.get("/api/v1/analytics/basket")
async def basket_analysis(min_support: float = 0.01, limit: int = 20):
    """Market basket analysis — frequently bought together."""
    baskets = sales_analytics.basket_analysis(min_support, limit)
    return {"patterns": baskets, "count": len(baskets)}


# ── Voice Commerce (Hausa/Yoruba/Pidgin) ────────────────────────────────────


@app.post("/api/v1/voice/transcribe")
async def voice_transcribe(data: dict):
    """Transcribe voice order audio and extract cart items."""
    import asyncpg
    db_url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    language = data.get("language", "en")
    agent_id = data.get("agentId", 0)
    audio_url = data.get("audioUrl", "")

    # Language-specific product keywords (Nigerian market)
    product_keywords = {
        "ha": {"ruwan sha": "bottled_water", "gari": "garri", "shinkafa": "rice", "wake": "beans"},
        "yo": {"omi": "bottled_water", "gari": "garri", "iresi": "rice", "ewa": "beans"},
        "pcm": {"water": "bottled_water", "garri": "garri", "rice": "rice", "beans": "beans"},
        "en": {"water": "bottled_water", "garri": "garri", "rice": "rice", "beans": "beans"},
    }

    transcript = data.get("transcript", "")
    keywords = product_keywords.get(language, product_keywords["en"])
    parsed_items = []
    for keyword, product_sku in keywords.items():
        if keyword.lower() in transcript.lower():
            parsed_items.append({"sku": product_sku, "keyword": keyword, "quantity": 1})

    confidence = min(len(parsed_items) / max(len(transcript.split()), 1), 1.0)

    # Persist to PostgreSQL
    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            await conn.execute(
                """INSERT INTO voice_orders (agent_id, language, audio_url, transcript, parsed_items, confidence, status)
                   VALUES ($1, $2, $3, $4, $5::jsonb, $6, 'parsed')""",
                agent_id, language, audio_url, transcript,
                __import__("json").dumps(parsed_items), confidence
            )
            await conn.close()
        except Exception as e:
            logger.warning(f"Voice order persistence failed: {e}")

    return {
        "transcript": transcript,
        "language": language,
        "parsedItems": parsed_items,
        "confidence": round(confidence, 4),
        "status": "parsed",
    }


@app.get("/api/v1/voice/supported-languages")
async def voice_languages():
    """List supported voice commerce languages."""
    return {
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "ha", "name": "Hausa"},
            {"code": "yo", "name": "Yoruba"},
            {"code": "pcm", "name": "Nigerian Pidgin"},
            {"code": "ig", "name": "Igbo"},
            {"code": "fr", "name": "French"},
        ]
    }


# ── Merchant Analytics (PostgreSQL-backed) ──────────────────────────────────


@app.get("/api/v1/analytics/merchant/{store_id}")
async def merchant_analytics(store_id: int, period: str = "30d"):
    """Get merchant analytics dashboard data."""
    import asyncpg
    db_url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    if not db_url:
        return {"storeId": store_id, "error": "no_database"}

    try:
        conn = await asyncpg.connect(db_url)
        row = await conn.fetchrow(
            """SELECT
                COALESCE(SUM(revenue), 0) as total_revenue,
                COALESCE(SUM(order_count), 0) as total_orders,
                COALESCE(AVG(avg_order_value), 0) as avg_order_value,
                COALESCE(SUM(unique_customers), 0) as unique_customers,
                COALESCE(SUM(repeat_customers), 0) as repeat_customers
               FROM merchant_analytics_daily
               WHERE store_id = $1 AND date >= CURRENT_DATE - INTERVAL '30 days'""",
            store_id
        )
        await conn.close()

        return {
            "storeId": store_id,
            "period": period,
            "totalRevenue": float(row["total_revenue"]) if row else 0,
            "totalOrders": int(row["total_orders"]) if row else 0,
            "avgOrderValue": float(row["avg_order_value"]) if row else 0,
            "uniqueCustomers": int(row["unique_customers"]) if row else 0,
            "repeatCustomers": int(row["repeat_customers"]) if row else 0,
        }
    except Exception as e:
        logger.warning(f"Merchant analytics query failed: {e}")
        return {"storeId": store_id, "error": str(e)}


@app.post("/api/v1/analytics/merchant/{store_id}/refresh")
async def refresh_merchant_analytics(store_id: int):
    """Refresh merchant analytics from order data."""
    import asyncpg
    db_url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    if not db_url:
        return {"status": "no_database"}

    try:
        conn = await asyncpg.connect(db_url)
        await conn.execute(
            """INSERT INTO merchant_analytics_daily (store_id, date, revenue, order_count, avg_order_value)
               SELECT
                 $1, CURRENT_DATE,
                 COALESCE(SUM(total_amount::numeric), 0),
                 COUNT(*),
                 COALESCE(AVG(total_amount::numeric), 0)
               FROM ecommerce_orders
               WHERE merchant_id = $1 AND created_at >= CURRENT_DATE
               ON CONFLICT (store_id, date) DO UPDATE SET
                 revenue = EXCLUDED.revenue,
                 order_count = EXCLUDED.order_count,
                 avg_order_value = EXCLUDED.avg_order_value""",
            store_id
        )
        await conn.close()
        return {"status": "refreshed", "storeId": store_id}
    except Exception as e:
        logger.warning(f"Merchant analytics refresh failed: {e}")
        return {"status": "error", "error": str(e)}


# ── AI Dynamic Pricing Wire (Innovation) ────────────────────────────────────


@app.post("/api/v1/pricing/checkout-adjust")
async def checkout_price_adjust(data: dict):
    """Adjust pricing at checkout based on demand/inventory/time signals."""
    product_id = data.get("productId", 0)
    original_price = data.get("originalPrice", 0)
    quantity = data.get("quantity", 1)

    try:
        adjusted = pricing_engine.calculate_price(product_id, original_price)
        discount = max(0, original_price - adjusted)
        return {
            "productId": product_id,
            "originalPrice": original_price,
            "adjustedPrice": adjusted,
            "discount": round(discount, 2),
            "totalAdjusted": round(adjusted * quantity, 2),
            "reason": "dynamic_pricing",
        }
    except Exception as e:
        logger.warning(f"Dynamic pricing failed: {e}")
        return {"productId": product_id, "originalPrice": original_price, "adjustedPrice": original_price, "discount": 0, "reason": "fallback"}


# ── Offline Catalog Sync (Innovation) ───────────────────────────────────────


@app.get("/api/v1/catalog/offline-bundle")
async def offline_catalog_bundle(store_id: int = 0, format: str = "json"):
    """Generate offline catalog bundle for areas with poor connectivity."""
    import asyncpg
    db_url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    if not db_url:
        return {"error": "no_database", "products": []}

    try:
        conn = await asyncpg.connect(db_url)
        products = await conn.fetch(
            """SELECT id, name, sku, price, description, image_url, category_id
               FROM ecommerce_products
               WHERE is_active = true
               ORDER BY name LIMIT 500"""
        )
        await conn.close()

        catalog = [dict(p) for p in products]
        return {
            "storeId": store_id,
            "productCount": len(catalog),
            "generatedAt": __import__("datetime").datetime.utcnow().isoformat(),
            "format": format,
            "catalog": catalog,
        }
    except Exception as e:
        logger.warning(f"Offline catalog generation failed: {e}")
        return {"error": str(e), "products": []}


# ── POS-to-Ecommerce Bridge (Innovation) ────────────────────────────────────


@app.post("/api/v1/bridge/barcode-to-cart")
async def barcode_to_cart(data: dict):
    """Scan barcode at POS, look up product, prepare cart addition."""
    import asyncpg
    barcode = data.get("barcode", "")
    customer_id = data.get("customerId", 0)
    db_url = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    if not db_url:
        return {"error": "no_database"}

    try:
        conn = await asyncpg.connect(db_url)
        product = await conn.fetchrow(
            """SELECT id, name, sku, price, image_url, merchant_id
               FROM ecommerce_products WHERE sku = $1 OR barcode = $1 LIMIT 1""",
            barcode
        )
        await conn.close()

        if not product:
            return {"found": False, "barcode": barcode}

        return {
            "found": True,
            "barcode": barcode,
            "product": dict(product),
            "cartPayload": {
                "customerId": customer_id,
                "sku": product["sku"],
                "productId": product["id"],
                "name": product["name"],
                "quantity": 1,
                "unitPrice": str(product["price"]),
                "merchantId": product["merchant_id"] or 1,
            },
        }
    except Exception as e:
        logger.warning(f"Barcode lookup failed: {e}")
        return {"found": False, "barcode": barcode, "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("INTELLIGENCE_PORT", "8103"))
    uvicorn.run(app, host="0.0.0.0", port=port)
