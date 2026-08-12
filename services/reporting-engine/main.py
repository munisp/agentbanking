"""
Reporting Engine
Port: 8130
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


app = FastAPI(title="Reporting Engine", description="Reporting Engine for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS report_templates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL,
                description TEXT,
                query_template TEXT NOT NULL,
                parameters JSONB DEFAULT '{}',
                schedule VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS report_executions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                template_id UUID REFERENCES report_templates(id),
                status VARCHAR(20) DEFAULT 'pending',
                parameters JSONB DEFAULT '{}',
                result JSONB,
                row_count INT DEFAULT 0,
                execution_time_ms INT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "reporting-engine", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "reporting-engine", "error": str(e)}


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query_template: str
    parameters: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None

@app.post("/api/v1/report-engine/templates")
async def create_template(t: TemplateCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO report_templates (name, description, query_template, parameters, schedule) VALUES ($1,$2,$3,$4,$5) RETURNING *",
            t.name, t.description, t.query_template, json.dumps(t.parameters or {}), t.schedule
        )
        return dict(row)

@app.get("/api/v1/report-engine/templates")
async def list_templates(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM report_templates WHERE is_active=TRUE ORDER BY name")
        return {"templates": [dict(r) for r in rows]}

@app.post("/api/v1/report-engine/execute/{template_id}")
async def execute_report(template_id: str, parameters: Optional[Dict[str, Any]] = None, token: str = Depends(verify_token)):
    """Execute a report template.

    Runs the template's ``query_template`` against the database and stores the
    real result set. Previously this endpoint marked every execution
    'completed' with a fabricated result containing no rows. Failures are now
    recorded as status='failed' with the underlying error.
    """
    pool = await get_db_pool()
    params = parameters or {}
    args = params.get("args", [])
    if not isinstance(args, list):
        raise HTTPException(status_code=400, detail="parameters.args must be a list of positional query arguments")
    async with pool.acquire() as conn:
        template = await conn.fetchrow("SELECT * FROM report_templates WHERE id=$1 AND is_active=TRUE", uuid.UUID(template_id))
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        import time
        start = time.time()
        try:
            rows = await conn.fetch(template["query_template"], *args)
            records = [dict(r) for r in rows]
            result = {
                "template": template["name"],
                "parameters": params,
                "rows": records,
                "generated_at": datetime.utcnow().isoformat(),
            }
            elapsed = int((time.time() - start) * 1000)
            row = await conn.fetchrow(
                """INSERT INTO report_executions (template_id, status, parameters, result, row_count, execution_time_ms, completed_at)
                   VALUES ($1, 'completed', $2, $3, $4, $5, NOW()) RETURNING *""",
                uuid.UUID(template_id), json.dumps(params), json.dumps(result, default=str), len(records), elapsed
            )
            return dict(row)
        except HTTPException:
            raise
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await conn.execute(
                """INSERT INTO report_executions (template_id, status, parameters, result, execution_time_ms, completed_at)
                   VALUES ($1, 'failed', $2, $3, $4, NOW())""",
                uuid.UUID(template_id), json.dumps(params), json.dumps({"error": str(e)}), elapsed
            )
            raise HTTPException(status_code=400, detail=f"Report execution failed: {e}")

@app.get("/api/v1/report-engine/executions")
async def list_executions(template_id: Optional[str] = None, skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if template_id:
            rows = await conn.fetch("SELECT * FROM report_executions WHERE template_id=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", uuid.UUID(template_id), limit, skip)
        else:
            rows = await conn.fetch("SELECT * FROM report_executions ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, skip)
        return {"executions": [dict(r) for r in rows]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8130)
