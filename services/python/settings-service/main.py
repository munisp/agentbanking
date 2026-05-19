"""
54Link Platform Settings Service
Production-ready settings management with full CRUD, audit trail, and Redis caching.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncpg
import aioredis

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SETTINGS_CACHE_TTL = int(os.getenv("SETTINGS_CACHE_TTL", "300"))

app = FastAPI(title="Settings Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Pydantic Models ────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    platform_name: Optional[str] = None
    support_email: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    two_factor_auth: Optional[bool] = None
    session_timeout: Optional[int] = None
    password_expiry: Optional[int] = None
    max_login_attempts: Optional[int] = None
    api_rate_limit: Optional[int] = None
    webhook_retries: Optional[int] = None
    log_retention: Optional[int] = None
    maintenance_mode: Optional[bool] = None
    debug_mode: Optional[bool] = None

class APIKeyCreate(BaseModel):
    name: str
    environment: str = Field(default="production", pattern="^(production|test|sandbox)$")
    permissions: List[str] = []
    expires_days: Optional[int] = None

class WebhookCreate(BaseModel):
    url: str
    events: List[str]
    secret: Optional[str] = None
    is_active: bool = True

# ── Database Helpers ───────────────────────────────────────────────────────────

async def get_db():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

async def get_redis():
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()

# ── Settings Endpoints ─────────────────────────────────────────────────────────

from fastapi import APIRouter
router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/")
async def get_settings(
    request: Request,
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Get all platform settings"""
    cache_key = "platform:settings"
    
    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    try:
        row = await db.fetchrow(
            "SELECT * FROM platform_settings WHERE id = 1"
        )
        if not row:
            # Return defaults
            settings = _default_settings()
        else:
            settings = dict(row)
        
        await redis.setex(cache_key, SETTINGS_CACHE_TTL, json.dumps(settings, default=str))
        return settings
    except Exception as e:
        logger.error(f"Failed to fetch settings: {e}")
        return _default_settings()


@router.put("/")
async def update_settings(
    data: SettingsUpdate,
    request: Request,
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Update platform settings"""
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    try:
        # Build dynamic update query
        set_clauses = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(updates.keys())])
        values = [1] + list(updates.values())
        
        await db.execute(
            f"UPDATE platform_settings SET {set_clauses}, updated_at = NOW() WHERE id = $1",
            *values
        )
        
        # Audit log
        await db.execute(
            """INSERT INTO settings_audit_log (changed_by, changes, changed_at)
               VALUES ($1, $2, NOW())""",
            request.headers.get("X-User-ID", "system"),
            json.dumps(updates)
        )
        
        # Invalidate cache
        await redis.delete("platform:settings")
        
        return {"success": True, "message": "Settings updated", "updated_fields": list(updates.keys())}
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api-keys")
async def list_api_keys(db=Depends(get_db)):
    """List all API keys (masked)"""
    try:
        rows = await db.fetch(
            """SELECT id, name, environment, permissions, 
                      LEFT(key_value, 8) || '...' as key_preview,
                      is_active, expires_at, created_at, last_used_at
               FROM api_keys ORDER BY created_at DESC"""
        )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        return []


@router.post("/api-keys")
async def create_api_key(data: APIKeyCreate, db=Depends(get_db)):
    """Create a new API key"""
    import secrets
    import hashlib
    from datetime import timedelta
    
    raw_key = f"54l_{data.environment[:4]}_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    expires_at = None
    if data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_days)
    
    try:
        row = await db.fetchrow(
            """INSERT INTO api_keys (name, environment, key_value, key_hash, permissions, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, name, environment, created_at""",
            data.name, data.environment, raw_key, key_hash,
            json.dumps(data.permissions), expires_at
        )
        return {
            "success": True,
            "api_key": raw_key,  # Only shown once
            "id": str(row["id"]),
            "name": row["name"],
            "environment": row["environment"],
            "created_at": row["created_at"].isoformat(),
            "warning": "Store this key securely. It will not be shown again.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, db=Depends(get_db)):
    """Revoke an API key"""
    try:
        result = await db.execute(
            "UPDATE api_keys SET is_active = false, revoked_at = NOW() WHERE id = $1",
            key_id
        )
        return {"success": True, "message": "API key revoked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhooks")
async def list_webhooks(db=Depends(get_db)):
    """List all webhooks"""
    try:
        rows = await db.fetch(
            "SELECT id, url, events, is_active, created_at, last_triggered_at FROM webhooks ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]
    except Exception as e:
        return []


@router.post("/webhooks")
async def create_webhook(data: WebhookCreate, db=Depends(get_db)):
    """Create a new webhook"""
    import secrets
    secret = data.secret or secrets.token_urlsafe(32)
    try:
        row = await db.fetchrow(
            """INSERT INTO webhooks (url, events, secret, is_active)
               VALUES ($1, $2, $3, $4) RETURNING id, url, events, created_at""",
            data.url, json.dumps(data.events), secret, data.is_active
        )
        return {
            "success": True,
            "id": str(row["id"]),
            "url": row["url"],
            "secret": secret,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, data: WebhookCreate, db=Depends(get_db)):
    """Update a webhook"""
    try:
        await db.execute(
            "UPDATE webhooks SET url=$2, events=$3, is_active=$4, updated_at=NOW() WHERE id=$1",
            webhook_id, data.url, json.dumps(data.events), data.is_active
        )
        return {"success": True, "message": "Webhook updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, db=Depends(get_db)):
    """Delete a webhook"""
    try:
        await db.execute("DELETE FROM webhooks WHERE id=$1", webhook_id)
        return {"success": True, "message": "Webhook deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-log")
async def get_audit_log(
    page: int = 1,
    limit: int = 50,
    db=Depends(get_db),
):
    """Get settings audit log"""
    offset = (page - 1) * limit
    try:
        rows = await db.fetch(
            "SELECT * FROM settings_audit_log ORDER BY changed_at DESC LIMIT $1 OFFSET $2",
            limit, offset
        )
        total = await db.fetchval("SELECT COUNT(*) FROM settings_audit_log")
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }
    except Exception as e:
        return {"items": [], "total": 0, "page": page, "limit": limit}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _default_settings() -> Dict[str, Any]:
    return {
        "platform_name": os.getenv("PLATFORM_NAME", "54Link Agency Banking Platform"),
        "support_email": os.getenv("SUPPORT_EMAIL", "support@54link.com"),
        "timezone": os.getenv("TZ", "Africa/Lagos"),
        "currency": os.getenv("DEFAULT_CURRENCY", "NGN"),
        "language": os.getenv("DEFAULT_LANGUAGE", "en"),
        "email_notifications": True,
        "sms_notifications": True,
        "push_notifications": True,
        "two_factor_auth": True,
        "session_timeout": int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
        "password_expiry": int(os.getenv("PASSWORD_EXPIRY_DAYS", "90")),
        "max_login_attempts": int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
        "api_rate_limit": int(os.getenv("API_RATE_LIMIT", "1000")),
        "webhook_retries": int(os.getenv("WEBHOOK_RETRIES", "3")),
        "log_retention": int(os.getenv("LOG_RETENTION_DAYS", "90")),
        "maintenance_mode": False,
        "debug_mode": os.getenv("ENVIRONMENT", "production") != "production",
    }


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8007")))
