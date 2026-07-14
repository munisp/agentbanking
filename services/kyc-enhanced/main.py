"""
KYC Enhanced (EDD) Gateway

Proxies Enhanced Due Diligence requests to the canonical KYC service
at core-services/kyc-service. EDD cases are handled via the /v2/edd
endpoints on the canonical service.
"""
import os
import logging
import httpx
import uvicorn
from typing import Any, Dict
from fastapi import FastAPI, Request, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

KYC_CORE_URL = os.getenv("KYC_CORE_SERVICE_URL", "http://kyc-service:8015")

app = FastAPI(
    title="KYC Enhanced (EDD) Gateway",
    description="Proxies to canonical KYC service for Enhanced Due Diligence operations.",
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
    params = dict(request.query_params)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, f"{KYC_CORE_URL}{path}", headers=headers,
                                     content=body, params=params)
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{KYC_CORE_URL}/health")
        upstream = resp.json()
    except Exception as e:
        upstream = {"error": str(e)}
    return {"status": "healthy", "service": "kyc-enhanced-gateway", "upstream": upstream}


@app.api_route("/api/v1/kyc-enhanced/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_edd(path: str, request: Request, token: str = Depends(verify_token)):
    return await _proxy(request.method, f"/v2/{path}", request, token)


@app.get("/", include_in_schema=False)
async def root() -> Dict[str, Any]:
    return {"message": "KYC Enhanced (EDD) Gateway is running", "version": "2.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8099")))
