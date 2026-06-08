import sys as _sys, os as _os

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

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Financial reconciliation service
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("reconciliation-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from datetime import datetime
import uvicorn
import os

import psycopg2
import psycopg2.extras

def _init_persistence():
    """Initialize PostgreSQL persistence for reconciliation-service."""
    import os
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', 'postgres://postgres:postgres@localhost:5432/reconciliation_service'))
        
        
        return conn
    except Exception as e:
        import logging
        logging.warning(f"Database unavailable ({e}) — running in-memory only")
        return None

_persistence_db = _init_persistence()

app = FastAPI(
    title="Reconciliation Service",
    description="Financial reconciliation service",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
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
        "service": "reconciliation-service",
        "version": "1.0.0",
        "description": "Financial reconciliation service",
        "status": "running"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "reconciliation-service",
        "timestamp": datetime.now(),
        "uptime_seconds": int(uptime)
    }

@app.get("/api/v1/status", response_model=StatusResponse)
async def get_status():
    """Get service status"""
    uptime = datetime.now() - service_start_time
    return {
        "service": "reconciliation-service",
        "status": "operational",
        "uptime": str(uptime)
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
        "uptime_seconds": int(uptime)
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
