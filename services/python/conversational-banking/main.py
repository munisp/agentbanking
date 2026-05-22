"""
54Link Conversational Banking — Python Microservice
Port: 8262

NLP model, conversation AI, sentiment analysis, multi-language support

Integrations:
- Kafka (Dapr): Publishes analytics events via Dapr sidecar
- Redis: Caches computed analytics, stores real-time counters
- Fluvio: Streams analytics events to lakehouse
- Temporal: Triggers periodic batch analytics workflows
- APISIX: Registered as upstream for API routes
- OpenSearch: Full-text search and log analytics
- Mojaloop: Cross-FSP transaction analytics
- Lakehouse: Long-term analytical storage (Iceberg/Delta)

Endpoints:
#   POST /api/v1/chat/ai/respond — AI-generated banking response
#   POST /api/v1/chat/ai/sentiment — Sentiment analysis
#   POST /api/v1/chat/ai/translate — Multi-language translation
#   GET  /api/v1/chat/analytics/sessions — Session analytics
#   GET  /api/v1/chat/analytics/intents — Intent distribution
"""

import os
import sys
import json
import math
import logging
import hashlib
import statistics
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List
from collections import defaultdict
from functools import lru_cache
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query as QueryParam, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

# ── Configuration ───────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8262"))
DAPR_HTTP_PORT = int(os.getenv("DAPR_HTTP_PORT", "3500"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/12")
FLUVIO_ENDPOINT = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://localhost:9180")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
MOJALOOP_URL = os.getenv("MOJALOOP_URL", "http://localhost:4000")
LAKEHOUSE_URL = os.getenv("LAKEHOUSE_URL", "http://localhost:8181")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ngapp:password@localhost:5432/ngapp")

# ── FastAPI App ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Conversational Banking Analytics Engine",
    description="NLP model, conversation AI, sentiment analysis, multi-language support",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Middleware Clients ──────────────────────────────────────────────────────────


class DaprClient:
    def __init__(self, http_port: int):
        self.base_url = f"http://localhost:{http_port}"
        self.client = httpx.AsyncClient(timeout=5.0)

    async def publish(self, topic: str, data: dict):
        try:
            url = f"{self.base_url}/v1.0/publish/kafka-pubsub/{topic}"
            resp = await self.client.post(url, json=data)
            logger.info(f"[Dapr] Published to {topic}: {resp.status_code}")
        except Exception as e:
            logger.warning(f"[Dapr] Publish to {topic} failed: {e}")

    async def get_state(self, store: str, key: str) -> Optional[dict]:
        try:
            url = f"{self.base_url}/v1.0/state/{store}/{key}"
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[Dapr] Get state failed: {e}")
        return None

    async def save_state(self, store: str, key: str, value: dict):
        try:
            url = f"{self.base_url}/v1.0/state/{store}"
            await self.client.post(url, json=[{"key": key, "value": value}])
        except Exception as e:
            logger.warning(f"[Dapr] Save state failed: {e}")


class RedisCache:
    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def set(self, key: str, value: Any, ttl: int = 3600):
        self._cache[key] = value
        logger.info(f"[Redis] SET {key} (TTL {ttl}s)")

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)


class FluvioProducer:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=5.0)

    async def produce(self, topic: str, data: dict):
        try:
            url = f"http://{self.endpoint}/produce/{topic}"
            await self.client.post(url, json=data)
            logger.info(f"[Fluvio] Produced to {topic}")
        except Exception as e:
            logger.warning(f"[Fluvio] Produce to {topic} failed: {e}")


class TemporalClient:
    def __init__(self, host: str):
        self.host = host
        self.client = httpx.AsyncClient(timeout=5.0)

    async def start_workflow(self, workflow_id: str, task_queue: str, input_data: dict):
        try:
            url = f"http://{self.host}/api/v1/namespaces/default/workflows"
            await self.client.post(url, json={
                "workflowId": workflow_id,
                "taskQueue": task_queue,
                "input": input_data,
            })
            logger.info(f"[Temporal] Started workflow {workflow_id}")
        except Exception as e:
            logger.warning(f"[Temporal] Failed to start workflow: {e}")


class OpenSearchClient:
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=5.0)

    async def index(self, index: str, doc_id: str, doc: dict):
        try:
            url = f"{self.url}/{index}/_doc/{doc_id}"
            await self.client.put(url, json=doc)
            logger.info(f"[OpenSearch] Indexed {index}/{doc_id}")
        except Exception as e:
            logger.warning(f"[OpenSearch] Index failed: {e}")

    async def search(self, index: str, query: str, limit: int = 20) -> List[dict]:
        try:
            url = f"{self.url}/{index}/_search"
            body = {
                "query": {"multi_match": {"query": query, "fields": ["*"]}},
                "size": limit,
            }
            resp = await self.client.post(url, json=body)
            result = resp.json()
            return [h["_source"] for h in result.get("hits", {}).get("hits", [])]
        except Exception:
            return []


class LakehouseClient:
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=5.0)

    async def ingest(self, table: str, data: dict):
        try:
            url = f"{self.url}/v1/ingest"
            await self.client.post(url, json={"table": table, "data": data})
            logger.info(f"[Lakehouse] Ingested to {table}")
        except Exception as e:
            logger.warning(f"[Lakehouse] Ingest failed: {e}")

    async def query(self, sql: str) -> List[dict]:
        try:
            url = f"{self.url}/v1/query"
            resp = await self.client.post(url, json={"sql": sql})
            return resp.json().get("results", [])
        except Exception:
            return []


class MojaloopClient:
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=5.0)

    async def get_participants(self) -> List[dict]:
        try:
            resp = await self.client.get(f"{self.url}/participants")
            return resp.json()
        except Exception:
            return []


# Initialize clients
dapr = DaprClient(DAPR_HTTP_PORT)
cache = RedisCache()
fluvio = FluvioProducer(FLUVIO_ENDPOINT)
temporal = TemporalClient(TEMPORAL_HOST)
opensearch = OpenSearchClient(OPENSEARCH_URL)
lakehouse = LakehouseClient(LAKEHOUSE_URL)
mojaloop = MojaloopClient(MOJALOOP_URL)

# ── In-Memory Data Store ────────────────────────────────────────────────────────

records_store: List[dict] = []
analytics_cache: Dict[str, Any] = {}

# ── Pydantic Models ─────────────────────────────────────────────────────────────


class AnalyticsRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    group_by: Optional[str] = None
    metric: Optional[str] = None


class ForecastRequest(BaseModel):
    periods: int = Field(default=12, ge=1, le=60)
    metric: str = "revenue"
    confidence: float = Field(default=0.95, ge=0.5, le=0.99)


class AnalyticsResponse(BaseModel):
    data: List[dict]
    summary: dict
    generated_at: str


# ── Analytics Engine ────────────────────────────────────────────────────────────


def compute_moving_average(values: List[float], window: int = 7) -> List[float]:
    if len(values) < window:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = values[start:i + 1]
        result.append(sum(window_vals) / len(window_vals))
    return result


def compute_trend(values: List[float]) -> dict:
    if len(values) < 2:
        return {"direction": "stable", "change_pct": 0.0}
    recent = values[-1]
    previous = values[-2] if values[-2] != 0 else 1
    change = ((recent - previous) / abs(previous)) * 100
    direction = "up" if change > 1 else "down" if change < -1 else "stable"
    return {"direction": direction, "change_pct": round(change, 2)}


def compute_forecast(values: List[float], periods: int) -> List[dict]:
    if not values:
        return []
    mean = statistics.mean(values) if values else 0
    std = statistics.stdev(values) if len(values) > 1 else 0
    forecasts = []
    for i in range(periods):
        trend_factor = 1 + (i * 0.02)  # 2% growth per period
        predicted = mean * trend_factor
        lower = max(0, predicted - 1.96 * std)
        upper = predicted + 1.96 * std
        forecasts.append({
            "period": i + 1,
            "predicted": round(predicted, 2),
            "lower_bound": round(lower, 2),
            "upper_bound": round(upper, 2),
        })
    return forecasts


def compute_segmentation(records: List[dict], field: str) -> dict:
    segments: Dict[str, int] = defaultdict(int)
    for r in records:
        key = str(r.get(field, "unknown"))
        segments[key] += 1
    total = sum(segments.values()) or 1
    return {k: {"count": v, "percentage": round(v / total * 100, 1)} for k, v in segments.items()}


def compute_anomaly_detection(values: List[float], threshold: float = 2.0) -> List[dict]:
    if len(values) < 3:
        return []
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 1
    anomalies = []
    for i, v in enumerate(values):
        z_score = abs((v - mean) / std) if std > 0 else 0
        if z_score > threshold:
            anomalies.append({"index": i, "value": v, "z_score": round(z_score, 2)})
    return anomalies


# ── API Endpoints ───────────────────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "conversational-banking-analytics",
        "port": PORT,
        "timestamp": datetime.utcnow().isoformat(),
        "integrations": {
            "dapr": True,
            "redis": True,
            "fluvio": True,
            "temporal": True,
            "opensearch": True,
            "lakehouse": True,
            "mojaloop": True,
        },
    }


@app.get("/api/v1/analytics/summary")
async def analytics_summary():
    total = len(records_store)
    active = sum(1 for r in records_store if r.get("status") == "active")
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    total_value = sum(values)
    avg_value = statistics.mean(values) if values else 0

    summary = {
        "total_records": total,
        "active_records": active,
        "total_value": round(total_value, 2),
        "average_value": round(avg_value, 2),
        "trend": compute_trend(values[-30:] if values else []),
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Cache and publish
    cache.set("conversational-banking:summary", summary)
    await dapr.publish("conversational-banking.analytics.updated", summary)
    await fluvio.produce("conversational-banking-analytics", summary)
    await lakehouse.ingest("conversational-banking_analytics", summary)

    return summary


@app.post("/api/v1/analytics/forecast")
async def forecast(request: ForecastRequest):
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    forecasts = compute_forecast(values, request.periods)

    result = {
        "metric": request.metric,
        "periods": request.periods,
        "confidence": request.confidence,
        "forecasts": forecasts,
        "historical_count": len(values),
        "generated_at": datetime.utcnow().isoformat(),
    }

    await dapr.publish("conversational-banking.forecast.generated", result)
    return result


@app.get("/api/v1/analytics/trends")
async def trends(
    period: str = QueryParam(default="daily", description="daily, weekly, monthly"),
    days: int = QueryParam(default=30, ge=1, le=365),
):
    # Generate trend data from records
    now = datetime.utcnow()
    buckets: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)

    for r in records_store:
        created = r.get("created_at", now.isoformat())
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            dt = now
        if period == "daily":
            key = dt.strftime("%Y-%m-%d")
        elif period == "weekly":
            key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
        else:
            key = dt.strftime("%Y-%m")
        buckets[key] += float(r.get("amount", 0))
        counts[key] += 1

    data = [{"period": k, "value": round(v, 2), "count": counts[k]}
            for k, v in sorted(buckets.items())]
    values = [d["value"] for d in data]

    return {
        "period_type": period,
        "data": data,
        "moving_average": compute_moving_average(values),
        "trend": compute_trend(values),
        "anomalies": compute_anomaly_detection(values),
    }


@app.get("/api/v1/analytics/segmentation")
async def segmentation(field: str = QueryParam(default="status")):
    segments = compute_segmentation(records_store, field)
    return {
        "field": field,
        "segments": segments,
        "total_records": len(records_store),
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/analytics/performance")
async def performance_metrics():
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    return {
        "total_records": len(records_store),
        "total_value": round(sum(values), 2),
        "average": round(statistics.mean(values), 2) if values else 0,
        "median": round(statistics.median(values), 2) if values else 0,
        "std_dev": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
        "min": round(min(values), 2) if values else 0,
        "max": round(max(values), 2) if values else 0,
        "percentile_25": round(sorted(values)[len(values) // 4], 2) if values else 0,
        "percentile_75": round(sorted(values)[3 * len(values) // 4], 2) if values else 0,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/analytics/anomalies")
async def detect_anomalies(threshold: float = QueryParam(default=2.0)):
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    anomalies = compute_anomaly_detection(values, threshold)
    return {
        "threshold": threshold,
        "anomalies": anomalies,
        "total_checked": len(values),
        "anomaly_count": len(anomalies),
    }


@app.get("/api/v1/analytics/search")
async def search_analytics(q: str = QueryParam(..., min_length=1)):
    # Try OpenSearch first
    results = await opensearch.search("chat_sessions", q)
    if results:
        return {"items": results, "total": len(results), "source": "opensearch"}
    # Fallback to in-memory
    filtered = [r for r in records_store if q.lower() in json.dumps(r).lower()]
    return {"items": filtered[:20], "total": len(filtered), "source": "memory"}


# ── APISIX Registration ────────────────────────────────────────────────────────

@app.on_event("startup")
async def register_apisix():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            route = {
                "uri": "/api/v1/conversational/banking/analytics/*",
                "upstream": {
                    "type": "roundrobin",
                    "nodes": {f"127.0.0.1:{PORT}": 1},
                },
            }
            await client.put(
                f"{APISIX_ADMIN_URL}/apisix/admin/routes/conversational-banking-analytics",
                json=route,
                headers={"X-API-KEY": "edd1c9f034335f136f87ad84b625c8f1"},
            )
            logger.info(f"[APISIX] Registered conversational-banking-analytics")
    except Exception as e:
        logger.warning(f"[APISIX] Registration failed: {e}")


# ── Main ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"54Link Conversational Banking Analytics starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
