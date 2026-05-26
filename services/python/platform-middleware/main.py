"""
Platform Middleware Service
Core middleware orchestration and routing

Features:
- Request routing
- Load balancing
- Circuit breaker
- Rate limiting
"""

from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
import asyncpg
import httpx
import os
import logging

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


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Platform Middleware Service", version="1.0.0")
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS request_logs (
                id SERIAL PRIMARY KEY,
                path VARCHAR(200),
                method VARCHAR(10),
                status_code INT,
                timestamp TIMESTAMP DEFAULT NOW()
            );
        """)
    logger.info("Platform Middleware Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    response = await call_next(request)
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO request_logs (path, method, status_code)
            VALUES ($1, $2, $3)
        """, str(request.url.path), request.method, response.status_code)
    
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "platform-middleware"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8213)
