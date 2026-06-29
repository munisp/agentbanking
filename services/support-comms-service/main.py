import os
import logging
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, Counter, Histogram
from starlette.responses import Response

from middlewares.required_headers import RequiredHeadersMiddleware
from api.v1 import health, support, broadcast, commerce, esg, analytics, payment_orchestration, helpdesk_v1

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Support & Comms Service",
    description=(
        "Microservice handling help desk tickets, live chat support, broadcast announcements, "
        "social commerce, ESG/carbon tracking, multi-channel payment orchestration, "
        "and revenue forecasting for the 54agent admin dashboard."
    ),
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS – allow all origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Required headers middleware
# Exempt: /health, /metrics, /docs, /openapi.json
# ---------------------------------------------------------------------------
app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=["x-tenant-id", "x-keycloak-realm", "x-keycloak-pub-key"],
    exclude_paths=["/health", "/metrics", "/docs", "/openapi.json"],
    exclude_prefixes=["/docs", "/redoc"],
)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency",
    ["method", "endpoint"],
)


@app.middleware("http")
async def prometheus_middleware(request, call_next):
    start_time = datetime.utcnow()
    response = await call_next(request)
    duration = (datetime.utcnow() - start_time).total_seconds()
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(duration)
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    return response


@app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Health check – mounted at root so /health is reachable without prefix
app.include_router(health.router)

# Support (tickets + live chat)
app.include_router(support.router, prefix="/api/support")

# Broadcast announcements
app.include_router(broadcast.router, prefix="/api/broadcast")

# Social commerce
app.include_router(commerce.router, prefix="/api/social-commerce")

# ESG / carbon tracking
app.include_router(esg.router, prefix="/api/esg")

# Revenue forecasting & analytics
app.include_router(analytics.router, prefix="/api/analytics")

# Multi-channel payment orchestration
app.include_router(payment_orchestration.router, prefix="/api/payment-orchestration")

# HelpDesk & chat v1 routes (called via /support/api/v1/* after APISIX strips /support/)
app.include_router(helpdesk_v1.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8011"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
