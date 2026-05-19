"""
Notification Service
Port: 8123
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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://remittance:remittance@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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

app = FastAPI(title="Notification Service", description="Notification Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                channel VARCHAR(20) NOT NULL DEFAULT 'push',
                title VARCHAR(255) NOT NULL,
                body TEXT NOT NULL,
                category VARCHAR(50),
                priority VARCHAR(10) DEFAULT 'normal',
                status VARCHAR(20) DEFAULT 'pending',
                read_at TIMESTAMPTZ,
                sent_at TIMESTAMPTZ,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id VARCHAR(255) PRIMARY KEY,
                push_enabled BOOLEAN DEFAULT TRUE,
                email_enabled BOOLEAN DEFAULT TRUE,
                sms_enabled BOOLEAN DEFAULT TRUE,
                categories JSONB DEFAULT '{}',
                quiet_hours_start TIME,
                quiet_hours_end TIME,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notif_status ON notifications(status)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "notification-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "notification-service", "error": str(e)}


class NotificationCreate(BaseModel):
    user_id: str
    channel: str = "push"
    title: str
    body: str
    category: Optional[str] = None
    priority: str = "normal"
    metadata: Optional[Dict[str, Any]] = None

class NotificationPrefsUpdate(BaseModel):
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None

@app.post("/api/v1/notifications/send")
async def send_notification(notif: NotificationCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        prefs = await conn.fetchrow("SELECT * FROM notification_preferences WHERE user_id=$1", notif.user_id)
        if prefs:
            channel_enabled = {
                "push": prefs["push_enabled"], "email": prefs["email_enabled"], "sms": prefs["sms_enabled"]
            }
            if not channel_enabled.get(notif.channel, True):
                return {"status": "skipped", "reason": f"{notif.channel} notifications disabled by user"}
        row = await conn.fetchrow(
            """INSERT INTO notifications (user_id, channel, title, body, category, priority, status, sent_at, metadata)
               VALUES ($1,$2,$3,$4,$5,$6,'sent',NOW(),$7) RETURNING *""",
            notif.user_id, notif.channel, notif.title, notif.body, notif.category, notif.priority,
            json.dumps(notif.metadata or {})
        )
        return {"status": "sent", "notification": dict(row)}

@app.post("/api/v1/notifications/bulk")
async def send_bulk(notifications: List[NotificationCreate], token: str = Depends(verify_token)):
    pool = await get_db_pool()
    results = []
    async with pool.acquire() as conn:
        for notif in notifications:
            row = await conn.fetchrow(
                """INSERT INTO notifications (user_id, channel, title, body, category, priority, status, sent_at, metadata)
                   VALUES ($1,$2,$3,$4,$5,$6,'sent',NOW(),$7) RETURNING id""",
                notif.user_id, notif.channel, notif.title, notif.body, notif.category, notif.priority,
                json.dumps(notif.metadata or {})
            )
            results.append(str(row["id"]))
    return {"sent": len(results), "ids": results}

@app.get("/api/v1/notifications")
async def list_notifications(user_id: Optional[str] = None, unread_only: bool = False,
                             skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        uid = user_id or token[:36]
        extra = "AND read_at IS NULL" if unread_only else ""
        rows = await conn.fetch(
            f"SELECT * FROM notifications WHERE user_id=$1 {extra} ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            uid, limit, skip
        )
        unread = await conn.fetchval("SELECT COUNT(*) FROM notifications WHERE user_id=$1 AND read_at IS NULL", uid)
        return {"notifications": [dict(r) for r in rows], "unread_count": unread}

@app.put("/api/v1/notifications/{notif_id}/read")
async def mark_read(notif_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("UPDATE notifications SET read_at=NOW() WHERE id=$1 RETURNING *", uuid.UUID(notif_id))
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")
        return dict(row)

@app.put("/api/v1/notifications/read-all")
async def mark_all_read(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE notifications SET read_at=NOW() WHERE user_id=$1 AND read_at IS NULL", token[:36])
        return {"updated": int(result.split()[-1])}

@app.get("/api/v1/notifications/preferences")
async def get_preferences(token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM notification_preferences WHERE user_id=$1", token[:36])
        if not row:
            return {"push_enabled": True, "email_enabled": True, "sms_enabled": True}
        return dict(row)

@app.put("/api/v1/notifications/preferences")
async def update_preferences(prefs: NotificationPrefsUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO notification_preferences (user_id, push_enabled, email_enabled, sms_enabled)
               VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO UPDATE SET
               push_enabled=COALESCE($2, notification_preferences.push_enabled),
               email_enabled=COALESCE($3, notification_preferences.email_enabled),
               sms_enabled=COALESCE($4, notification_preferences.sms_enabled), updated_at=NOW()""",
            token[:36], prefs.push_enabled, prefs.email_enabled, prefs.sms_enabled
        )
        return {"updated": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8123)
