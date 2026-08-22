"""
Authentication and authorization service
"""

from fastapi import APIRouter, Depends, HTTPException, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse

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


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "auth-service", "timestamp": datetime.utcnow().isoformat()}

from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

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

router = APIRouter(prefix="/authservice", tags=["auth-service"])

# Pydantic models
class AuthserviceBase(BaseModel):
    """Base model for auth-service."""
    pass

class AuthserviceCreate(BaseModel):
    """Create model for auth-service."""
    name: str
    description: Optional[str] = None

class AuthserviceResponse(BaseModel):
    """Response model for auth-service."""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# API endpoints
@router.post("/", response_model=AuthserviceResponse, status_code=status.HTTP_201_CREATED)
async def create(data: AuthserviceCreate):
    """Create new auth-service record."""
    # Implementation here
    return {"id": 1, "name": data.name, "description": data.description, "created_at": datetime.now(), "updated_at": None}

@router.get("/{id}", response_model=AuthserviceResponse)
async def get_by_id(id: int):
    """Get auth-service by ID."""
    # Implementation here
    return {"id": id, "name": "Sample", "description": "Sample description", "created_at": datetime.now(), "updated_at": None}

@router.get("/", response_model=List[AuthserviceResponse])
async def list_all(skip: int = 0, limit: int = 100):
    """List all auth-service records."""
    # Implementation here
    return []

@router.put("/{id}", response_model=AuthserviceResponse)
async def update(id: int, data: AuthserviceCreate):
    """Update auth-service record."""
    # Implementation here
    return {"id": id, "name": data.name, "description": data.description, "created_at": datetime.now(), "updated_at": datetime.now()}

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(id: int):
    """Delete auth-service record."""
    # Implementation here
    return None

import psycopg2
import psycopg2.extras
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/auth_service")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    for stmt in """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE, password_hash TEXT, role TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER, token TEXT UNIQUE, role TEXT, expires_at TEXT
        )""".split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()

init_db()

import hashlib, hmac, secrets, time

TOKEN_EXPIRY = 3600  # 1 hour

# --- NF-SEC-8: salted password hashing (PBKDF2-HMAC-SHA256) ---
# Migration note: users.password_hash previously stored UNSALTED
# hashlib.sha256(password).hexdigest() (64 lowercase hex chars). Those rows are
# cryptographically weak and are NOT accepted anymore: verification fails closed
# for any value that is not in the PBKDF2 format below. Operators must force a
# password reset (or re-hash on next provisioning run) for legacy users.
# New format: pbkdf2_sha256$<iterations>$<salt_hex>$<derived_key_hex>
_PBKDF2_ITERATIONS = 210_000  # >= 100k per policy; OWASP 2023 recommendation for sha256
_PBKDF2_SALT_BYTES = 16
_PBKDF2_PREFIX = "pbkdf2_sha256"


def hash_password(password: str, salt: bytes | None = None, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a per-user random salt."""
    if salt is None:
        salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_PBKDF2_PREFIX}${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored PBKDF2 hash. Fails closed: any
    malformed, legacy (unsalted SHA-256), or unparseable value returns False."""
    try:
        prefix, iterations_s, salt_hex, dk_hex = stored.split("$")
        if prefix != _PBKDF2_PREFIX:
            logging.warning("[auth] refusing non-PBKDF2 password hash format (legacy/insecure) — fail closed")
            return False
        iterations = int(iterations_s)
        if iterations < 100_000:
            logging.warning("[auth] refusing PBKDF2 hash with insufficient iterations — fail closed")
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate, expected)
    except Exception as e:
        logging.warning(f"[auth] password verification error (fail closed): {type(e).__name__}")
        return False

@app.post("/api/v1/login")
async def login(request: Request):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("login_" + str(int(_time.time() * 1000)), _json.dumps({"action": "login", "timestamp": _time.time()}), "auth-service")

    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    conn = get_db()
    cursor = conn.cursor()
    # Fetch the stored hash by username, then verify with PBKDF2 (NF-SEC-8).
    # verify_password fails closed on legacy unsalted SHA-256 rows.
    cursor.execute("SELECT id, role, password_hash FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if not user or not verify_password(password, user[2] or ""):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    cursor.execute("INSERT INTO sessions (user_id, token, role, expires_at) VALUES (%s, %s, %s, NOW() + INTERVAL '1 hour')",
                   (user[0], token, user[1]))
    conn.commit()
    conn.close()
    return {"token": token, "role": user[1], "expires_in": TOKEN_EXPIRY}

@app.post("/api/v1/validate")
async def validate_token(request: Request):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("validate_token_" + str(int(_time.time() * 1000)), _json.dumps({"action": "validate_token", "timestamp": _time.time()}), "auth-service")

    body = await request.json()
    token = body.get("token", "")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM sessions WHERE token = %s AND expires_at > NOW()", (token,))
    session = cursor.fetchone()
    conn.close()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True, "user_id": session[0], "role": session[1]}

@app.post("/api/v1/logout")
async def logout(request: Request):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("logout_" + str(int(_time.time() * 1000)), _json.dumps({"action": "logout", "timestamp": _time.time()}), "auth-service")

    body = await request.json()
    token = body.get("token", "")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
    conn.commit()
    conn.close()
    return {"status": "logged_out"}
