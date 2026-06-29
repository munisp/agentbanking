import os
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import inspect, text
from shared.middleware import apply_middleware
from shared.observability import setup_logging, metrics_router

from config import engine
from models import Base
from router import router as loyalty_router

logger = logging.getLogger(__name__)
AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")


def ensure_user_id_string_column() -> None:
    """Ensure legacy integer user_id columns are migrated to string in PostgreSQL."""
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    if "loyalty_accounts" not in inspector.get_table_names():
        return

    columns = {
        column["name"]: column for column in inspector.get_columns("loyalty_accounts")
    }
    user_id_column = columns.get("user_id")
    if not user_id_column:
        return

    column_type = str(user_id_column.get("type", "")).lower()
    if any(token in column_type for token in ("char", "text", "string", "varchar")):
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE loyalty_accounts "
                "ALTER COLUMN user_id TYPE VARCHAR(64) USING user_id::text"
            )
        )
    logger.info("Migrated loyalty_accounts.user_id column type to VARCHAR(64)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        ensure_user_id_string_column()
    except Exception as exc:
        logger.warning("Could not auto-migrate user_id column type: %s", exc)
    yield


app = FastAPI(
    title="Loyalty Service",
    description="Customer loyalty and rewards",
    version="1.0.0",
    lifespan=lifespan,
)


def emit_audit_event(request: Request, status_code: int):
    event_type_map = {
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }
    event_type = event_type_map.get(request.method)
    if not event_type:
        return

    tenant_id = request.headers.get("x-tenant-id") or "54agent"
    actor_id = request.headers.get("x-keycloak-id") or "system"

    payload = {
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "event_data": {
            "service": "loyalty-service",
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "query": str(request.url.query),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    def _send():
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{AUDIT_SVC_URL}/audits",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-tenant-id": tenant_id,
                        "x-keycloak-id": actor_id,
                    },
                )
        except Exception:
            logger.warning("Failed to emit audit event")

    threading.Thread(target=_send, daemon=True).start()


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and response.status_code < 500
        and not request.url.path.startswith(("/docs", "/openapi", "/redoc"))
    ):
        emit_audit_event(request, response.status_code)
    return response

apply_middleware(app)
setup_logging("loyalty-service")
app.include_router(metrics_router)
app.include_router(loyalty_router)

# CORS
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

# Service state
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
    """Root endpoint"""
    return {
        "service": "loyalty-service",
        "version": "1.0.0",
        "description": "Customer loyalty and rewards",
        "status": "running",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "loyalty-service",
        "timestamp": datetime.now(),
        "uptime_seconds": int(uptime),
    }


@app.get("/api/v1/status", response_model=StatusResponse)
async def get_status():
    """Get service status"""
    uptime = datetime.now() - service_start_time
    return {
        "service": "loyalty-service",
        "status": "operational",
        "uptime": str(uptime),
    }


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get service metrics"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "requests_total": 1000,
        "requests_success": 950,
        "requests_failed": 50,
        "avg_response_time_ms": 45,
        "uptime_seconds": int(uptime),
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
