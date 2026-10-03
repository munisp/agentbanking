"""
Multi-Currency Wallet
Port: 8085
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

app = FastAPI(title="Multi-Currency Wallet", description="Multi-Currency Wallet for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS currency_wallets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                balance DECIMAL(18,2) DEFAULT 0,
                available_balance DECIMAL(18,2) DEFAULT 0,
                frozen_amount DECIMAL(18,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "multi-currency-wallet", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "multi-currency-wallet", "error": str(e)}


class ItemCreate(BaseModel):
    user_id: str
    currency: str
    balance: Optional[float] = None
    available_balance: Optional[float] = None
    frozen_amount: Optional[float] = None
    status: Optional[str] = None

class ItemUpdate(BaseModel):
    user_id: Optional[str] = None
    currency: Optional[str] = None
    balance: Optional[float] = None
    available_balance: Optional[float] = None
    frozen_amount: Optional[float] = None
    status: Optional[str] = None


@app.post("/api/v1/multi-currency-wallet")
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
        ph = ", ".join(["$" + str(i+1) for i in range(len(cols))])
        query = f"INSERT INTO currency_wallets ({', '.join(cols)}) VALUES ({ph}) RETURNING *"
        row = await conn.fetchrow(query, *vals)
        return dict(row)


@app.get("/api/v1/multi-currency-wallet")
async def list_items(skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM currency_wallets ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, skip
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM currency_wallets")
        return {"total": total, "items": [dict(r) for r in rows], "skip": skip, "limit": limit}


@app.get("/api/v1/multi-currency-wallet/{item_id}")
async def get_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM currency_wallets WHERE id=$1", uuid.UUID(item_id))
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)


@app.put("/api/v1/multi-currency-wallet/{item_id}")
async def update_item(item_id: str, item: ItemUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM currency_wallets WHERE id=$1", uuid.UUID(item_id))
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
        query = f"UPDATE currency_wallets SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)


@app.delete("/api/v1/multi-currency-wallet/{item_id}")
async def delete_item(item_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM currency_wallets WHERE id=$1", uuid.UUID(item_id))
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}


@app.get("/api/v1/multi-currency-wallet/stats")
async def get_stats(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM currency_wallets")
        today = await conn.fetchval("SELECT COUNT(*) FROM currency_wallets WHERE created_at >= CURRENT_DATE")
        return {"total": total, "today": today, "service": "multi-currency-wallet"}



# ── Round-11 wave-7 gap fix: /wallet/* facade ─────────────────────────────────
# The mobile-agent-dashboard and pos-agent-app frontends call /wallet/balances,
# /wallet/list, /wallet/create, /wallet/exchange-rate, /wallet/exchange and
# /wallet/virtual-cards*. The APISIX /wallet/* route lands here (prefix
# stripped). Every handler proxies to a real downstream service and fails
# closed (503) when the downstream is not configured — no data is fabricated.
#
# Configuration:
#   ACCOUNTS_SERVICE_URL   — multi-currency-accounts base (accounts + balances)
#   CARD_SERVICE_URL       — card-service base (virtual cards)
#   FX_SERVICE_URL         — FX provider base (exchange rates / conversion)

import httpx

ACCOUNTS_SERVICE_URL = os.getenv("ACCOUNTS_SERVICE_URL", "").rstrip("/")
CARD_SERVICE_URL = os.getenv("CARD_SERVICE_URL", "").rstrip("/")
FX_SERVICE_URL = os.getenv("FX_SERVICE_URL", "").rstrip("/")

_FWD_HEADERS = ("authorization", "x-tenant-id", "x-keycloak-id", "x-request-id")


def _forward_headers(request) -> dict:
    return {k: v for k, v in request.headers.items() if k.lower() in _FWD_HEADERS}


async def _proxy(method: str, base: str, path: str, request, json_body=None, params=None):
    if not base:
        raise HTTPException(status_code=503, detail="downstream service is not configured for this endpoint")
    url = base + path
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, url, headers=_forward_headers(request),
                                        json=json_body, params=params)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"downstream service unavailable: {type(e).__name__}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:500])
    try:
        return resp.json()
    except ValueError:
        return {"status": resp.status_code}


@app.get("/wallet/list")
@app.get("/balances")
@app.get("/list")
async def wallet_list(request: Request, token: str = Depends(verify_token)):
    """List the caller's multi-currency accounts (wallets)."""
    return await _proxy("GET", ACCOUNTS_SERVICE_URL, "/api/v1/accounts", request)


@app.get("/wallet/balances")
@app.get("/balances")
async def wallet_balances(request: Request, token: str = Depends(verify_token)):
    """Aggregated per-currency balances across the caller's accounts."""
    if not ACCOUNTS_SERVICE_URL:
        raise HTTPException(status_code=503, detail="accounts service is not configured")
    accounts = await _proxy("GET", ACCOUNTS_SERVICE_URL, "/api/v1/accounts", request)
    acc_list = accounts.get("accounts", accounts) if isinstance(accounts, dict) else accounts
    if not isinstance(acc_list, list):
        return accounts
    balances = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for acc in acc_list[:50]:
            acc_id = acc.get("id") or acc.get("account_id")
            if not acc_id:
                continue
            try:
                r = await client.get(f"{ACCOUNTS_SERVICE_URL}/api/v1/accounts/{acc_id}/balances",
                                     headers=_forward_headers(request))
                if r.status_code < 400:
                    body = r.json()
                    for b in (body.get("balances", body) if isinstance(body, dict) else body):
                        if isinstance(b, dict):
                            b.setdefault("account_id", acc_id)
                            balances.append(b)
            except (httpx.HTTPError, ValueError):
                continue
    return {"balances": balances, "accounts": len(acc_list)}


@app.get("/wallet/balance")
@app.get("/balance")
async def wallet_balance(request: Request, account_id: Optional[str] = None, token: str = Depends(verify_token)):
    if account_id:
        return await _proxy("GET", ACCOUNTS_SERVICE_URL, f"/api/v1/accounts/{account_id}/balances", request)
    return await wallet_balances(request, token)


@app.post("/wallet/create")
@app.post("/create")
async def wallet_create(request: Request, token: str = Depends(verify_token)):
    body = await request.json()
    return await _proxy("POST", ACCOUNTS_SERVICE_URL, "/api/v1/accounts", request, json_body=body)


@app.get("/wallet/exchange-rate")
@app.get("/exchange-rate")
async def wallet_exchange_rate(request: Request, token: str = Depends(verify_token)):
    return await _proxy("GET", FX_SERVICE_URL, "/rates", request, params=dict(request.query_params))


@app.post("/wallet/exchange")
@app.post("/exchange")
async def wallet_exchange(request: Request, token: str = Depends(verify_token)):
    body = await request.json()
    return await _proxy("POST", FX_SERVICE_URL, "/convert", request, json_body=body)


@app.get("/wallet/virtual-cards")
@app.get("/virtual-cards")
async def wallet_virtual_cards(request: Request, token: str = Depends(verify_token)):
    return await _proxy("GET", CARD_SERVICE_URL, "/api/v1/cards/customer", request)


@app.post("/wallet/virtual-cards")
@app.post("/virtual-cards")
async def wallet_virtual_card_create(request: Request, token: str = Depends(verify_token)):
    body = await request.json()
    return await _proxy("POST", CARD_SERVICE_URL, "/api/v1/cards/issue", request, json_body=body)


@app.post("/wallet/virtual-cards/{card_id}/freeze")
@app.post("/virtual-cards/{card_id}/freeze")
async def wallet_virtual_card_freeze(card_id: str, request: Request, token: str = Depends(verify_token)):
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    return await _proxy("POST", CARD_SERVICE_URL, f"/api/v1/cards/{card_id}/freeze", request, json_body=body)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085)
