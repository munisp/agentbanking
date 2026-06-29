"""
54agent Platform Dashboard Service
Real-time dashboard metrics with Redis caching and PostgreSQL aggregations.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import aioredis

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


logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DASHBOARD_CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL", "30"))

app = FastAPI(title="Dashboard Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from fastapi import APIRouter
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

async def get_db():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

async def get_redis():
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()


@router.get("/stats")
async def get_dashboard_stats(
    period: str = Query(default="today", pattern="^(today|week|month|year)$"),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Get main dashboard statistics"""
    cache_key = f"dashboard:stats:{period}"
    
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    try:
        now = datetime.utcnow()
        period_map = {
            "today": now - timedelta(days=1),
            "week": now - timedelta(weeks=1),
            "month": now - timedelta(days=30),
            "year": now - timedelta(days=365),
        }
        since = period_map[period]
        
        # Parallel queries
        total_agents = await db.fetchval("SELECT COUNT(*) FROM agents WHERE is_active = true") or 0
        active_agents = await db.fetchval(
            "SELECT COUNT(*) FROM agents WHERE is_active = true AND last_activity > $1", since
        ) or 0
        total_transactions = await db.fetchval(
            "SELECT COUNT(*) FROM transactions WHERE created_at > $1", since
        ) or 0
        total_volume = await db.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE created_at > $1 AND status = 'completed'", since
        ) or 0
        pending_kyc = await db.fetchval(
            "SELECT COUNT(*) FROM kyc_applications WHERE status = 'pending'"
        ) or 0
        fraud_alerts = await db.fetchval(
            "SELECT COUNT(*) FROM fraud_alerts WHERE status = 'open' AND created_at > $1", since
        ) or 0
        total_customers = await db.fetchval("SELECT COUNT(*) FROM customers") or 0
        
        # Transaction trend (last 7 days)
        trend_rows = await db.fetch(
            """SELECT DATE(created_at) as date, COUNT(*) as count, SUM(amount) as volume
               FROM transactions 
               WHERE created_at > NOW() - INTERVAL '7 days'
               GROUP BY DATE(created_at) ORDER BY date""",
        )
        
        stats = {
            "period": period,
            "agents": {
                "total": int(total_agents),
                "active": int(active_agents),
                "inactive": int(total_agents) - int(active_agents),
            },
            "transactions": {
                "total": int(total_transactions),
                "volume": float(total_volume),
                "volume_formatted": f"₦{float(total_volume)/1_000_000:.2f}M",
            },
            "customers": {
                "total": int(total_customers),
            },
            "compliance": {
                "pending_kyc": int(pending_kyc),
                "fraud_alerts": int(fraud_alerts),
            },
            "trend": [
                {
                    "date": str(r["date"]),
                    "transactions": int(r["count"]),
                    "volume": float(r["volume"] or 0),
                }
                for r in trend_rows
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await redis.setex(cache_key, DASHBOARD_CACHE_TTL, json.dumps(stats, default=str))
        return stats
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return _fallback_stats(period)


@router.get("/transactions/recent")
async def get_recent_transactions(
    limit: int = Query(default=10, le=100),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Get recent transactions for dashboard"""
    cache_key = f"dashboard:recent_txns:{limit}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    try:
        rows = await db.fetch(
            """SELECT t.id, t.transaction_ref, t.type, t.amount, t.currency,
                      t.status, t.created_at, 
                      a.name as agent_name, a.agent_code,
                      c.name as customer_name
               FROM transactions t
               LEFT JOIN agents a ON t.agent_id = a.id
               LEFT JOIN customers c ON t.customer_id = c.id
               ORDER BY t.created_at DESC LIMIT $1""",
            limit
        )
        result = [dict(r) for r in rows]
        await redis.setex(cache_key, 15, json.dumps(result, default=str))
        return result
    except Exception as e:
        logger.error(f"Recent transactions error: {e}")
        return []


@router.get("/agents/top")
async def get_top_agents(
    limit: int = Query(default=5, le=20),
    period: str = Query(default="month"),
    db=Depends(get_db),
):
    """Get top performing agents"""
    try:
        since = datetime.utcnow() - timedelta(days=30 if period == "month" else 7)
        rows = await db.fetch(
            """SELECT a.id, a.name, a.agent_code, a.tier,
                      COUNT(t.id) as transaction_count,
                      COALESCE(SUM(t.amount), 0) as total_volume
               FROM agents a
               LEFT JOIN transactions t ON t.agent_id = a.id AND t.created_at > $2
               WHERE a.is_active = true
               GROUP BY a.id, a.name, a.agent_code, a.tier
               ORDER BY total_volume DESC LIMIT $1""",
            limit, since
        )
        return [dict(r) for r in rows]
    except Exception as e:
        return []


@router.get("/system/health")
async def get_system_health(
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Get system health metrics"""
    health = {
        "database": "healthy",
        "cache": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    try:
        await db.fetchval("SELECT 1")
    except Exception:
        health["database"] = "unhealthy"
    
    try:
        await redis.ping()
    except Exception:
        health["cache"] = "unhealthy"
    
    health["overall"] = "healthy" if all(
        v == "healthy" for k, v in health.items() if k not in ("timestamp", "overall")
    ) else "degraded"
    
    return health


@router.get("/notifications")
async def get_notifications(
    unread_only: bool = True,
    limit: int = Query(default=20, le=100),
    db=Depends(get_db),
):
    """Get platform notifications"""
    try:
        query = """SELECT id, type, title, message, is_read, created_at
                   FROM platform_notifications"""
        params = []
        if unread_only:
            query += " WHERE is_read = false"
        query += " ORDER BY created_at DESC LIMIT $1"
        params.append(limit)
        
        rows = await db.fetch(query, *params)
        return [dict(r) for r in rows]
    except Exception as e:
        return []


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, db=Depends(get_db)):
    """Mark a notification as read"""
    try:
        await db.execute(
            "UPDATE platform_notifications SET is_read = true, read_at = NOW() WHERE id = $1",
            notification_id
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _fallback_stats(period: str) -> Dict[str, Any]:
    """Return empty stats structure when DB is unavailable"""
    return {
        "period": period,
        "agents": {"total": 0, "active": 0, "inactive": 0},
        "transactions": {"total": 0, "volume": 0.0, "volume_formatted": "₦0.00"},
        "customers": {"total": 0},
        "compliance": {"pending_kyc": 0, "fraud_alerts": 0},
        "trend": [],
        "timestamp": datetime.utcnow().isoformat(),
        "_fallback": True,
    }


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
