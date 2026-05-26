"""
54Link Store Analytics & Recommendation Engine — Python Microservice
Port: 8222

Provides real-time and batch analytics for agent stores:
- Sales forecasting (time series moving averages)
- Trending products detection
- Customer purchase pattern analysis
- Revenue insights and projections
- Store performance benchmarking
- Product recommendation (collaborative filtering)

Integrations:
- Kafka (Dapr): Consumes order.completed, product.viewed events; publishes analytics.updated
- Redis: Caches computed analytics, stores real-time counters
- Fluvio: Streams analytics events to lakehouse
- Temporal: Triggers periodic batch analytics workflows
- APISIX: Registered as upstream for /api/store-analytics/* routes
"""

import os
import sys
import json
import math
import logging
import hashlib
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List
from collections import defaultdict
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


# ── Configuration ───────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8222"))
DAPR_HTTP_PORT = int(os.getenv("DAPR_HTTP_PORT", "3500"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/12")
FLUVIO_ENDPOINT = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://localhost:9180")

# ── FastAPI App ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Store Analytics & Recommendation Engine",
    description="Real-time analytics, forecasting, and recommendations for agent stores",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

http_client = httpx.AsyncClient(timeout=10.0)

# ── In-Memory Analytics Store (production: PostgreSQL + Redis) ──────────────────

# Sales data: store_id -> list of {date, amount, items, productId}
store_sales: Dict[int, list] = defaultdict(list)
# Product views: store_id -> product_id -> count
product_views: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
# Customer purchases: customer_id -> list of product_ids
customer_purchases: Dict[int, list] = defaultdict(list)
# Store metrics cache
metrics_cache: Dict[str, Any] = {}


# ── Pydantic Models ────────────────────────────────────────────────────────────

class SaleEvent(BaseModel):
    store_id: int
    order_id: int
    customer_id: int
    amount: float
    items: List[Dict[str, Any]]
    payment_method: str = "card"
    timestamp: Optional[str] = None


class ProductViewEvent(BaseModel):
    store_id: int
    product_id: int
    customer_id: Optional[int] = None
    timestamp: Optional[str] = None


class ForecastRequest(BaseModel):
    store_id: int
    days_ahead: int = 30
    metric: str = "revenue"  # revenue, orders, avg_order


class BenchmarkRequest(BaseModel):
    store_id: int
    city: Optional[str] = None
    category: Optional[str] = None


# ── Analytics Core ──────────────────────────────────────────────────────────────

def moving_average(values: List[float], window: int = 7) -> List[float]:
    """Simple moving average for time series smoothing."""
    if len(values) < window:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        result.append(sum(values[start:i + 1]) / (i - start + 1))
    return result


def linear_trend(values: List[float]) -> tuple:
    """Linear regression for trend detection. Returns (slope, intercept)."""
    n = len(values)
    if n < 2:
        return (0.0, values[0] if values else 0.0)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean
    return (slope, intercept)


def forecast_values(values: List[float], days_ahead: int) -> List[float]:
    """Forecast future values using trend + seasonal decomposition."""
    if not values:
        return [0.0] * days_ahead
    slope, intercept = linear_trend(values)
    n = len(values)
    forecasts = []
    for i in range(days_ahead):
        trend_val = slope * (n + i) + intercept
        # Add weekly seasonality if enough data
        if n >= 14:
            week_idx = (n + i) % 7
            seasonal = sum(
                values[j] for j in range(week_idx, n, 7)
            ) / max(1, len(range(week_idx, n, 7))) - (sum(values) / n)
            trend_val += seasonal * 0.3  # Dampen seasonal component
        forecasts.append(max(0, round(trend_val, 2)))
    return forecasts


def detect_trending(
    sales: list, window_recent: int = 7, window_baseline: int = 30
) -> List[Dict[str, Any]]:
    """Detect trending products by comparing recent vs baseline sales velocity."""
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=window_recent)
    baseline_cutoff = now - timedelta(days=window_baseline)

    recent_counts: Dict[int, int] = defaultdict(int)
    baseline_counts: Dict[int, int] = defaultdict(int)

    for sale in sales:
        ts = datetime.fromisoformat(sale.get("timestamp", now.isoformat()))
        for item in sale.get("items", []):
            pid = item.get("productId", 0)
            if ts >= recent_cutoff:
                recent_counts[pid] += item.get("quantity", 1)
            if ts >= baseline_cutoff:
                baseline_counts[pid] += item.get("quantity", 1)

    trending = []
    for pid, recent in recent_counts.items():
        baseline = baseline_counts.get(pid, 0)
        # Normalize to daily rate
        recent_rate = recent / window_recent
        baseline_rate = baseline / window_baseline if window_baseline > 0 else 0
        if baseline_rate > 0:
            acceleration = (recent_rate - baseline_rate) / baseline_rate * 100
        else:
            acceleration = 100.0 if recent > 0 else 0.0
        if acceleration > 20:  # 20% acceleration threshold
            trending.append({
                "productId": pid,
                "recentSales": recent,
                "baselineSales": baseline,
                "acceleration": round(acceleration, 1),
                "name": item.get("name", f"Product #{pid}"),
            })

    trending.sort(key=lambda x: x["acceleration"], reverse=True)
    return trending[:20]


def compute_customer_segments(
    sales: list,
) -> Dict[str, Any]:
    """RFM-based customer segmentation (Recency, Frequency, Monetary)."""
    now = datetime.utcnow()
    customer_data: Dict[int, Dict[str, Any]] = {}

    for sale in sales:
        cid = sale.get("customer_id", 0)
        if cid == 0:
            continue
        ts = datetime.fromisoformat(sale.get("timestamp", now.isoformat()))
        amount = sale.get("amount", 0)
        if cid not in customer_data:
            customer_data[cid] = {"last_purchase": ts, "frequency": 0, "monetary": 0.0}
        cd = customer_data[cid]
        if ts > cd["last_purchase"]:
            cd["last_purchase"] = ts
        cd["frequency"] += 1
        cd["monetary"] += amount

    segments = {"champions": 0, "loyal": 0, "at_risk": 0, "new": 0, "lost": 0}
    for cid, data in customer_data.items():
        recency_days = (now - data["last_purchase"]).days
        freq = data["frequency"]
        if recency_days < 14 and freq >= 5:
            segments["champions"] += 1
        elif recency_days < 30 and freq >= 3:
            segments["loyal"] += 1
        elif recency_days > 60 and freq >= 2:
            segments["at_risk"] += 1
        elif freq <= 1:
            segments["new"] += 1
        elif recency_days > 90:
            segments["lost"] += 1
        else:
            segments["loyal"] += 1

    return {
        "segments": segments,
        "totalCustomers": len(customer_data),
        "avgOrdersPerCustomer": round(
            sum(d["frequency"] for d in customer_data.values()) / max(1, len(customer_data)),
            1,
        ),
        "avgSpendPerCustomer": round(
            sum(d["monetary"] for d in customer_data.values()) / max(1, len(customer_data)),
            2,
        ),
    }


def recommend_products(
    customer_id: int, store_id: int, limit: int = 10
) -> List[Dict[str, Any]]:
    """Collaborative filtering: recommend products bought by similar customers."""
    my_products = set(customer_purchases.get(customer_id, []))
    if not my_products:
        # Cold start: return most viewed products in store
        views = product_views.get(store_id, {})
        top = sorted(views.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"productId": pid, "score": count, "reason": "popular"} for pid, count in top]

    # Find similar customers (Jaccard similarity)
    scores: Dict[int, float] = defaultdict(float)
    for other_id, other_products in customer_purchases.items():
        if other_id == customer_id:
            continue
        other_set = set(other_products)
        intersection = my_products & other_set
        union = my_products | other_set
        if not union:
            continue
        similarity = len(intersection) / len(union)
        if similarity > 0.1:
            for pid in other_set - my_products:
                scores[pid] += similarity

    recommendations = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {"productId": pid, "score": round(score, 3), "reason": "similar_customers"}
        for pid, score in recommendations
    ]


# ── Middleware Integration Helpers ──────────────────────────────────────────────

async def publish_event(topic: str, data: dict):
    try:
        url = f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/kafka-pubsub/{topic}"
        await http_client.post(url, json=data)
    except Exception as e:
        logger.warning(f"Dapr publish failed for {topic}: {e}")


async def cache_set(key: str, value: Any, ttl: int = 3600):
    try:
        url = f"http://localhost:{DAPR_HTTP_PORT}/v1.0/state/redis-store"
        await http_client.post(url, json=[{"key": key, "value": value}])
    except Exception:
        pass


async def stream_to_fluvio(topic: str, data: dict):
    try:
        url = f"http://{FLUVIO_ENDPOINT}/produce/{topic}"
        await http_client.post(url, json=data)
    except Exception:
        pass


# ── API Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "store-analytics-engine",
        "version": "1.0.0",
        "time": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/analytics/ingest/sale")
async def ingest_sale(event: SaleEvent):
    """Ingest a sale event for analytics processing."""
    ts = event.timestamp or datetime.utcnow().isoformat()
    record = {
        "order_id": event.order_id,
        "customer_id": event.customer_id,
        "amount": event.amount,
        "items": event.items,
        "payment_method": event.payment_method,
        "timestamp": ts,
    }
    store_sales[event.store_id].append(record)

    # Update customer purchase history
    for item in event.items:
        pid = item.get("productId", 0)
        if pid:
            customer_purchases[event.customer_id].append(pid)

    await publish_event("analytics.sale.ingested", {
        "storeId": event.store_id, "orderId": event.order_id, "amount": event.amount,
    })

    return {"status": "ingested", "storeId": event.store_id}


@app.post("/api/v1/analytics/ingest/view")
async def ingest_view(event: ProductViewEvent):
    """Ingest a product view event."""
    product_views[event.store_id][event.product_id] += 1
    return {"status": "recorded"}


@app.get("/api/v1/analytics/store/{store_id}/dashboard")
async def store_dashboard(store_id: int = Path(...)):
    """Comprehensive store analytics dashboard."""
    sales = store_sales.get(store_id, [])
    now = datetime.utcnow()

    # Time-based aggregation
    today_sales = [s for s in sales if datetime.fromisoformat(s["timestamp"]).date() == now.date()]
    week_sales = [s for s in sales if (now - datetime.fromisoformat(s["timestamp"])).days <= 7]
    month_sales = [s for s in sales if (now - datetime.fromisoformat(s["timestamp"])).days <= 30]

    today_revenue = sum(s["amount"] for s in today_sales)
    week_revenue = sum(s["amount"] for s in week_sales)
    month_revenue = sum(s["amount"] for s in month_sales)

    # Daily revenue for last 30 days
    daily_revenue = []
    for i in range(30):
        d = (now - timedelta(days=29 - i)).date()
        day_total = sum(s["amount"] for s in sales if datetime.fromisoformat(s["timestamp"]).date() == d)
        daily_revenue.append({"date": d.isoformat(), "revenue": round(day_total, 2)})

    # Top products
    product_sales: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"quantity": 0, "revenue": 0.0, "name": ""})
    for sale in month_sales:
        for item in sale.get("items", []):
            pid = item.get("productId", 0)
            product_sales[pid]["quantity"] += item.get("quantity", 1)
            product_sales[pid]["revenue"] += item.get("price", 0) * item.get("quantity", 1)
            product_sales[pid]["name"] = item.get("name", f"Product #{pid}")

    top_products = sorted(product_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]
    top_products_list = [
        {"productId": pid, **data} for pid, data in top_products
    ]

    # Payment method breakdown
    payment_methods: Dict[str, int] = defaultdict(int)
    for sale in month_sales:
        payment_methods[sale.get("payment_method", "unknown")] += 1

    return {
        "storeId": store_id,
        "period": "last_30_days",
        "summary": {
            "todayRevenue": round(today_revenue, 2),
            "todayOrders": len(today_sales),
            "weekRevenue": round(week_revenue, 2),
            "weekOrders": len(week_sales),
            "monthRevenue": round(month_revenue, 2),
            "monthOrders": len(month_sales),
            "totalOrders": len(sales),
            "avgOrderValue": round(month_revenue / max(1, len(month_sales)), 2),
        },
        "dailyRevenue": daily_revenue,
        "topProducts": top_products_list,
        "paymentMethods": dict(payment_methods),
        "customerSegments": compute_customer_segments(month_sales),
        "trendingProducts": detect_trending(sales),
    }


@app.post("/api/v1/analytics/store/{store_id}/forecast")
async def sales_forecast(store_id: int = Path(...), req: ForecastRequest = None):
    """Forecast future sales using time series analysis."""
    if req is None:
        req = ForecastRequest(store_id=store_id)

    sales = store_sales.get(store_id, [])
    now = datetime.utcnow()

    # Build daily values for the last 90 days
    daily_values = []
    for i in range(90):
        d = (now - timedelta(days=89 - i)).date()
        if req.metric == "revenue":
            val = sum(s["amount"] for s in sales if datetime.fromisoformat(s["timestamp"]).date() == d)
        elif req.metric == "orders":
            val = sum(1 for s in sales if datetime.fromisoformat(s["timestamp"]).date() == d)
        else:  # avg_order
            day_sales = [s for s in sales if datetime.fromisoformat(s["timestamp"]).date() == d]
            val = sum(s["amount"] for s in day_sales) / max(1, len(day_sales)) if day_sales else 0
        daily_values.append(val)

    forecasted = forecast_values(daily_values, req.days_ahead)
    smoothed = moving_average(daily_values, 7)

    forecast_dates = [
        (now + timedelta(days=i + 1)).date().isoformat()
        for i in range(req.days_ahead)
    ]

    slope, _ = linear_trend(daily_values[-30:] if len(daily_values) >= 30 else daily_values)
    trend = "growing" if slope > 0.5 else "declining" if slope < -0.5 else "stable"

    return {
        "storeId": store_id,
        "metric": req.metric,
        "historical": [{"date": (now - timedelta(days=89 - i)).date().isoformat(), "value": round(v, 2)} for i, v in enumerate(daily_values)],
        "smoothed": [round(v, 2) for v in smoothed],
        "forecast": [{"date": d, "value": v} for d, v in zip(forecast_dates, forecasted)],
        "trend": trend,
        "slope": round(slope, 4),
        "confidence": "medium" if len(sales) >= 30 else "low",
    }


@app.get("/api/v1/analytics/store/{store_id}/trending")
async def trending_products(store_id: int = Path(...)):
    """Get trending products for a store."""
    sales = store_sales.get(store_id, [])
    trending = detect_trending(sales)
    return {"storeId": store_id, "trending": trending}


@app.get("/api/v1/analytics/store/{store_id}/recommendations/{customer_id}")
async def get_recommendations(
    store_id: int = Path(...),
    customer_id: int = Path(...),
    limit: int = Query(10, ge=1, le=50),
):
    """Get personalized product recommendations for a customer."""
    recs = recommend_products(customer_id, store_id, limit)
    return {
        "storeId": store_id,
        "customerId": customer_id,
        "recommendations": recs,
    }


@app.get("/api/v1/analytics/store/{store_id}/conversion")
async def conversion_funnel(store_id: int = Path(...)):
    """Conversion funnel: views -> cart -> purchase."""
    views = sum(product_views.get(store_id, {}).values())
    purchases = len(store_sales.get(store_id, []))
    # Estimate cart adds as 30% of views (heuristic)
    cart_adds = int(views * 0.3)

    return {
        "storeId": store_id,
        "funnel": {
            "views": views,
            "cartAdds": cart_adds,
            "purchases": purchases,
        },
        "rates": {
            "viewToCart": round(cart_adds / max(1, views) * 100, 1),
            "cartToPurchase": round(purchases / max(1, cart_adds) * 100, 1),
            "viewToPurchase": round(purchases / max(1, views) * 100, 1),
        },
    }


@app.get("/api/v1/analytics/store/{store_id}/revenue-breakdown")
async def revenue_breakdown(store_id: int = Path(...), days: int = Query(30)):
    """Revenue breakdown by product category, payment method, and time."""
    sales = store_sales.get(store_id, [])
    now = datetime.utcnow()
    period_sales = [s for s in sales if (now - datetime.fromisoformat(s["timestamp"])).days <= days]

    # By hour of day
    hourly: Dict[int, float] = defaultdict(float)
    for s in period_sales:
        hour = datetime.fromisoformat(s["timestamp"]).hour
        hourly[hour] += s["amount"]

    # By day of week
    daily_dow: Dict[str, float] = defaultdict(float)
    dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for s in period_sales:
        dow = datetime.fromisoformat(s["timestamp"]).weekday()
        daily_dow[dow_names[dow]] += s["amount"]

    total_revenue = sum(s["amount"] for s in period_sales)
    avg_daily = total_revenue / max(1, days)

    return {
        "storeId": store_id,
        "period": f"last_{days}_days",
        "totalRevenue": round(total_revenue, 2),
        "avgDailyRevenue": round(avg_daily, 2),
        "byHourOfDay": {str(h): round(v, 2) for h, v in sorted(hourly.items())},
        "byDayOfWeek": {d: round(v, 2) for d, v in daily_dow.items()},
        "peakHour": max(hourly, key=hourly.get) if hourly else None,
        "peakDay": max(daily_dow, key=daily_dow.get) if daily_dow else None,
    }


@app.get("/api/v1/analytics/platform/overview")
async def platform_overview():
    """Platform-wide analytics overview for all stores."""
    total_stores = len(store_sales)
    total_orders = sum(len(s) for s in store_sales.values())
    total_revenue = sum(sum(sale["amount"] for sale in sales) for sales in store_sales.values())

    # Top stores by revenue
    store_revenues = []
    for sid, sales in store_sales.items():
        rev = sum(s["amount"] for s in sales)
        store_revenues.append({"storeId": sid, "revenue": round(rev, 2), "orders": len(sales)})
    store_revenues.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "totalStores": total_stores,
        "totalOrders": total_orders,
        "totalRevenue": round(total_revenue, 2),
        "avgRevenuePerStore": round(total_revenue / max(1, total_stores), 2),
        "topStores": store_revenues[:10],
    }


# ── Startup ─────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info(f"Store Analytics Engine starting on :{PORT}")
    # Register with APISIX
    try:
        await http_client.put(
            f"{APISIX_ADMIN_URL}/apisix/admin/routes/store-analytics",
            json={
                "uri": "/api/store-analytics/*",
                "upstream": {
                    "type": "roundrobin",
                    "nodes": {f"http://localhost:{PORT}": 1},
                },
            },
            headers={"X-API-KEY": "edd1c9f034335f136f87ad84b625c8f1"},
        )
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
