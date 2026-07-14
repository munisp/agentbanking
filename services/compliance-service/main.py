"""
Compliance Service
Port: 8116
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

app = FastAPI(title="Compliance Service", description="Compliance Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS compliance_checks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                check_type VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                risk_level VARCHAR(20) DEFAULT 'low',
                details JSONB DEFAULT '{}',
                reviewer_id VARCHAR(255),
                reviewed_at TIMESTAMPTZ,
                expires_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS compliance_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                rule_name VARCHAR(100) NOT NULL,
                rule_type VARCHAR(50) NOT NULL,
                conditions JSONB NOT NULL,
                action VARCHAR(50) DEFAULT 'flag',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_comp_user ON compliance_checks(user_id);
            CREATE INDEX IF NOT EXISTS idx_comp_status ON compliance_checks(status)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "compliance-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "compliance-service", "error": str(e)}


class ComplianceCheckCreate(BaseModel):
    user_id: str
    check_type: str
    details: Optional[Dict[str, Any]] = None

class ComplianceRuleCreate(BaseModel):
    rule_name: str
    rule_type: str
    conditions: Dict[str, Any]
    action: str = "flag"

@app.post("/api/v1/compliance/checks")
async def create_check(check: ComplianceCheckCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        risk = "low"
        if check.details:
            amount = check.details.get("amount", 0)
            if amount > 1000000:
                risk = "high"
            elif amount > 100000:
                risk = "medium"
        row = await conn.fetchrow(
            """INSERT INTO compliance_checks (user_id, check_type, risk_level, details)
               VALUES ($1,$2,$3,$4) RETURNING *""",
            check.user_id, check.check_type, risk, json.dumps(check.details or {})
        )
        return dict(row)

@app.get("/api/v1/compliance/checks")
async def list_checks(user_id: Optional[str] = None, status: Optional[str] = None,
                      risk_level: Optional[str] = None, skip: int = 0, limit: int = 50,
                      token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conditions, params = [], []
        idx = 1
        if user_id:
            conditions.append(f"user_id=${idx}"); params.append(user_id); idx += 1
        if status:
            conditions.append(f"status=${idx}"); params.append(status); idx += 1
        if risk_level:
            conditions.append(f"risk_level=${idx}"); params.append(risk_level); idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([limit, skip])
        rows = await conn.fetch(f"SELECT * FROM compliance_checks {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}", *params)
        return {"checks": [dict(r) for r in rows]}

@app.put("/api/v1/compliance/checks/{check_id}/review")
async def review_check(check_id: str, status: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE compliance_checks SET status=$1, reviewer_id=$2, reviewed_at=NOW() WHERE id=$3 RETURNING *",
            status, token[:36], uuid.UUID(check_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Check not found")
        return dict(row)

@app.post("/api/v1/compliance/rules")
async def create_rule(rule: ComplianceRuleCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO compliance_rules (rule_name, rule_type, conditions, action) VALUES ($1,$2,$3,$4) RETURNING *",
            rule.rule_name, rule.rule_type, json.dumps(rule.conditions), rule.action
        )
        return dict(row)

@app.get("/api/v1/compliance/rules")
async def list_rules(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM compliance_rules WHERE is_active=TRUE ORDER BY rule_name")
        return {"rules": [dict(r) for r in rows]}

@app.get("/v1/compliance/alerts")
async def list_alerts(risk_level: Optional[str] = None, skip: int = 0, limit: int = 50,
                      token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if risk_level:
            rows = await conn.fetch(
                "SELECT * FROM compliance_checks WHERE status IN ('flagged','blocked') AND risk_level=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                risk_level, limit, skip
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM compliance_checks WHERE status IN ('flagged','blocked') ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, skip
            )
        return {"alerts": [dict(r) for r in rows], "total": len(rows)}

@app.post("/api/v1/compliance/screen-transaction")
async def screen_transaction(data: Dict[str, Any], token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rules = await conn.fetch("SELECT * FROM compliance_rules WHERE is_active=TRUE")
        flags = []
        for rule in rules:
            conditions = json.loads(rule["conditions"]) if isinstance(rule["conditions"], str) else rule["conditions"]
            for field, threshold in conditions.items():
                val = data.get(field)
                if val is not None and isinstance(threshold, (int, float)) and isinstance(val, (int, float)) and val > threshold:
                    flags.append({"rule": rule["rule_name"], "action": rule["action"], "field": field, "value": val, "threshold": threshold})
        status = "blocked" if any(f["action"] == "block" for f in flags) else "flagged" if flags else "approved"
        return {"status": status, "flags": flags, "checked_rules": len(rules)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("APP_PORT", "8116")))
    uvicorn.run(app, host="0.0.0.0", port=port)
