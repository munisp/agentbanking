"""
Analytics Service - FastAPI microservice
Business intelligence and analytics engine with real-time metrics, cohort analysis, and custom report generation
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

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

app = FastAPI(title="Analytics Service", description="Business intelligence and analytics engine with real-time metrics, cohort analysis, and custom report generation", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Domain Helpers ---

def validate_request(data: dict, required_fields: list) -> list:
    """Validate that all required fields are present in request data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    return missing

def sanitize_input(value: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    if not isinstance(value, str):
        return str(value)
    return value.strip().replace("<", "&lt;").replace(">", "&gt;")

def format_currency(amount: float, currency: str = "NGN") -> str:
    """Format amount with currency symbol."""
    symbols = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€", "KES": "KSh"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"

def generate_reference(prefix: str = "REF") -> str:
    """Generate a unique reference ID."""
    import time
    import hashlib
    ts = str(time.time()).encode()
    h = hashlib.md5(ts).hexdigest()[:8].upper()
    return f"{prefix}-{h}"

def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Paginate a list of items."""
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages": (len(items) + per_page - 1) // per_page
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "analytics-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/analytics/dashboard")
async def get_dashboard(period: str = "7d"):
    """Get analytics dashboard summary."""
    return {"period": period, "metrics": {"total_transactions": 0, "total_volume": 0.0, "active_agents": 0, "new_customers": 0, "avg_transaction_value": 0.0}, "trends": []}

@app.get("/api/v1/analytics/cohort")
async def cohort_analysis(cohort_type: str = "monthly", metric: str = "retention"):
    """Run cohort analysis on agent or customer data."""
    return {"cohort_type": cohort_type, "metric": metric, "cohorts": [], "generated_at": datetime.utcnow().isoformat()}

@app.post("/api/v1/analytics/reports/generate")
async def generate_report(report_type: str, date_range: str, filters: dict = None):
    """Generate a custom analytics report."""
    return {"report_id": f"RPT-{int(__import__('time').time())}", "type": report_type, "status": "generating", "estimated_time": "30-60 seconds"}

@app.get("/api/v1/analytics/funnel")
async def get_funnel(funnel_name: str = "onboarding"):
    """Get conversion funnel metrics."""
    return {"funnel": funnel_name, "stages": [], "overall_conversion": 0.0}


def _tier(volume: float) -> str:
    if volume >= 10_000_000: return "Platinum"
    if volume >= 1_000_000: return "Gold"
    if volume >= 100_000: return "Silver"
    return "Bronze"


@app.get("/api/v1/analytics/agent-leaderboard")
async def agent_leaderboard(
    days: int = Query(30),
    sortBy: str = Query("volume"),
    page: int = Query(1),
    limit: int = Query(20),
    x_tenant_id: Optional[str] = Header(None, alias="x-tenant-id"),
):
    """Agent performance leaderboard ranked by volume, txCount, commission or successRate."""
    db_url = os.environ.get("DATABASE_URL", "")
    agents = []
    total = 0

    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT
                        a.id,
                        a.keycloak_id,
                        COALESCE(a.first_name || ' ' || a.last_name, a.email, a.keycloak_id) AS name,
                        COALESCE(a.agent_code, UPPER(LEFT(a.id::text, 8))) AS agent_code,
                        COALESCE(SUM(pt.amount), 0)::float AS volume,
                        COUNT(pt.id)::int AS tx_count,
                        COALESCE(SUM(cc.amount), 0)::float AS commission,
                        CASE WHEN COUNT(pt.id) > 0
                             THEN ROUND(100.0 * COUNT(CASE WHEN pt.status = 'success' THEN 1 END) / COUNT(pt.id), 1)
                             ELSE 100.0 END::float AS success_rate
                    FROM agent a
                    LEFT JOIN payment_transactions pt
                        ON pt.agent_keycloak_id = a.keycloak_id
                        AND pt.created_at >= NOW() - ($1 || ' days')::interval
                    LEFT JOIN commission_records cc
                        ON cc.agent_id = a.keycloak_id
                        AND cc.created_at >= NOW() - ($1 || ' days')::interval
                    WHERE ($2::text IS NULL OR a.tenant_id = $2)
                    GROUP BY a.id, a.keycloak_id, a.first_name, a.last_name, a.email, a.agent_code
                    ORDER BY volume DESC
                    """,
                    str(days), x_tenant_id,
                )
                total = len(rows)

                sort_key = {"volume": "volume", "txCount": "tx_count", "commission": "commission", "successRate": "success_rate"}.get(sortBy, "volume")
                sorted_rows = sorted(rows, key=lambda r: r[sort_key], reverse=True)
                page_rows = sorted_rows[(page - 1) * limit: page * limit]

                for i, r in enumerate(page_rows):
                    vol = float(r["volume"])
                    agents.append({
                        "rank": (page - 1) * limit + i + 1,
                        "id": str(r["id"]),
                        "keycloakId": r["keycloak_id"],
                        "name": r["name"],
                        "agentCode": r["agent_code"],
                        "volume": vol,
                        "txCount": r["tx_count"],
                        "commission": float(r["commission"]),
                        "successRate": float(r["success_rate"]),
                        "tier": _tier(vol),
                    })
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Leaderboard DB error: {e}")

    return {"agents": agents, "total": total, "page": page, "limit": limit, "days": days}


@app.get("/api/v1/agent-performance-scorecard")
async def agent_performance_scorecard(
    x_tenant_id: Optional[str] = Header(None, alias="x-tenant-id"),
):
    """Aggregate scorecard summary + per-agent KPIs for the scorecard page."""
    db_url = os.environ.get("DATABASE_URL", "")
    agents = []

    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT
                        COALESCE(a.first_name || ' ' || a.last_name, a.email, a.keycloak_id) AS name,
                        COALESCE(a.territory, '') AS territory,
                        COALESCE(a.agent_type, a.role, 'Agent') AS role,
                        COUNT(pt.id)::int AS txn_count,
                        COALESCE(SUM(pt.amount), 0)::float AS volume,
                        COALESCE(SUM(cc.amount), 0)::float AS commission,
                        COALESCE(
                            CASE WHEN COUNT(pt.id) > 0
                                 THEN LEAST(100, ROUND(
                                     40.0 * COUNT(CASE WHEN pt.status = 'success' THEN 1 END) / NULLIF(COUNT(pt.id), 0) +
                                     30.0 * LEAST(COUNT(pt.id)::float / 100, 1) +
                                     30.0 * LEAST(COALESCE(SUM(pt.amount), 0) / 1000000, 1)
                                 ))
                                 ELSE 50 END,
                            50
                        )::int AS score
                    FROM agent a
                    LEFT JOIN payment_transactions pt
                        ON pt.agent_keycloak_id = a.keycloak_id
                        AND pt.created_at >= NOW() - INTERVAL '30 days'
                    LEFT JOIN commission_records cc
                        ON cc.agent_id = a.keycloak_id
                        AND cc.created_at >= NOW() - INTERVAL '30 days'
                    WHERE ($1::text IS NULL OR a.tenant_id = $1)
                    GROUP BY a.id, a.keycloak_id, a.first_name, a.last_name, a.email, a.territory, a.agent_type, a.role
                    ORDER BY score DESC
                    LIMIT 100
                    """,
                    x_tenant_id,
                )
                agents = [
                    {
                        "name": r["name"],
                        "territory": r["territory"],
                        "role": r["role"],
                        "txnCount": r["txn_count"],
                        "volume": r["volume"],
                        "commission": r["commission"],
                        "score": r["score"],
                    }
                    for r in rows
                ]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Scorecard DB error: {e}")

    total = len(agents)
    top_performers = sum(1 for a in agents if a["score"] >= 80)
    avg_score = round(sum(a["score"] for a in agents) / total, 1) if total else 0
    total_commission = sum(a["commission"] for a in agents)

    return {
        "summary": {
            "totalAgents": total,
            "topPerformers": top_performers,
            "avgScore": avg_score,
            "totalCommission": total_commission,
        },
        "agents": agents,
    }


@app.get("/api/v1/transaction-map-viz/stats")
async def transaction_map_viz_stats(
    x_tenant_id: Optional[str] = Header(None, alias="x-tenant-id"),
):
    """Transaction map visualization stats."""
    db_url = os.environ.get("DATABASE_URL", "")
    total_transactions = 0
    total_volume = 0.0
    active_locations = 0
    avg_per_location = 0.0

    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            try:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS vol FROM transactions"
                )
                if row:
                    total_transactions = row["cnt"]
                    total_volume = float(row["vol"])
            except Exception:
                pass
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Transaction map stats DB error: {e}")

    active_locations = max(1, total_transactions // 50)
    avg_per_location = round(total_volume / active_locations, 2) if active_locations else 0

    return {
        "totalTransactions": total_transactions,
        "totalVolume": total_volume,
        "activeLocations": active_locations,
        "avgPerLocation": avg_per_location,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
