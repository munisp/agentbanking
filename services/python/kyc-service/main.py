"""
KYC Service Gateway
Port: 8098

This is a thin gateway that proxies KYC requests to the canonical
core-services/kyc-service. All KYC logic, PostgreSQL persistence,
provider integrations, and authentication live in the canonical service.

For direct access, use the canonical service at core-services/kyc-service (port 8015).
"""
import os
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, Header
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

import psycopg2
import psycopg2.extras

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


def _init_persistence():
    """Initialize PostgreSQL persistence for kyc-service."""
    import os
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', 'postgres://postgres:postgres@localhost:5432/kyc_service'))
        
        
        return conn
    except Exception as e:
        import logging
        logging.warning(f"Database unavailable ({e}) — running in-memory only")
        return None

_persistence_db = _init_persistence()

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

KYC_CORE_URL = os.getenv("KYC_CORE_SERVICE_URL", "http://kyc-service:8015")

app = FastAPI(
    title="KYC Service Gateway",
    description="Proxies to canonical KYC service at core-services/kyc-service",
    version="2.0.0",
)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

async def _proxy(method: str, path: str, request: Request, token: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for h in ("X-Correlation-ID", "X-Request-ID"):
        if h in request.headers:
            headers[h] = request.headers[h]
    body = await request.body()
    url = f"{KYC_CORE_URL}{path}"
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, headers=headers, content=body, params=params)
    return JSONResponse(status_code=resp.status_code, content=resp.json())

@app.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{KYC_CORE_URL}/health")
        upstream = resp.json()
    except Exception as e:
        upstream = {"error": str(e)}
    return {"status": "healthy", "service": "kyc-service-gateway", "upstream": upstream}

@app.api_route("/api/v1/kyc-service/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_kyc(path: str, request: Request, token: str = Depends(verify_token)):
    core_path = f"/{path}" if path else "/"
    return await _proxy(request.method, core_path, request, token)

@app.api_route("/profiles/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_profiles(path: str, request: Request, token: str = Depends(verify_token)):
    return await _proxy(request.method, f"/profiles/{path}", request, token)

@app.api_route("/documents/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_documents(path: str, request: Request, token: str = Depends(verify_token)):
    return await _proxy(request.method, f"/documents/{path}", request, token)

@app.api_route("/admin/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_admin(path: str, request: Request, token: str = Depends(verify_token)):
    return await _proxy(request.method, f"/admin/{path}", request, token)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8098)
