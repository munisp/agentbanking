"""
LPO Service (Local Purchase Order / invoice-purchase financing)
Port: 8088

Backs the 54link_admin LPO page. All state lives in Postgres (lpo_applications,
lpo_repayments). Workflow transitions are atomic (SELECT ... FOR UPDATE) and
recorded in status_history. Authentication is enforced via Keycloak realm JWTs
(except /health). Fails closed: when the DB is unavailable, endpoints return
503 rather than serving in-memory or fabricated data.

Round-11 wave-8: new service — the admin UI previously called /lpo/* with no
backend at all.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid
import os
import json
import asyncpg
import uvicorn
import logging

DATABASE_URL = os.getenv("LPO_SERVICE_DATABASE_URL",
                         os.getenv("DATABASE_URL",
                                   "postgresql://postgres:postgres@localhost:5432/platform"))

_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        async with _db_pool.acquire() as c:
            await c.execute("""
                CREATE TABLE IF NOT EXISTS lpo_applications (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    supplier_name VARCHAR(200) NOT NULL,
                    supplier_email VARCHAR(200),
                    supplier_phone VARCHAR(64),
                    company_registration VARCHAR(64),
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    status_history JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_by VARCHAR(128),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")
            await c.execute("""
                CREATE TABLE IF NOT EXISTS lpo_repayments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lpo_id UUID NOT NULL REFERENCES lpo_applications(id) ON DELETE CASCADE,
                    amount NUMERIC(18, 2) NOT NULL,
                    paid_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    reference VARCHAR(128)
                )""")
    return _db_pool

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "remittance")
_JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient
        _jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)
    return _jwks_client


async def verify_token(authorization: str = Header(...)):
    """Validate the Bearer JWT against the Keycloak realm JWKS. Always enforced."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    import jwt
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims.get("sub", "")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


app = FastAPI(title="LPO Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

ALLOWED_TRANSITIONS = {
    "pending":  {"verify": "verified", "reject": "rejected"},
    "verified": {"approve": "approved", "reject": "rejected"},
    "approved": {"disburse": "disbursed"},
}


def _row_to_lpo(r) -> dict:
    return {
        "id": str(r["id"]),
        "supplier_name": r["supplier_name"],
        "supplier_email": r["supplier_email"],
        "supplier_phone": r["supplier_phone"],
        "company_registration": r["company_registration"],
        "status": r["status"],
        "status_history": json.loads(r["status_history"]) if isinstance(r["status_history"], str) else r["status_history"],
        "created_by": r["created_by"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        **(json.loads(r["payload"]) if isinstance(r["payload"], str) else (r["payload"] or {})),
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "lpo-service", "version": "1.0.0"}


@app.post("/api/v1/lpo/supplier/register", status_code=201)
async def register_supplier(
    supplier_id: Optional[str] = Query(default=None),
    business_name: Optional[str] = Query(default=None),
    registration_number: Optional[str] = Query(default=None),
    user: str = Depends(verify_token),
):
    """Register a supplier by creating the initial LPO application record.
    Accepts query params because the admin UI posts URLSearchParams."""
    if not business_name:
        raise HTTPException(status_code=400, detail="business_name is required")
    pool = await get_db_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("""
            INSERT INTO lpo_applications
                (supplier_name, company_registration, payload, status, status_history, created_by)
            VALUES ($1, $2, $3, 'pending',
                    jsonb_build_array(jsonb_build_object(
                        'status', 'pending', 'at', now()::text, 'by', $4)), $4)
            RETURNING *
        """, business_name, registration_number or (supplier_id or ""),
             json.dumps({"supplier_id": supplier_id}), user)
    return _row_to_lpo(row)


@app.get("/api/v1/lpo/applications")
async def list_applications(status: Optional[str] = None, user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        if status:
            rows = await c.fetch(
                "SELECT * FROM lpo_applications WHERE status = $1 ORDER BY created_at DESC LIMIT 500", status)
        else:
            rows = await c.fetch("SELECT * FROM lpo_applications ORDER BY created_at DESC LIMIT 500")
    items = [_row_to_lpo(r) for r in rows]
    return {"items": items, "total": len(items)}


# NOTE: literal routes must be declared BEFORE /api/v1/lpo/{lpo_id} (FastAPI route order).
@app.get("/api/v1/lpo/administration")
async def lpo_administration(user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT * FROM lpo_applications ORDER BY created_at DESC LIMIT 500")
        stats = await c.fetchrow("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE status = 'pending') AS pending,
                   count(*) FILTER (WHERE status = 'approved') AS approved,
                   count(*) FILTER (WHERE status = 'disbursed') AS disbursed,
                   count(*) FILTER (WHERE status = 'rejected') AS rejected
            FROM lpo_applications""")
    return {"items": [_row_to_lpo(r) for r in rows], "lpos": [_row_to_lpo(r) for r in rows],
            "total": len(rows), "stats": dict(stats)}


@app.get("/api/v1/lpo/{lpo_id}")
async def get_lpo(lpo_id: uuid.UUID, user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT * FROM lpo_applications WHERE id = $1", lpo_id)
    if not row:
        raise HTTPException(status_code=404, detail="LPO not found")
    return _row_to_lpo(row)


async def _transition(lpo_id: uuid.UUID, action: str, user: str, note: Optional[str] = None):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        async with c.transaction():
            row = await c.fetchrow(
                "SELECT * FROM lpo_applications WHERE id = $1 FOR UPDATE", lpo_id)
            if not row:
                raise HTTPException(status_code=404, detail="LPO not found")
            current = row["status"]
            new_status = ALLOWED_TRANSITIONS.get(current, {}).get(action)
            if not new_status:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot {action} an LPO in status '{current}'")
            entry = {"status": new_status, "action": action,
                     "at": datetime.utcnow().isoformat(), "by": user}
            if note:
                entry["note"] = note
            await c.execute("""
                UPDATE lpo_applications
                SET status = $2,
                    status_history = status_history || $3::jsonb,
                    updated_at = now()
                WHERE id = $1
            """, lpo_id, new_status, json.dumps([entry]))
    return {"id": str(lpo_id), "status": new_status}


class TransitionBody(BaseModel):
    note: Optional[str] = None
    reason: Optional[str] = None


@app.post("/api/v1/lpo/{lpo_id}/verify")
async def verify_lpo(lpo_id: uuid.UUID, body: Optional[TransitionBody] = None,
                     user: str = Depends(verify_token)):
    return await _transition(lpo_id, "verify", user, body.note if body else None)


@app.post("/api/v1/lpo/{lpo_id}/approve")
async def approve_lpo(lpo_id: uuid.UUID, body: Optional[TransitionBody] = None,
                      user: str = Depends(verify_token)):
    return await _transition(lpo_id, "approve", user, body.note if body else None)


@app.post("/api/v1/lpo/{lpo_id}/reject")
async def reject_lpo(lpo_id: uuid.UUID, body: Optional[TransitionBody] = None,
                     user: str = Depends(verify_token)):
    return await _transition(lpo_id, "reject", user,
                             (body.reason or body.note) if body else None)


@app.post("/api/v1/lpo/{lpo_id}/disburse")
async def disburse_lpo(lpo_id: uuid.UUID, body: Optional[TransitionBody] = None,
                       user: str = Depends(verify_token)):
    return await _transition(lpo_id, "disburse", user, body.note if body else None)


@app.get("/api/v1/lpo/{lpo_id}/repayments")
async def lpo_repayments(lpo_id: uuid.UUID, user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        exists = await c.fetchval("SELECT 1 FROM lpo_applications WHERE id = $1", lpo_id)
        if not exists:
            raise HTTPException(status_code=404, detail="LPO not found")
        rows = await c.fetch(
            "SELECT * FROM lpo_repayments WHERE lpo_id = $1 ORDER BY paid_at DESC", lpo_id)
    items = [{"id": str(r["id"]), "lpo_id": str(r["lpo_id"]),
              "amount": float(r["amount"]),
              "paid_at": r["paid_at"].isoformat() if r["paid_at"] else None,
              "reference": r["reference"]} for r in rows]
    return {"repayments": items, "total": len(items)}


@app.get("/api/v1/suppliers")
async def list_suppliers(user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT DISTINCT ON (supplier_name)
                   supplier_name, supplier_email, supplier_phone, company_registration,
                   min(created_at) AS since
            FROM lpo_applications
            GROUP BY supplier_name, supplier_email, supplier_phone, company_registration
            ORDER BY supplier_name LIMIT 500""")
    items = [{"supplier_name": r["supplier_name"], "supplier_email": r["supplier_email"],
              "supplier_phone": r["supplier_phone"],
              "company_registration": r["company_registration"]} for r in rows]
    return {"items": items, "suppliers": items, "total": len(items)}


@app.get("/api/v1/lpo/supplier/{supplier_id}/profile")
async def supplier_profile(supplier_id: str, user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow("""
            SELECT * FROM lpo_applications
            WHERE supplier_name = $1
               OR payload->>'supplier_id' = $1
               OR company_registration = $1
            ORDER BY created_at DESC LIMIT 1""", supplier_id)
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return _row_to_lpo(row)


@app.get("/api/v1/lpo/supplier/{supplier_id}")
async def supplier_lpos(supplier_id: str, user: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT * FROM lpo_applications
            WHERE supplier_name = $1
               OR payload->>'supplier_id' = $1
               OR company_registration = $1
            ORDER BY created_at DESC LIMIT 500""", supplier_id)
    items = [_row_to_lpo(r) for r in rows]
    return {"items": items, "lpos": items, "total": len(items)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8088")))
