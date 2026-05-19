"""
Edge Computing Service - Offline-capable transaction processing
Handles transaction caching, sync queue management, and connectivity monitoring
for low-connectivity environments common in remittance corridors
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from decimal import Decimal
import asyncpg
import uuid
import os
import logging
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/edge")
SYNC_SERVICE_URL = os.getenv("SYNC_SERVICE_URL", "http://localhost:8040")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Remittance Edge Service", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool: Optional[asyncpg.Pool] = None


class SyncStatus(str, Enum):
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class QueuedTransaction(BaseModel):
    sender_id: str
    recipient_id: str
    amount: Decimal
    currency: str
    description: Optional[str] = None
    device_id: str
    offline: bool = True


async def verify_bearer_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return authorization[7:]


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=3, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                device_id VARCHAR(100) NOT NULL,
                operation_type VARCHAR(50) NOT NULL,
                payload JSONB NOT NULL,
                sync_status VARCHAR(20) DEFAULT 'pending',
                retry_count INT DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                synced_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS device_registry (
                device_id VARCHAR(100) PRIMARY KEY,
                user_id VARCHAR(100) NOT NULL,
                last_seen TIMESTAMP DEFAULT NOW(),
                last_sync TIMESTAMP,
                is_online BOOLEAN DEFAULT TRUE,
                app_version VARCHAR(20),
                os_type VARCHAR(20),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_sync_queue_device ON sync_queue(device_id, sync_status);
            CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(sync_status);
        """)
    logger.info("Edge Computing Service started")


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


@app.post("/api/v1/edge/transactions/queue")
async def queue_transaction(txn: QueuedTransaction, token: str = Depends(verify_bearer_token)):
    import json
    txn_id = str(uuid.uuid4())
    payload = {
        "transaction_id": txn_id,
        "sender_id": txn.sender_id,
        "recipient_id": txn.recipient_id,
        "amount": str(txn.amount),
        "currency": txn.currency,
        "description": txn.description,
    }
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO sync_queue (device_id, operation_type, payload)
            VALUES ($1, 'transaction', $2::jsonb)""",
            txn.device_id, json.dumps(payload),
        )
    logger.info(f"Transaction queued from device {txn.device_id}")
    return {"queued_id": txn_id, "status": "pending", "device_id": txn.device_id}


@app.get("/api/v1/edge/sync/pending/{device_id}")
async def get_pending_sync(device_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sync_queue WHERE device_id = $1 AND sync_status = 'pending' ORDER BY created_at",
            device_id,
        )
    return {
        "device_id": device_id,
        "pending_count": len(rows),
        "items": [
            {"id": str(r["id"]), "type": r["operation_type"], "payload": r["payload"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ],
    }


@app.post("/api/v1/edge/sync/{device_id}")
async def trigger_sync(device_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sync_queue WHERE device_id = $1 AND sync_status = 'pending' ORDER BY created_at LIMIT 50",
            device_id,
        )
        synced = 0
        failed = 0
        for row in rows:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{SYNC_SERVICE_URL}/api/v1/sync/process",
                        json={"operation": row["operation_type"], "payload": row["payload"]},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code < 300:
                        await conn.execute(
                            "UPDATE sync_queue SET sync_status = 'synced', synced_at = NOW() WHERE id = $1",
                            row["id"],
                        )
                        synced += 1
                    else:
                        await conn.execute(
                            "UPDATE sync_queue SET sync_status = 'failed', retry_count = retry_count + 1, error_message = $2 WHERE id = $1",
                            row["id"], resp.text[:500],
                        )
                        failed += 1
            except Exception as e:
                await conn.execute(
                    "UPDATE sync_queue SET retry_count = retry_count + 1, error_message = $2 WHERE id = $1",
                    row["id"], str(e)[:500],
                )
                failed += 1

        await conn.execute(
            "UPDATE device_registry SET last_sync = NOW(), is_online = TRUE WHERE device_id = $1",
            device_id,
        )

    return {"device_id": device_id, "synced": synced, "failed": failed, "remaining": len(rows) - synced - failed}


@app.post("/api/v1/edge/devices/register")
async def register_device(device_id: str, user_id: str, app_version: str = "1.0.0", os_type: str = "android", token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO device_registry (device_id, user_id, app_version, os_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (device_id) DO UPDATE SET last_seen = NOW(), app_version = $3, is_online = TRUE""",
            device_id, user_id, app_version, os_type,
        )
    return {"device_id": device_id, "registered": True}


@app.post("/api/v1/edge/devices/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE device_registry SET last_seen = NOW(), is_online = TRUE WHERE device_id = $1",
            device_id,
        )
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM sync_queue WHERE device_id = $1 AND sync_status = 'pending'",
            device_id,
        )
    return {"device_id": device_id, "pending_sync": pending, "server_time": datetime.utcnow().isoformat()}


@app.get("/health")
async def health_check():
    db_ok = False
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass
    return {"status": "healthy" if db_ok else "degraded", "service": "edge-computing", "database": db_ok}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)


