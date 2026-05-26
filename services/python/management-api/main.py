"""
54Link Management API Service
Unified backend API for the Management PWA.
Provides all endpoints needed by the PWA frontend with real database operations.
"""
import os
import json
import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Query, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, EmailStr
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
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

app = FastAPI(
    title="54Link Management API",
    version="14.0.0",
    description="Unified Management API for 54Link Agency Banking Platform PWA",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── DB/Cache Dependencies ──────────────────────────────────────────────────────

_db_pool: Optional[asyncpg.Pool] = None
_redis: Optional[aioredis.Redis] = None

@app.on_event("startup")
async def startup():
    global _db_pool, _redis
    try:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)
        logger.info("✅ DB pool ready")
    except Exception as e:
        logger.warning(f"DB pool failed: {e}")
    try:
        _redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        logger.info("✅ Redis ready")
    except Exception as e:
        logger.warning(f"Redis failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    if _db_pool:
        await _db_pool.close()
    if _redis:
        await _redis.close()

async def db():
    if not _db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db_pool.acquire() as conn:
        yield conn

async def cache():
    yield _redis

# ── Pydantic Models ────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    tier: str = Field(default="agent", pattern="^(agent|super_agent|master_agent|distributor)$")
    region: str
    parent_agent_id: Optional[str] = None
    address: Optional[str] = None
    bvn: Optional[str] = None
    nin: Optional[str] = None

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tier: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None

class TransactionFilter(BaseModel):
    status: Optional[str] = None
    type: Optional[str] = None
    agent_id: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

class POSTerminalCreate(BaseModel):
    terminal_id: str
    agent_id: str
    model: str
    serial_number: str
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class QRCodeGenerate(BaseModel):
    agent_id: str
    amount: Optional[float] = None
    description: Optional[str] = None
    expires_minutes: int = Field(default=30, ge=1, le=1440)
    is_dynamic: bool = True

class CommissionRule(BaseModel):
    name: str
    transaction_type: str
    rate_type: str = Field(default="percentage", pattern="^(percentage|flat)$")
    rate_value: float
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    agent_tier: Optional[str] = None

class KYCReview(BaseModel):
    application_id: str
    decision: str = Field(pattern="^(approved|rejected|pending_more_info)$")
    notes: Optional[str] = None
    reviewer_id: Optional[str] = None

class InventoryItem(BaseModel):
    name: str
    sku: str
    category: str
    quantity: int = 0
    unit_price: float
    reorder_level: int = 10
    supplier_id: Optional[str] = None

# ============================================================================
# AGENTS ENDPOINTS
# ============================================================================

@app.get("/api/v1/agents", tags=["Agents"])
async def list_agents(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, le=100),
    search: Optional[str] = None,
    tier: Optional[str] = None,
    status: Optional[str] = None,
    region: Optional[str] = None,
    conn=Depends(db),
    redis=Depends(cache),
):
    """List all agents with filtering and pagination"""
    offset = (page - 1) * limit
    conditions = ["1=1"]
    params = []
    
    if search:
        params.append(f"%{search}%")
        conditions.append(f"(a.name ILIKE ${len(params)} OR a.email ILIKE ${len(params)} OR a.agent_code ILIKE ${len(params)})")
    if tier:
        params.append(tier)
        conditions.append(f"a.tier = ${len(params)}")
    if status:
        params.append(status)
        conditions.append(f"a.status = ${len(params)}")
    if region:
        params.append(region)
        conditions.append(f"a.region = ${len(params)}")
    
    where = " AND ".join(conditions)
    
    try:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM agents a WHERE {where}", *params)
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"""SELECT a.id, a.name, a.email, a.phone, a.agent_code, a.tier, a.status,
                       a.region, a.created_at, a.last_activity,
                       COUNT(t.id) as transaction_count,
                       COALESCE(SUM(t.amount), 0) as total_volume
                FROM agents a
                LEFT JOIN transactions t ON t.agent_id = a.id AND t.created_at > NOW() - INTERVAL '30 days'
                WHERE {where}
                GROUP BY a.id ORDER BY a.created_at DESC
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": -(-total // limit),
        }
    except Exception as e:
        logger.error(f"List agents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/agents/{agent_id}", tags=["Agents"])
async def get_agent(agent_id: str = Path(...), conn=Depends(db)):
    """Get agent details"""
    try:
        row = await conn.fetchrow(
            """SELECT a.*, 
                      COUNT(t.id) as total_transactions,
                      COALESCE(SUM(t.amount), 0) as total_volume,
                      COUNT(DISTINCT c.id) as customer_count
               FROM agents a
               LEFT JOIN transactions t ON t.agent_id = a.id
               LEFT JOIN customers c ON c.agent_id = a.id
               WHERE a.id = $1
               GROUP BY a.id""",
            agent_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/agents", status_code=status.HTTP_201_CREATED, tags=["Agents"])
async def create_agent(data: AgentCreate, request: Request, conn=Depends(db)):
    """Create a new agent"""
    agent_code = f"AG{secrets.token_hex(4).upper()}"
    try:
        row = await conn.fetchrow(
            """INSERT INTO agents (name, email, phone, tier, region, agent_code, 
                                   parent_agent_id, address, bvn, nin, status, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending',$11)
               RETURNING id, name, email, agent_code, tier, status, created_at""",
            data.name, data.email, data.phone, data.tier, data.region, agent_code,
            data.parent_agent_id, data.address, data.bvn, data.nin,
            request.headers.get("X-User-ID", "system")
        )
        return {"success": True, "agent": dict(row)}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Agent with this email already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/agents/{agent_id}", tags=["Agents"])
async def update_agent(agent_id: str, data: AgentUpdate, conn=Depends(db)):
    """Update agent details"""
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    set_clauses = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(updates.keys())])
    values = [agent_id] + list(updates.values())
    
    try:
        result = await conn.execute(
            f"UPDATE agents SET {set_clauses}, updated_at = NOW() WHERE id = $1",
            *values
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"success": True, "updated_fields": list(updates.keys())}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/agents/{agent_id}", tags=["Agents"])
async def delete_agent(agent_id: str, conn=Depends(db)):
    """Deactivate an agent (soft delete)"""
    try:
        result = await conn.execute(
            "UPDATE agents SET status = 'deactivated', deactivated_at = NOW() WHERE id = $1",
            agent_id
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"success": True, "message": "Agent deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/agents/{agent_id}/hierarchy", tags=["Agents"])
async def get_agent_hierarchy(agent_id: str, conn=Depends(db)):
    """Get agent hierarchy tree"""
    try:
        rows = await conn.fetch(
            """WITH RECURSIVE hierarchy AS (
                SELECT id, name, agent_code, tier, parent_agent_id, 0 as level
                FROM agents WHERE id = $1
                UNION ALL
                SELECT a.id, a.name, a.agent_code, a.tier, a.parent_agent_id, h.level + 1
                FROM agents a JOIN hierarchy h ON a.parent_agent_id = h.id
            )
            SELECT * FROM hierarchy ORDER BY level, name""",
            agent_id
        )
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TRANSACTIONS ENDPOINTS
# ============================================================================

@app.get("/api/v1/transactions", tags=["Transactions"])
async def list_transactions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, le=100),
    status: Optional[str] = None,
    type: Optional[str] = None,
    agent_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    conn=Depends(db),
):
    """List transactions with filtering"""
    offset = (page - 1) * limit
    conditions = ["1=1"]
    params = []
    
    if status:
        params.append(status)
        conditions.append(f"t.status = ${len(params)}")
    if type:
        params.append(type)
        conditions.append(f"t.type = ${len(params)}")
    if agent_id:
        params.append(agent_id)
        conditions.append(f"t.agent_id = ${len(params)}")
    if from_date:
        params.append(from_date)
        conditions.append(f"t.created_at >= ${len(params)}")
    if to_date:
        params.append(to_date)
        conditions.append(f"t.created_at <= ${len(params)}")
    
    where = " AND ".join(conditions)
    
    try:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM transactions t WHERE {where}", *params)
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"""SELECT t.id, t.transaction_ref, t.type, t.amount, t.currency,
                       t.status, t.description, t.created_at, t.completed_at,
                       a.name as agent_name, a.agent_code,
                       c.name as customer_name, c.account_number
                FROM transactions t
                LEFT JOIN agents a ON t.agent_id = a.id
                LEFT JOIN customers c ON t.customer_id = c.id
                WHERE {where}
                ORDER BY t.created_at DESC
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/transactions/stats", tags=["Transactions"])
async def get_transaction_stats(
    period: str = Query(default="today"),
    conn=Depends(db),
    redis=Depends(cache),
):
    """Get transaction statistics"""
    cache_key = f"txn:stats:{period}"
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    
    since_map = {
        "today": timedelta(days=1),
        "week": timedelta(weeks=1),
        "month": timedelta(days=30),
    }
    since = datetime.utcnow() - since_map.get(period, timedelta(days=1))
    
    try:
        stats = await conn.fetchrow(
            """SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COALESCE(SUM(amount) FILTER (WHERE status = 'completed'), 0) as total_volume,
                COALESCE(AVG(amount) FILTER (WHERE status = 'completed'), 0) as avg_amount
               FROM transactions WHERE created_at > $1""",
            since
        )
        result = dict(stats)
        if redis:
            await redis.setex(cache_key, 30, json.dumps(result, default=str))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/transactions/{transaction_id}", tags=["Transactions"])
async def get_transaction(transaction_id: str, conn=Depends(db)):
    """Get transaction details"""
    try:
        row = await conn.fetchrow(
            """SELECT t.*, a.name as agent_name, c.name as customer_name
               FROM transactions t
               LEFT JOIN agents a ON t.agent_id = a.id
               LEFT JOIN customers c ON t.customer_id = c.id
               WHERE t.id = $1 OR t.transaction_ref = $1""",
            transaction_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POS TERMINALS ENDPOINTS
# ============================================================================

@app.get("/api/v1/pos/terminals", tags=["POS"])
async def list_pos_terminals(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    conn=Depends(db),
):
    """List POS terminals"""
    offset = (page - 1) * limit
    conditions = ["1=1"]
    params = []
    
    if status:
        params.append(status)
        conditions.append(f"p.status = ${len(params)}")
    if agent_id:
        params.append(agent_id)
        conditions.append(f"p.agent_id = ${len(params)}")
    
    where = " AND ".join(conditions)
    params.extend([limit, offset])
    
    try:
        rows = await conn.fetch(
            f"""SELECT p.id, p.terminal_id, p.model, p.serial_number, p.status,
                       p.location, p.latitude, p.longitude, p.last_seen,
                       a.name as agent_name, a.agent_code
                FROM pos_terminals p
                LEFT JOIN agents a ON p.agent_id = a.id
                WHERE {where}
                ORDER BY p.last_seen DESC NULLS LAST
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM pos_terminals p WHERE {where}", *params[:-2])
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/pos/terminals", status_code=201, tags=["POS"])
async def create_pos_terminal(data: POSTerminalCreate, conn=Depends(db)):
    """Register a new POS terminal"""
    try:
        row = await conn.fetchrow(
            """INSERT INTO pos_terminals (terminal_id, agent_id, model, serial_number, 
                                          location, latitude, longitude, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,'inactive')
               RETURNING id, terminal_id, model, status, created_at""",
            data.terminal_id, data.agent_id, data.model, data.serial_number,
            data.location, data.latitude, data.longitude
        )
        return {"success": True, "terminal": dict(row)}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Terminal ID already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pos/status", tags=["POS"])
async def get_pos_status(conn=Depends(db)):
    """Get POS fleet status summary"""
    try:
        row = await conn.fetchrow(
            """SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'active') as active,
                COUNT(*) FILTER (WHERE status = 'inactive') as inactive,
                COUNT(*) FILTER (WHERE status = 'maintenance') as maintenance,
                COUNT(*) FILTER (WHERE last_seen > NOW() - INTERVAL '5 minutes') as online
               FROM pos_terminals"""
        )
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# QR CODES ENDPOINTS
# ============================================================================

@app.get("/api/v1/qr-codes", tags=["QR Codes"])
async def list_qr_codes(
    page: int = 1,
    limit: int = 20,
    agent_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    conn=Depends(db),
):
    """List QR codes"""
    offset = (page - 1) * limit
    conditions = ["1=1"]
    params = []
    
    if agent_id:
        params.append(agent_id)
        conditions.append(f"q.agent_id = ${len(params)}")
    if is_active is not None:
        params.append(is_active)
        conditions.append(f"q.is_active = ${len(params)}")
    
    where = " AND ".join(conditions)
    params.extend([limit, offset])
    
    try:
        rows = await conn.fetch(
            f"""SELECT q.id, q.code, q.agent_id, q.amount, q.description,
                       q.is_active, q.scan_count, q.expires_at, q.created_at,
                       a.name as agent_name
                FROM qr_codes q
                LEFT JOIN agents a ON q.agent_id = a.id
                WHERE {where}
                ORDER BY q.created_at DESC
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM qr_codes q WHERE {where}", *params[:-2])
        return {"items": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/qr-codes/generate", status_code=201, tags=["QR Codes"])
async def generate_qr_code(data: QRCodeGenerate, conn=Depends(db)):
    """Generate a new QR code"""
    import uuid
    import qrcode
    import io
    import base64
    
    code = str(uuid.uuid4()).replace("-", "")[:16].upper()
    expires_at = datetime.utcnow() + timedelta(minutes=data.expires_minutes)
    
    try:
        # Generate QR image
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr_data = json.dumps({
            "code": code,
            "agent_id": data.agent_id,
            "amount": data.amount,
            "platform": "54link",
        })
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_image_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        row = await conn.fetchrow(
            """INSERT INTO qr_codes (code, agent_id, amount, description, is_dynamic, expires_at)
               VALUES ($1,$2,$3,$4,$5,$6)
               RETURNING id, code, agent_id, amount, expires_at, created_at""",
            code, data.agent_id, data.amount, data.description, data.is_dynamic, expires_at
        )
        return {
            "success": True,
            "qr_code": dict(row),
            "qr_image": f"data:image/png;base64,{qr_image_b64}",
        }
    except Exception as e:
        # Fallback without QR image
        try:
            row = await conn.fetchrow(
                """INSERT INTO qr_codes (code, agent_id, amount, description, is_dynamic, expires_at)
                   VALUES ($1,$2,$3,$4,$5,$6)
                   RETURNING id, code, agent_id, amount, expires_at, created_at""",
                code, data.agent_id, data.amount, data.description, data.is_dynamic, expires_at
            )
            return {"success": True, "qr_code": dict(row)}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))


@app.post("/api/v1/qr-codes/validate", tags=["QR Codes"])
async def validate_qr_code(code: str, conn=Depends(db)):
    """Validate a QR code"""
    try:
        row = await conn.fetchrow(
            """SELECT q.*, a.name as agent_name
               FROM qr_codes q
               LEFT JOIN agents a ON q.agent_id = a.id
               WHERE q.code = $1""",
            code
        )
        if not row:
            return {"valid": False, "reason": "QR code not found"}
        
        qr = dict(row)
        if not qr["is_active"]:
            return {"valid": False, "reason": "QR code is inactive"}
        if qr["expires_at"] and qr["expires_at"] < datetime.utcnow():
            return {"valid": False, "reason": "QR code has expired"}
        
        # Increment scan count
        await conn.execute("UPDATE qr_codes SET scan_count = scan_count + 1 WHERE code = $1", code)
        
        return {"valid": True, "qr_code": qr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/qr-codes/stats", tags=["QR Codes"])
async def get_qr_stats(conn=Depends(db)):
    """Get QR code statistics"""
    try:
        row = await conn.fetchrow(
            """SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = true) as active,
                COUNT(*) FILTER (WHERE expires_at < NOW()) as expired,
                COALESCE(SUM(scan_count), 0) as total_scans
               FROM qr_codes"""
        )
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# COMMISSIONS ENDPOINTS
# ============================================================================

@app.get("/api/v1/commissions", tags=["Commissions"])
async def list_commissions(
    agent_id: Optional[str] = None,
    period: str = Query(default="month"),
    page: int = 1,
    limit: int = 20,
    conn=Depends(db),
):
    """List commission records"""
    offset = (page - 1) * limit
    since = datetime.utcnow() - timedelta(days=30 if period == "month" else 7)
    
    conditions = ["c.created_at > $1"]
    params = [since]
    
    if agent_id:
        params.append(agent_id)
        conditions.append(f"c.agent_id = ${len(params)}")
    
    where = " AND ".join(conditions)
    params.extend([limit, offset])
    
    try:
        rows = await conn.fetch(
            f"""SELECT c.id, c.agent_id, c.transaction_id, c.commission_type,
                       c.amount, c.rate, c.status, c.created_at, c.paid_at,
                       a.name as agent_name, a.agent_code
                FROM commissions c
                LEFT JOIN agents a ON c.agent_id = a.id
                WHERE {where}
                ORDER BY c.created_at DESC
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM commissions c WHERE {where}", *params[:-2])
        return {"items": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/commissions/rules", tags=["Commissions"])
async def list_commission_rules(conn=Depends(db)):
    """List commission rules"""
    try:
        rows = await conn.fetch("SELECT * FROM commission_rules WHERE is_active = true ORDER BY created_at DESC")
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/commissions/rules", status_code=201, tags=["Commissions"])
async def create_commission_rule(data: CommissionRule, conn=Depends(db)):
    """Create a commission rule"""
    try:
        row = await conn.fetchrow(
            """INSERT INTO commission_rules (name, transaction_type, rate_type, rate_value, 
                                             min_amount, max_amount, agent_tier)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               RETURNING id, name, transaction_type, rate_type, rate_value, created_at""",
            data.name, data.transaction_type, data.rate_type, data.rate_value,
            data.min_amount, data.max_amount, data.agent_tier
        )
        return {"success": True, "rule": dict(row)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/commissions/rules/{rule_id}", tags=["Commissions"])
async def update_commission_rule(rule_id: str, data: CommissionRule, conn=Depends(db)):
    """Update a commission rule"""
    try:
        await conn.execute(
            """UPDATE commission_rules SET name=$2, transaction_type=$3, rate_type=$4,
               rate_value=$5, min_amount=$6, max_amount=$7, agent_tier=$8, updated_at=NOW()
               WHERE id=$1""",
            rule_id, data.name, data.transaction_type, data.rate_type, data.rate_value,
            data.min_amount, data.max_amount, data.agent_tier
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/commissions/rules/{rule_id}", tags=["Commissions"])
async def delete_commission_rule(rule_id: str, conn=Depends(db)):
    """Delete (deactivate) a commission rule"""
    try:
        await conn.execute("UPDATE commission_rules SET is_active=false WHERE id=$1", rule_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# KYC MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/kyc/applications", tags=["KYC"])
async def list_kyc_applications(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    conn=Depends(db),
):
    """List KYC applications"""
    offset = (page - 1) * limit
    conditions = ["1=1"]
    params = []
    
    if status:
        params.append(status)
        conditions.append(f"k.status = ${len(params)}")
    
    where = " AND ".join(conditions)
    params.extend([limit, offset])
    
    try:
        rows = await conn.fetch(
            f"""SELECT k.id, k.customer_id, k.status, k.tier, k.submitted_at,
                       k.reviewed_at, k.reviewer_id, k.rejection_reason,
                       c.name as customer_name, c.phone, c.email
                FROM kyc_applications k
                LEFT JOIN customers c ON k.customer_id = c.id
                WHERE {where}
                ORDER BY k.submitted_at DESC
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM kyc_applications k WHERE {where}", *params[:-2])
        return {"items": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/kyc/applications/{application_id}/review", tags=["KYC"])
async def review_kyc_application(application_id: str, data: KYCReview, conn=Depends(db)):
    """Review a KYC application"""
    try:
        await conn.execute(
            """UPDATE kyc_applications 
               SET status=$2, reviewer_id=$3, reviewed_at=NOW(), 
                   rejection_reason=CASE WHEN $2='rejected' THEN $4 ELSE NULL END
               WHERE id=$1""",
            application_id, data.decision, data.reviewer_id, data.notes
        )
        return {"success": True, "decision": data.decision}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@app.get("/api/v1/analytics/overview", tags=["Analytics"])
async def get_analytics_overview(
    period: str = Query(default="month"),
    conn=Depends(db),
    redis=Depends(cache),
):
    """Get analytics overview"""
    cache_key = f"analytics:overview:{period}"
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    
    days = {"today": 1, "week": 7, "month": 30, "year": 365}.get(period, 30)
    since = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Transaction breakdown by type
        type_breakdown = await conn.fetch(
            """SELECT type, COUNT(*) as count, COALESCE(SUM(amount), 0) as volume
               FROM transactions WHERE created_at > $1 AND status = 'completed'
               GROUP BY type ORDER BY volume DESC""",
            since
        )
        
        # Daily trend
        daily_trend = await conn.fetch(
            """SELECT DATE(created_at) as date, COUNT(*) as transactions, 
                      COALESCE(SUM(amount), 0) as volume
               FROM transactions WHERE created_at > $1
               GROUP BY DATE(created_at) ORDER BY date""",
            since
        )
        
        # Agent performance
        agent_perf = await conn.fetch(
            """SELECT a.tier, COUNT(DISTINCT a.id) as agent_count,
                      COUNT(t.id) as transaction_count,
                      COALESCE(SUM(t.amount), 0) as volume
               FROM agents a
               LEFT JOIN transactions t ON t.agent_id = a.id AND t.created_at > $1
               GROUP BY a.tier ORDER BY volume DESC""",
            since
        )
        
        result = {
            "period": period,
            "transaction_types": [dict(r) for r in type_breakdown],
            "daily_trend": [dict(r) for r in daily_trend],
            "agent_performance": [dict(r) for r in agent_perf],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if redis:
            await redis.setex(cache_key, 300, json.dumps(result, default=str))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# INVENTORY ENDPOINTS
# ============================================================================

@app.get("/api/v1/inventory", tags=["Inventory"])
async def list_inventory(
    category: Optional[str] = None,
    low_stock: bool = False,
    page: int = 1,
    limit: int = 20,
    conn=Depends(db),
):
    """List inventory items"""
    offset = (page - 1) * limit
    conditions = ["1=1"]
    params = []
    
    if category:
        params.append(category)
        conditions.append(f"i.category = ${len(params)}")
    if low_stock:
        conditions.append("i.quantity <= i.reorder_level")
    
    where = " AND ".join(conditions)
    params.extend([limit, offset])
    
    try:
        rows = await conn.fetch(
            f"""SELECT i.id, i.name, i.sku, i.category, i.quantity, i.unit_price,
                       i.reorder_level, i.last_restocked, i.created_at
                FROM inventory_items i
                WHERE {where}
                ORDER BY i.name
                LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM inventory_items i WHERE {where}", *params[:-2])
        return {"items": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/inventory", status_code=201, tags=["Inventory"])
async def create_inventory_item(data: InventoryItem, conn=Depends(db)):
    """Create inventory item"""
    try:
        row = await conn.fetchrow(
            """INSERT INTO inventory_items (name, sku, category, quantity, unit_price, reorder_level, supplier_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               RETURNING id, name, sku, category, quantity, created_at""",
            data.name, data.sku, data.category, data.quantity, data.unit_price,
            data.reorder_level, data.supplier_id
        )
        return {"success": True, "item": dict(row)}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="SKU already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/inventory/{item_id}", tags=["Inventory"])
async def update_inventory_item(item_id: str, data: InventoryItem, conn=Depends(db)):
    """Update inventory item"""
    try:
        await conn.execute(
            """UPDATE inventory_items SET name=$2, sku=$3, category=$4, quantity=$5,
               unit_price=$6, reorder_level=$7, updated_at=NOW() WHERE id=$1""",
            item_id, data.name, data.sku, data.category, data.quantity,
            data.unit_price, data.reorder_level
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/inventory/{item_id}", tags=["Inventory"])
async def delete_inventory_item(item_id: str, conn=Depends(db)):
    """Delete inventory item"""
    try:
        await conn.execute("DELETE FROM inventory_items WHERE id=$1", item_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SYSTEM HEALTH ENDPOINTS
# ============================================================================

@app.get("/api/v1/system/health", tags=["System"])
async def get_system_health(conn=Depends(db), redis=Depends(cache)):
    """Get comprehensive system health"""
    services = {}
    
    # Database
    try:
        await conn.fetchval("SELECT 1")
        services["database"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        services["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Redis
    try:
        if redis:
            await redis.ping()
            services["redis"] = {"status": "healthy"}
        else:
            services["redis"] = {"status": "not_configured"}
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "error": str(e)}
    
    # External services (check env vars)
    for svc, env_var in [
        ("kafka", "KAFKA_BOOTSTRAP_SERVERS"),
        ("temporal", "TEMPORAL_HOST"),
        ("keycloak", "KEYCLOAK_URL"),
        ("tigerbeetle", "TIGERBEETLE_ADDRESS"),
    ]:
        services[svc] = {
            "status": "configured" if os.getenv(env_var) else "not_configured",
            "endpoint": os.getenv(env_var, "not_set"),
        }
    
    overall = "healthy" if all(
        v.get("status") in ("healthy", "configured", "not_configured")
        for v in services.values()
    ) else "degraded"
    
    return {
        "overall": overall,
        "services": services,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "14.0.0",
        "environment": ENVIRONMENT,
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
