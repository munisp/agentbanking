"""
Commission Service
Port: 8114
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import os
import json
import asyncpg
import uvicorn

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


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://remittance:remittance@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

app = FastAPI(title="Commission Service", description="Commission Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS commission_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                corridor VARCHAR(20) NOT NULL DEFAULT '',
                currency_from VARCHAR(3) NOT NULL,
                currency_to VARCHAR(3) NOT NULL,
                min_amount DECIMAL(18,2) DEFAULT 0,
                max_amount DECIMAL(18,2) DEFAULT 999999999,
                fee_type VARCHAR(10) DEFAULT 'percentage',
                fee_value DECIMAL(10,4) NOT NULL,
                flat_fee DECIMAL(18,2) DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS commission_transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                transaction_id VARCHAR(255) NOT NULL,
                rule_id UUID REFERENCES commission_rules(id),
                amount DECIMAL(18,2) NOT NULL,
                fee_amount DECIMAL(18,2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                calculated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS commission_settlements (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                agent_id VARCHAR(255),
                period_start TIMESTAMPTZ,
                period_end TIMESTAMPTZ,
                total_commissions DECIMAL(18,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                settled_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS commission_policy (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                config JSONB DEFAULT '{}',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_comm_corridor ON commission_rules(corridor, is_active);
            CREATE TABLE IF NOT EXISTS commission_clawbacks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                agent_id VARCHAR(255) NOT NULL,
                agent_name VARCHAR(255) NOT NULL DEFAULT '',
                reason VARCHAR(50) NOT NULL DEFAULT 'reversal',
                amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                original_commission_date DATE,
                status VARCHAR(30) NOT NULL DEFAULT 'pending_approval',
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_clawbacks_agent ON commission_clawbacks(agent_id);
            CREATE INDEX IF NOT EXISTS idx_clawbacks_status ON commission_clawbacks(status)
        """)
        await conn.execute("""
            ALTER TABLE commission_transactions ADD COLUMN IF NOT EXISTS agent_id VARCHAR(255);
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS fee_type VARCHAR(10) DEFAULT 'percentage';
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS flat_fee DECIMAL(18,2) DEFAULT 0;
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS min_amount DECIMAL(18,2) DEFAULT 0;
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS max_amount DECIMAL(18,2) DEFAULT 999999999;
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS currency_from VARCHAR(3);
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS currency_to VARCHAR(3);
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS fee_value DECIMAL(10,4) DEFAULT 0;
            ALTER TABLE commission_rules ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "commission-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "commission-service", "error": str(e)}


class CommissionRuleCreate(BaseModel):
    corridor: str
    currency_from: str
    currency_to: str
    min_amount: float = 0
    max_amount: float = 999999999
    fee_type: str = "percentage"
    fee_value: float
    flat_fee: float = 0

class FeeCalculationRequest(BaseModel):
    amount: float
    corridor: str
    currency_from: str
    currency_to: str
    transaction_id: Optional[str] = None

@app.post("/api/v1/commissions/rules")
async def create_rule(rule: CommissionRuleCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO commission_rules (corridor, currency_from, currency_to, min_amount, max_amount, fee_type, fee_value, flat_fee)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
            rule.corridor, rule.currency_from, rule.currency_to, rule.min_amount,
            rule.max_amount, rule.fee_type, rule.fee_value, rule.flat_fee
        )
        return dict(row)

@app.get("/api/v1/commissions/rules")
async def list_rules(corridor: Optional[str] = None, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if corridor:
            rows = await conn.fetch("SELECT * FROM commission_rules WHERE corridor=$1 AND is_active=TRUE ORDER BY min_amount", corridor)
        else:
            rows = await conn.fetch("SELECT * FROM commission_rules WHERE is_active=TRUE ORDER BY corridor, min_amount")
        return {"rules": [dict(r) for r in rows]}

@app.post("/api/v1/commissions/calculate")
async def calculate_fee(req: FeeCalculationRequest, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rule = await conn.fetchrow(
            """SELECT * FROM commission_rules WHERE corridor=$1 AND currency_from=$2 AND currency_to=$3
               AND min_amount <= $4 AND max_amount >= $4 AND is_active=TRUE ORDER BY fee_value ASC LIMIT 1""",
            req.corridor, req.currency_from, req.currency_to, req.amount
        )
        if not rule:
            raise HTTPException(status_code=404, detail="No commission rule found for this corridor and amount")
        if rule["fee_type"] == "percentage":
            fee = round(req.amount * float(rule["fee_value"]) / 100, 2)
        else:
            fee = float(rule["fee_value"])
        fee += float(rule["flat_fee"])
        total = req.amount + fee
        if req.transaction_id:
            await conn.execute(
                "INSERT INTO commission_transactions (transaction_id, rule_id, amount, fee_amount, currency) VALUES ($1,$2,$3,$4,$5)",
                req.transaction_id, rule["id"], req.amount, fee, req.currency_from
            )
        return {"amount": req.amount, "fee": fee, "total": total, "fee_type": rule["fee_type"],
                "fee_rate": float(rule["fee_value"]), "flat_fee": float(rule["flat_fee"]), "corridor": req.corridor}

@app.get("/api/v1/commissions/stats")
async def commission_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COALESCE(SUM(fee_amount), 0) FROM commission_transactions")
        count = await conn.fetchval("SELECT COUNT(*) FROM commission_transactions")
        by_corridor = await conn.fetch(
            """SELECT r.corridor, COUNT(*) as txn_count, SUM(ct.fee_amount) as total_fees
               FROM commission_transactions ct JOIN commission_rules r ON ct.rule_id=r.id
               GROUP BY r.corridor ORDER BY total_fees DESC"""
        )
        return {"total_fees_collected": float(total), "total_transactions": count, "by_corridor": [dict(r) for r in by_corridor]}


@app.get("/api/v1/commissions")
async def list_commissions(
    page: int = 1, limit: int = 50,
    agent_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    token: str = Depends(verify_token)
):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    conditions = []
    params = []
    if agent_id:
        params.append(agent_id)
        conditions.append(f"agent_id = ${len(params)}")
    if start_date:
        params.append(datetime.strptime(start_date, "%Y-%m-%d"))
        conditions.append(f"calculated_at >= ${len(params)}")
    if end_date:
        params.append(datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
        conditions.append(f"calculated_at < ${len(params)}")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    filter_params = list(params)
    params.extend([limit, offset])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM commission_transactions {where} ORDER BY calculated_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM commission_transactions {where}", *filter_params)
        return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}

@app.get("/api/v1/commission-rules")
async def list_commission_rules(active_only: bool = True, page: int = 1, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    async with pool.acquire() as conn:
        where = "WHERE is_active=TRUE" if active_only else ""
        rows = await conn.fetch(f"SELECT * FROM commission_rules {where} ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, offset)
        total = await conn.fetchval(f"SELECT COUNT(*) FROM commission_rules {where}")
        return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}

@app.post("/api/v1/commission-rules")
async def create_commission_rule(rule: CommissionRuleCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO commission_rules (corridor, currency_from, currency_to, min_amount, max_amount, fee_type, fee_value, flat_fee)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
            rule.corridor, rule.currency_from, rule.currency_to, rule.min_amount,
            rule.max_amount, rule.fee_type, rule.fee_value, rule.flat_fee
        )
        return dict(row)

@app.get("/api/v1/settlements")
async def list_settlements(
    page: int = 1, limit: int = 50,
    agent_id: Optional[str] = None,
    token: str = Depends(verify_token)
):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    async with pool.acquire() as conn:
        if agent_id:
            rows = await conn.fetch(
                "SELECT * FROM commission_settlements WHERE agent_id=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                agent_id, limit, offset
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM commission_settlements WHERE agent_id=$1", agent_id)
        else:
            rows = await conn.fetch("SELECT * FROM commission_settlements ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, offset)
            total = await conn.fetchval("SELECT COUNT(*) FROM commission_settlements")
        return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}

@app.get("/api/v1/agents/{agent_id}/balance")
async def get_agent_balance(agent_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total_earned = await conn.fetchval(
            "SELECT COALESCE(SUM(fee_amount), 0) FROM commission_transactions WHERE agent_id=$1",
            agent_id
        )
        total_settled = await conn.fetchval(
            "SELECT COALESCE(SUM(total_commissions), 0) FROM commission_settlements WHERE agent_id=$1 AND status='settled'",
            agent_id
        )
        pending = await conn.fetchval(
            "SELECT COALESCE(SUM(total_commissions), 0) FROM commission_settlements WHERE agent_id=$1 AND status='pending'",
            agent_id
        )
        available = float(total_earned) - float(total_settled)
        return {
            "agent_id": agent_id,
            "total_earned": float(total_earned),
            "total_settled": float(total_settled),
            "pending_settlement": float(pending),
            "available_balance": available,
            "currency": "NGN"
        }

@app.get("/api/v1/agents")
async def list_agents(page: int = 1, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT agent_id, COUNT(*) as transaction_count, COALESCE(SUM(fee_amount), 0) as total_commissions
               FROM commission_transactions GROUP BY agent_id ORDER BY total_commissions DESC LIMIT $1 OFFSET $2""",
            limit, offset
        )
        total = await conn.fetchval("SELECT COUNT(DISTINCT agent_id) FROM commission_transactions")
        return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}

@app.get("/api/v1/agents/leaderboard")
async def get_agent_leaderboard(
    days: int = 30,
    sort_by: str = "volume",
    page: int = 1,
    limit: int = 50,
    token: str = Depends(verify_token),
):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    order_col = {
        "volume": "total_volume",
        "commissions": "total_commissions",
        "transactions": "transaction_count",
    }.get(sort_by, "total_volume")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                agent_id,
                COUNT(*) AS transaction_count,
                COALESCE(SUM(amount), 0) AS total_volume,
                COALESCE(SUM(fee_amount), 0) AS total_commissions
            FROM commission_transactions
            WHERE calculated_at >= NOW() - INTERVAL '{days} days'
              AND agent_id IS NOT NULL
            GROUP BY agent_id
            ORDER BY {order_col} DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        total = await conn.fetchval(
            "SELECT COUNT(DISTINCT agent_id) FROM commission_transactions "
            "WHERE calculated_at >= NOW() - ($1 || ' days')::interval AND agent_id IS NOT NULL",
            str(days),
        )
        data = [
            {
                "rank": offset + i + 1,
                "agent_id": r["agent_id"],
                "transaction_count": int(r["transaction_count"]),
                "total_volume": float(r["total_volume"]),
                "total_commissions": float(r["total_commissions"]),
                "currency": "NGN",
            }
            for i, r in enumerate(rows)
        ]
        return {"data": data, "total": int(total or 0), "page": page, "limit": limit, "days": days}

@app.get("/api/v1/policy")
async def get_policy(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM commission_policy WHERE is_active=TRUE ORDER BY created_at DESC LIMIT 1")
        if not row:
            return {"id": None, "name": "Default Policy", "description": "No policy configured", "config": {}, "is_active": True}
        return dict(row)


class ClawbackCreate(BaseModel):
    agent_id: str
    agent_name: str
    reason: str = "reversal"
    amount: float
    original_commission_date: Optional[str] = None
    notes: Optional[str] = None

def _row_to_clawback(r: dict) -> dict:
    out = dict(r)
    for k in ("amount",):
        if k in out and out[k] is not None:
            out[k] = float(out[k])
    for k in ("created_at", "updated_at"):
        if k in out and out[k] is not None:
            out[k] = out[k].isoformat() if hasattr(out[k], "isoformat") else str(out[k])
    if "original_commission_date" in out and out["original_commission_date"] is not None:
        out["original_commission_date"] = str(out["original_commission_date"])
    if "id" in out:
        out["id"] = str(out["id"])
    return out

@app.get("/api/v1/clawbacks")
async def list_clawbacks(
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    token: str = Depends(verify_token),
):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    conditions, params = [], []
    if status:
        params.append(status); conditions.append(f"status = ${len(params)}")
    if agent_id:
        params.append(agent_id); conditions.append(f"agent_id = ${len(params)}")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    filter_params = list(params)
    params.extend([limit, offset])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM commission_clawbacks {where} ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM commission_clawbacks {where}", *filter_params)
        cases = [_row_to_clawback(dict(r)) for r in rows]
        return {"cases": cases, "total": total, "page": page, "limit": limit}

@app.post("/api/v1/clawbacks", status_code=201)
async def create_clawback(body: ClawbackCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    orig_date = None
    if body.original_commission_date:
        try:
            from datetime import date
            orig_date = date.fromisoformat(body.original_commission_date)
        except ValueError:
            pass
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO commission_clawbacks
               (agent_id, agent_name, reason, amount, original_commission_date, status, notes)
               VALUES ($1,$2,$3,$4,$5,'pending_approval',$6) RETURNING *""",
            body.agent_id, body.agent_name, body.reason, body.amount, orig_date, body.notes,
        )
        return _row_to_clawback(dict(row))

@app.post("/api/v1/clawbacks/{clawback_id}/approve")
async def approve_clawback(clawback_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM commission_clawbacks WHERE id=$1", clawback_id)
        if not row:
            raise HTTPException(status_code=404, detail="Clawback not found")
        if row["status"] != "pending_approval":
            raise HTTPException(status_code=400, detail=f"Cannot approve clawback with status '{row['status']}'")
        updated = await conn.fetchrow(
            "UPDATE commission_clawbacks SET status='approved', updated_at=NOW() WHERE id=$1 RETURNING *",
            clawback_id,
        )
        return _row_to_clawback(dict(updated))

@app.post("/api/v1/clawbacks/{clawback_id}/execute")
async def execute_clawback(clawback_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM commission_clawbacks WHERE id=$1", clawback_id)
        if not row:
            raise HTTPException(status_code=404, detail="Clawback not found")
        if row["status"] != "approved":
            raise HTTPException(status_code=400, detail=f"Cannot execute clawback with status '{row['status']}'")
        updated = await conn.fetchrow(
            "UPDATE commission_clawbacks SET status='executed', updated_at=NOW() WHERE id=$1 RETURNING *",
            clawback_id,
        )
        return _row_to_clawback(dict(updated))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8114)
