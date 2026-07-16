"""Security Monitoring Service."""

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from config import engine
from models import Base
from router import router as alerts_router


app = FastAPI(
    title="Security Monitoring",
    description="Security Monitoring for Remittance Platform",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the DB-backed alerts router at /api/v1/security-monitoring
app.include_router(alerts_router, prefix="/api/v1")

REDIS_URL = os.getenv("REDIS_URL", "")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = os.getenv("SMTP_PORT", "")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

dependency_status: Dict[str, Any] = {
    "postgres": "not_configured",
    "redis": "not_configured",
    "twilio": "not_configured",
    "smtp": "not_configured",
    "keycloak": "not_configured",
    "kafka": "not_configured",
}

_redis_client: Optional[redis.Redis] = None


@app.on_event("startup")
async def startup():
    global _redis_client

    try:
        Base.metadata.create_all(bind=engine)
        dependency_status["postgres"] = "connected"
    except Exception as exc:
        dependency_status["postgres"] = f"degraded: {str(exc)[:120]}"

    if REDIS_URL:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await _redis_client.ping()
            dependency_status["redis"] = "connected"
        except Exception as exc:
            dependency_status["redis"] = f"degraded: {str(exc)[:120]}"

    dependency_status["twilio"] = (
        "configured"
        if all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER])
        else "not_configured"
    )
    dependency_status["smtp"] = (
        "configured"
        if all([SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD])
        else "not_configured"
    )
    dependency_status["keycloak"] = (
        "configured" if KEYCLOAK_URL and KEYCLOAK_REALM else "not_configured"
    )
    dependency_status["kafka"] = (
        "configured" if KAFKA_BOOTSTRAP_SERVERS else "not_configured"
    )


@app.on_event("shutdown")
async def shutdown():
    global _redis_client
    if _redis_client:
        await _redis_client.close()


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "security-monitoring",
        "dependencies": dependency_status,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8132)
