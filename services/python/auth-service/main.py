"""
Authentication and authorization service
"""

from fastapi import APIRouter, Depends, HTTPException, status


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

import hashlib, secrets, time

TOKEN_EXPIRY = 3600  # 1 hour

@app.post("/api/v1/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role FROM users WHERE username = %s AND password_hash = %s", (username, password_hash))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    cursor.execute("INSERT INTO sessions (user_id, token, role, expires_at) VALUES (?, ?, ?, NOW() + INTERVAL '1 hour')",
                   (user[0], token, user[1]))
    conn.commit()
    conn.close()
    return {"token": token, "role": user[1], "expires_in": TOKEN_EXPIRY}

@app.post("/api/v1/validate")
async def validate_token(request: Request):
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
    body = await request.json()
    token = body.get("token", "")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
    conn.commit()
    conn.close()
    return {"status": "logged_out"}
