#!/usr/bin/env python3
"""
TigerBeetle Edge Service
Edge computing service for TigerBeetle ledger operations
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncpg
import aioredis
from fastapi import FastAPI, HTTPException
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres123@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8143"))

app = FastAPI(title="TigerBeetle Edge Service", version="1.0.0")
apply_middleware(app, enable_auth=True)

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/tigerbeetle_edge")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

db_pool = None
redis_client = None

class EdgeTransaction(BaseModel):
    transaction_id: str
    account_id: str
    amount: float
    transaction_type: str
    edge_location: str

async def init_database():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS edge_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(255) UNIQUE NOT NULL,
                    account_id VARCHAR(255) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    transaction_type VARCHAR(50) NOT NULL,
                    edge_location VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'PENDING',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    INDEX idx_transaction_id (transaction_id),
                    INDEX idx_account_id (account_id)
                )
            """)
        logger.info("TigerBeetle Edge database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def init_redis():
    global redis_client
    try:
        redis_client = await aioredis.from_url(REDIS_URL)
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    await init_database()
    await init_redis()

@app.on_event("shutdown")
async def shutdown_event():
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()

@app.get("/health")
async def health_check():
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        await redis_client.ping()
        return {"status": "healthy", "service": "tigerbeetle-edge", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/api/v1/transactions")
async def process_edge_transaction(transaction: EdgeTransaction):
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO edge_transactions (transaction_id, account_id, amount, transaction_type, edge_location)
                VALUES ($1, $2, $3, $4, $5) RETURNING id""", transaction.transaction_id, transaction.account_id, transaction.amount, 
            transaction.transaction_type, transaction.edge_location)
        
        # Cache for quick access
        await redis_client.setex(f"edge_tx:{transaction.transaction_id}", 3600, json.dumps(transaction.dict()))
        
        return {"status": "success", "message": "Edge transaction processed", "transaction_id": transaction.transaction_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process transaction: {str(e)}")

@app.get("/api/v1/transactions/{transaction_id}")
async def get_edge_transaction(transaction_id: str):
    try:
        # Check cache first
        cached = await redis_client.get(f"edge_tx:{transaction_id}")
        if cached:
            return json.loads(cached)
        
        # Get from database
        async with db_pool.acquire() as conn:
            tx = await conn.fetchrow("""
                SELECT * FROM edge_transactions WHERE transaction_id = $1
            """, transaction_id)
            
            if not tx:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            return {
                "transaction_id": tx['transaction_id'],
                "account_id": tx['account_id'],
                "amount": float(tx['amount']),
                "transaction_type": tx['transaction_type'],
                "edge_location": tx['edge_location'],
                "status": tx['status'],
                "created_at": tx['created_at'].isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=SERVICE_PORT, reload=False, log_level="info")

