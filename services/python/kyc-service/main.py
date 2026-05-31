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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

import sqlite3

def _init_persistence():
    """Initialize SQLite persistence for kyc-service."""
    import os
    db_path = os.environ.get("KYC_SERVICE_DB_PATH", "/tmp/kyc-service.db")
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    except Exception as e:
        import logging
        logging.warning(f"SQLite unavailable ({e}) — running in-memory only")
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
