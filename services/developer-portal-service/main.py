"""
Developer Portal Service — API key management, webhooks, analytics, and integrations
"""
import logging
import os
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("developer-portal-service")

app = FastAPI(
    title="Developer Portal Service",
    description="API key management, webhooks, analytics, rate limiting, and integration marketplace for the 54agent developer portal",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:3000",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service_start_time = datetime.now()


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    uptime_seconds: int


class StatusResponse(BaseModel):
    service: str
    status: str
    uptime: str


@app.get("/")
async def root():
    return {
        "service": "developer-portal-service",
        "version": "1.0.0",
        "description": "Developer portal API management service",
        "status": "running",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "developer-portal-service",
        "timestamp": datetime.now(),
        "uptime_seconds": int(uptime),
    }


@app.get("/api/v1/status", response_model=StatusResponse)
async def get_status():
    uptime = datetime.now() - service_start_time
    return {
        "service": "developer-portal-service",
        "status": "operational",
        "uptime": str(uptime),
    }


@app.get("/api/v1/metrics")
async def get_metrics():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "requests_total": 5432,
        "requests_success": 5280,
        "requests_failed": 152,
        "avg_response_time_ms": 38,
        "uptime_seconds": int(uptime),
    }


app.include_router(router)
logger.info("Developer portal router loaded")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
