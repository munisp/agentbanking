"""
Agent Business Dashboard API - FastAPI microservice
Backend API for agent business intelligence dashboard with revenue, growth, and operational metrics
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(

import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agent_business_dashboard")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS agent_metrics (
            id SERIAL PRIMARY KEY,
            agent_id TEXT, tx_count INTEGER, volume REAL,
            commission REAL, active_customers INTEGER, float_util REAL,
            recorded_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

@app.get("/api/v1/dashboard/{agent_id}")
async def get_dashboard(agent_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_metrics WHERE agent_id = %s ORDER BY recorded_at DESC LIMIT 1", (agent_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"agent_id": agent_id, "daily_tx_count": 0, "daily_volume": 0, "commission_earned": 0}
    return {"agent_id": agent_id, "daily_tx_count": row[2], "daily_volume": row[3],
            "commission_earned": row[4], "active_customers": row[5], "float_utilization": row[6]}

@app.post("/api/v1/metrics/record")
async def record_metric(request: Request):
    body = await request.json()
    agent_id = body.get("agentId")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agentId required")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO agent_metrics (agent_id, tx_count, volume, commission, active_customers, float_util, recorded_at)
                      VALUES (?, ?, ?, ?, ?, ?, NOW())""",
                   (agent_id, body.get("txCount", 0), body.get("volume", 0),
                    body.get("commission", 0), body.get("activeCustomers", 0), body.get("floatUtil", 0)))
    conn.commit()
    conn.close()
    return {"status": "recorded", "agent_id": agent_id}

@app.get("/api/v1/leaderboard")
async def get_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT agent_id, SUM(tx_count) as total_tx, SUM(volume) as total_vol, SUM(commission) as total_comm
                      FROM agent_metrics GROUP BY agent_id ORDER BY total_vol DESC LIMIT 50""")
    rows = cursor.fetchall()
    conn.close()
    return {"leaderboard": [{"agent_id": r[0], "total_transactions": r[1], "total_volume": r[2], "total_commission": r[3]} for r in rows]}
    title="Agent Business Dashboard API",
    description="Backend API for agent business intelligence dashboard with revenue, growth, and operational metrics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "agent-business-dashboard", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/dashboard/{agent_id}/overview")
async def get_dashboard_overview(agent_id: str):
    """Get agent dashboard overview with key metrics."""
    return {
        "agent_id": agent_id,
        "revenue": {"today": 0.0, "this_week": 0.0, "this_month": 0.0},
        "transactions": {"today": 0, "this_week": 0, "this_month": 0},
        "customers": {"total": 0, "new_this_month": 0},
        "float_balance": 0.0,
        "commission_earned": 0.0,
    }

@app.get("/api/v1/dashboard/{agent_id}/trends")
async def get_trends(agent_id: str, period: str = "30d"):
    """Get transaction and revenue trends."""
    return {"agent_id": agent_id, "period": period, "data_points": [], "trend": "stable"}

@app.get("/api/v1/dashboard/{agent_id}/alerts")
async def get_dashboard_alerts(agent_id: str):
    """Get actionable alerts for the agent."""
    return {"agent_id": agent_id, "alerts": [], "unread_count": 0}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
