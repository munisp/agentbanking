import concurrent.futures

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database import engine
from utils import create_logger

health_router = APIRouter()

logger = create_logger(__name__)

@health_router.get("/health")
def health():
    return {
        "message": "Api is healthy!"
    }

def _db_ping():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

@health_router.get("/ready")
def ready():
    """Readiness — distinct from /health: fails with 503 unless the database
    is reachable. The probe is bounded to 3 seconds so a hung pool cannot
    stall the load balancer's readiness check."""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            ex.submit(_db_ping).result(timeout=3)
    except Exception as exc:
        logger.warning("readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": str(exc)},
        )
    return {"status": "ready"}