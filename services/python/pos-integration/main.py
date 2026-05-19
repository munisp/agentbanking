"""
POS Integration Gateway
Port: 8126
Delegates to pos_service.py (core POS) and integrates with
transaction-scoring, chart-of-accounts, projections-targets,
qr-ticket-verification, and inventory-management services.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import os
import json
import asyncpg
import httpx
import uvicorn
import logging
import time as _time
from collections import defaultdict

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://remittance:remittance@localhost:5432/remittance")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
POS_CORE_URL = os.getenv("POS_CORE_URL", "http://localhost:8016")
TIGERBEETLE_SYNC_URL = os.getenv("TIGERBEETLE_SYNC_URL", "http://localhost:8085")
POS_MGMT_URL = os.getenv("POS_MGMT_URL", "http://localhost:8443")

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


app = FastAPI(
    title="POS Integration Gateway",
    description="POS Integration Gateway with scoring, COA, targets, QR tickets & inventory",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stats = {"total_requests": 0, "start_time": datetime.utcnow()}

RATE_LIMIT_MAX = int(os.getenv("POS_RATE_LIMIT_MAX", "60"))
RATE_LIMIT_WINDOW_SEC = int(os.getenv("POS_RATE_LIMIT_WINDOW_SEC", "60"))
_agent_requests: Dict[str, list] = defaultdict(list)
_rate_limit_stats = {"blocked": 0, "total_checked": 0}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    agent_id = request.headers.get("X-Agent-ID", "")
    if agent_id:
        _rate_limit_stats["total_checked"] += 1
        now = _time.time()
        cutoff = now - RATE_LIMIT_WINDOW_SEC
        _agent_requests[agent_id] = [t for t in _agent_requests[agent_id] if t > cutoff]
        if len(_agent_requests[agent_id]) >= RATE_LIMIT_MAX:
            _rate_limit_stats["blocked"] += 1
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "agent_id": agent_id, "limit": RATE_LIMIT_MAX, "window_sec": RATE_LIMIT_WINDOW_SEC},
            )
        _agent_requests[agent_id].append(now)
    response = await call_next(request)
    return response


@app.get("/rate-limit/stats")
async def get_rate_limit_stats():
    return {
        "max_per_window": RATE_LIMIT_MAX,
        "window_sec": RATE_LIMIT_WINDOW_SEC,
        "agents_tracked": len(_agent_requests),
        "total_checked": _rate_limit_stats["total_checked"],
        "total_blocked": _rate_limit_stats["blocked"],
    }


@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pos_terminals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                terminal_id VARCHAR(100) NOT NULL,
                merchant_id VARCHAR(255),
                location VARCHAR(255),
                status VARCHAR(20) DEFAULT 'active',
                last_transaction_at TIMESTAMPTZ,
                model VARCHAR(50),
                firmware_version VARCHAR(20),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


@app.get("/")
async def root():
    return {
        "service": "pos-integration",
        "description": "POS Integration Gateway",
        "version": "2.0.0",
        "port": 8126,
        "status": "operational",
        "features": [
            "transaction-scoring",
            "chart-of-accounts",
            "projections-targets",
            "qr-ticket-verification",
            "inventory-management",
        ],
    }


@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "pos-integration", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "pos-integration", "error": str(e)}


class ItemCreate(BaseModel):
    terminal_id: str
    merchant_id: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    last_transaction_at: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None


class ItemUpdate(BaseModel):
    terminal_id: Optional[str] = None
    merchant_id: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    last_transaction_at: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None


@app.post("/api/v1/pos-integration")
async def create_item(item: ItemCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        data = {k: v for k, v in item.dict().items() if v is not None}
        if not data:
            raise HTTPException(status_code=400, detail="No fields provided")
        cols = list(data.keys())
        vals = list(data.values())
        for i in range(len(vals)):
            if isinstance(vals[i], dict):
                vals[i] = json.dumps(vals[i])
        ph = ", ".join(["$" + str(i + 1) for i in range(len(cols))])
        query = f"INSERT INTO pos_terminals ({', '.join(cols)}) VALUES ({ph}) RETURNING *"
        row = await conn.fetchrow(query, *vals)
        return dict(row)


@app.get("/api/v1/pos-integration")
async def list_items(skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM pos_terminals ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, skip,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM pos_terminals")
        return {"total": total, "items": [dict(r) for r in rows], "skip": skip, "limit": limit}


@app.get("/api/v1/pos-integration/{item_id}")
async def get_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pos_terminals WHERE id=$1", uuid.UUID(item_id))
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)


@app.put("/api/v1/pos-integration/{item_id}")
async def update_item(item_id: str, item: ItemUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM pos_terminals WHERE id=$1", uuid.UUID(item_id))
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")
        updates = {k: v for k, v in item.dict().items() if v is not None}
        if not updates:
            return dict(existing)
        set_parts = []
        params = [uuid.UUID(item_id)]
        idx = 2
        for k, v in updates.items():
            set_parts.append(f"{k}=${idx}")
            params.append(json.dumps(v) if isinstance(v, dict) else v)
            idx += 1
        query = f"UPDATE pos_terminals SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)


@app.delete("/api/v1/pos-integration/{item_id}")
async def delete_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM pos_terminals WHERE id=$1", uuid.UUID(item_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}


@app.get("/api/v1/pos-integration/stats")
async def get_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM pos_terminals")
        today = await conn.fetchval("SELECT COUNT(*) FROM pos_terminals WHERE created_at >= CURRENT_DATE")
        return {"total": total, "today": today, "service": "pos-integration"}


@app.post("/process-payment")
async def process_payment(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(f"{POS_CORE_URL}/process-payment", json=body)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.json())
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="POS core service unavailable")


@app.get("/transaction/{transaction_id}/status")
async def get_transaction_status(transaction_id: str):
    stats["total_requests"] += 1
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{POS_CORE_URL}/transaction/{transaction_id}/status")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.json())
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="POS core service unavailable")


@app.post("/transaction/{transaction_id}/refund")
async def refund_transaction(transaction_id: str, request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{POS_CORE_URL}/transaction/{transaction_id}/refund", json=body,
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.json())
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="POS core service unavailable")


@app.post("/pos/score-transaction")
async def score_transaction(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{GATEWAY_URL}/transaction-scoring/score", json=body)
            return resp.json()
        except httpx.ConnectError:
            return {"error": "Transaction scoring service unavailable", "overall_score": None}


@app.post("/pos/gl-post")
async def gl_post(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/chart-of-accounts/auto-post",
                params={
                    "transaction_ref": body.get("transaction_ref", ""),
                    "transaction_type": body.get("transaction_type", "cash_in"),
                    "amount": body.get("amount", 0),
                    "currency": body.get("currency", "NGN"),
                    "agent_id": body.get("agent_id", ""),
                },
            )
            return resp.json()
        except httpx.ConnectError:
            return {"error": "COA service unavailable"}


@app.get("/pos/agent-targets/{agent_id}")
async def get_agent_targets(agent_id: str):
    stats["total_requests"] += 1
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{GATEWAY_URL}/projections-targets/targets",
                params={"agent_id": agent_id, "status": "active"},
            )
            return resp.json()
        except httpx.ConnectError:
            return []


@app.post("/pos/agent-targets/{agent_id}/record")
async def record_agent_target(agent_id: str, request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    target_id = body.get("target_id", "")
    value = body.get("value", 0)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/projections-targets/targets/{target_id}/record-actual",
                params={"value": value},
            )
            return resp.json()
        except httpx.ConnectError:
            return {"error": "Targets service unavailable"}


@app.post("/pos/qr-ticket/create")
async def create_qr_ticket(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{GATEWAY_URL}/qr-tickets/create", json=body)
            return resp.json()
        except httpx.ConnectError:
            return {"error": "QR ticket service unavailable"}


@app.post("/pos/qr-ticket/verify")
async def verify_qr_ticket(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{GATEWAY_URL}/qr-tickets/verify", json=body)
            return resp.json()
        except httpx.ConnectError:
            return {"error": "QR ticket service unavailable"}


@app.get("/pos/inventory/{agent_id}")
async def get_agent_inventory(agent_id: str):
    stats["total_requests"] += 1
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{GATEWAY_URL}/inventory-management/agent/{agent_id}")
            return resp.json()
        except httpx.ConnectError:
            return {"items": [], "error": "Inventory service unavailable"}


@app.post("/pos/inventory/{agent_id}/deduct")
async def deduct_agent_inventory(agent_id: str, request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    item_id = body.get("item_id", "")
    quantity = body.get("quantity", 1)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/inventory-management/agent/{agent_id}/transfer",
                json={
                    "item_id": item_id,
                    "quantity": quantity,
                    "transfer_type": "usage",
                    "reason": body.get("reason", "POS transaction supply usage"),
                },
            )
            return resp.json()
        except httpx.ConnectError:
            return {"error": "Inventory service unavailable"}


@app.post("/ledger/record-payment")
async def record_payment_to_ledger(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    transfer_data = {
        "debit_account_id": body.get("merchant_account_id", ""),
        "credit_account_id": body.get("settlement_account_id", ""),
        "amount": body.get("amount", 0),
        "currency": body.get("currency", "NGN"),
        "ledger_id": body.get("ledger_id", 1),
        "metadata": {
            "source": "pos",
            "transaction_id": body.get("transaction_id", ""),
            "terminal_id": body.get("terminal_id", ""),
            "payment_method": body.get("payment_method", ""),
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{TIGERBEETLE_SYNC_URL}/api/v1/sync/transfers",
                json=transfer_data,
            )
            if resp.status_code in (200, 201):
                return {"ledger_recorded": True, "detail": resp.json()}
            return {"ledger_recorded": False, "status": resp.status_code, "detail": resp.text}
        except Exception as e:
            logger.warning(f"TigerBeetle ledger record failed: {e}")
            return {"ledger_recorded": False, "error": str(e)}


@app.get("/management/terminals")
async def mgmt_list_terminals():
    stats["total_requests"] += 1
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{POS_MGMT_URL}/api/v1/terminals")
            return resp.json()
        except Exception as e:
            return {"error": str(e), "management_server": "unreachable"}


@app.post("/management/terminals/{terminal_id}/command")
async def mgmt_send_command(terminal_id: str, request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{POS_MGMT_URL}/api/v1/terminals/{terminal_id}/command", json=body,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e), "management_server": "unreachable"}


@app.post("/management/updates/deploy")
async def mgmt_deploy_update(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{POS_MGMT_URL}/api/v1/updates/deploy", json=body)
            return resp.json()
        except Exception as e:
            return {"error": str(e), "management_server": "unreachable"}


@app.get("/management/health")
async def mgmt_health():
    stats["total_requests"] += 1
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{POS_MGMT_URL}/health")
            return resp.json()
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8126)
