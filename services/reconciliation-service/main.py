"""
Production reconciliation service — float vs ledger, settlement vs commission.
"""
import logging
import os
import signal
import sys
import atexit
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Startup validation ──────────────────────────────────────────────────────
_DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not _DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required and not set.")
if _DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("SQLite is not supported. Set DATABASE_URL to a PostgreSQL connection string.")

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("reconciliation-service")

# ── Graceful shutdown ────────────────────────────────────────────────────────
_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    logger.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logger.warning(f"[shutdown] Handler error: {e}")
    logger.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logger.info("[shutdown] atexit handler called"))

# ── App ──────────────────────────────────────────────────────────────────────
from router import router

app = FastAPI(
    title="Reconciliation Service",
    description="Automated reconciliation between float balances, ledger entries, and settlements.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service_start_time = datetime.now()


@app.on_event("startup")
def on_startup():
    """Create reconciliation_reports table if it does not exist."""
    from models import Base
    from router import engine
    Base.metadata.create_all(bind=engine)
    logger.info("reconciliation_reports table ensured.")


@app.get("/health")
def health_check():
    uptime = (datetime.now() - service_start_time).total_seconds()
    return {
        "status": "healthy",
        "service": "reconciliation-service",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": int(uptime),
    }


app.include_router(router)
logger.info("Reconciliation router loaded")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8150))
    uvicorn.run(app, host="0.0.0.0", port=port)
