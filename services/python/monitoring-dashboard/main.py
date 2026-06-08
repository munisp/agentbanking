"""
Monitoring Dashboard Service
Real-time platform monitoring and metrics

Features:
- System health monitoring
- Performance metrics
- Alert management
- Real-time dashboards
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
import asyncpg
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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/monitoring")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Monitoring Dashboard Service", version="1.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/monitoring_dashboard")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
db_pool = None

class SystemMetrics(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    requests_per_second: float
    timestamp: datetime

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id SERIAL PRIMARY KEY,
                cpu_usage DECIMAL(5,2),
                memory_usage DECIMAL(5,2),
                disk_usage DECIMAL(5,2),
                active_connections INT,
                requests_per_second DECIMAL(10,2),
                timestamp TIMESTAMP DEFAULT NOW()
            );
        """)
    logger.info("Monitoring Dashboard Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.get("/metrics/current", response_model=SystemMetrics)
async def get_current_metrics():
    """Get current system metrics"""
    import psutil
    
    metrics = SystemMetrics(
        cpu_usage=psutil.cpu_percent(),
        memory_usage=psutil.virtual_memory().percent,
        disk_usage=psutil.disk_usage('/').percent,
        active_connections=len(psutil.net_connections()),
        requests_per_second=0.0,
        timestamp=datetime.utcnow()
    )
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO system_metrics (cpu_usage, memory_usage, disk_usage, active_connections, requests_per_second)
            VALUES ($1, $2, $3, $4, $5) RETURNING id""", metrics.cpu_usage, metrics.memory_usage, metrics.disk_usage, 
            metrics.active_connections, metrics.requests_per_second)
    
    return metrics

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "monitoring-dashboard"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8210)
