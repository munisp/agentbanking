"""
Reporting Service
Port: 8000
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

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "remittance")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "remittance-api")
_JWKS_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient
        _jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)
    return _jwks_client


async def verify_token(authorization: str = Header(...)):
    """Validate the Bearer JWT against the Keycloak realm JWKS.

    Previously this only checked the header shape, so any non-empty string
    was accepted as a token (authentication bypass). Authentication is now
    always enforced: tokens must be signed, unexpired realm JWTs.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    import jwt
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims.get("sub", "")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Token validation unavailable: {e}")


app = FastAPI(title="Reporting Service", description="Reporting Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                report_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                parameters JSONB DEFAULT '{}',
                status VARCHAR(20) DEFAULT 'pending',
                result JSONB,
                generated_by VARCHAR(255),
                file_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_report_type ON reports(report_type);
            CREATE INDEX IF NOT EXISTS idx_report_status ON reports(status)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "reporting-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "reporting-service", "error": str(e)}


class ReportRequest(BaseModel):
    report_type: str
    title: str
    parameters: Optional[Dict[str, Any]] = None

@app.post("/api/v1/reports/generate")
async def generate_report(req: ReportRequest, token: str = Depends(verify_token)):
    """Request generation of a report.

    FAIL LOUD: this service has no report-rendering backend wired up, and the
    previous implementation marked every request 'completed' with a fabricated
    summary. Requests are now recorded as 'failed' and the caller gets a 501
    instead of a fake report.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO reports (report_type, title, parameters, generated_by, status, result)
               VALUES ($1, $2, $3, $4, 'failed', $5) RETURNING *""",
            req.report_type, req.title, json.dumps(req.parameters or {}), token[:36],
            json.dumps({"error": "Report generation backend is not implemented for this service"}),
        )
        raise HTTPException(
            status_code=501,
            detail={
                "report_id": str(row["id"]),
                "error": "Report generation is not implemented for this service. No report was produced.",
            },
        )

@app.get("/api/v1/reports")
async def list_reports(report_type: Optional[str] = None, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if report_type:
            rows = await conn.fetch("SELECT * FROM reports WHERE report_type=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", report_type, limit, skip)
        else:
            rows = await conn.fetch("SELECT * FROM reports ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, skip)
        return {"reports": [dict(r) for r in rows]}

@app.get("/api/v1/reports/{report_id}")
async def get_report(report_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM reports WHERE id=$1", uuid.UUID(report_id))
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        return dict(row)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
