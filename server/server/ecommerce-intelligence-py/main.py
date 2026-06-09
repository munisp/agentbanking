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


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("INTELLIGENCE_PORT", "8103"))
    uvicorn.run(app, host="0.0.0.0", port=port)
