"""
Scheduler Service
Port: 8131
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

app = FastAPI(title="Scheduler Service", description="Scheduler Service for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_name VARCHAR(100) NOT NULL,
                job_type VARCHAR(50) NOT NULL,
                cron_expression VARCHAR(100),
                endpoint_url TEXT,
                payload JSONB DEFAULT '{}',
                is_active BOOLEAN DEFAULT TRUE,
                last_run_at TIMESTAMPTZ,
                next_run_at TIMESTAMPTZ,
                last_status VARCHAR(20),
                retry_count INT DEFAULT 0,
                max_retries INT DEFAULT 3,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS job_executions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_id UUID REFERENCES scheduled_jobs(id),
                status VARCHAR(20) NOT NULL,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ,
                duration_ms INT,
                result JSONB,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_job_active ON scheduled_jobs(is_active, next_run_at)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "scheduler-service", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "scheduler-service", "error": str(e)}


class JobCreate(BaseModel):
    job_name: str
    job_type: str
    cron_expression: Optional[str] = None
    endpoint_url: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    max_retries: int = 3

@app.post("/api/v1/scheduler/jobs")
async def create_job(job: JobCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO scheduled_jobs (job_name, job_type, cron_expression, endpoint_url, payload, max_retries)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            job.job_name, job.job_type, job.cron_expression, job.endpoint_url, json.dumps(job.payload or {}), job.max_retries
        )
        return dict(row)

@app.get("/api/v1/scheduler/jobs")
async def list_jobs(active_only: bool = True, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if active_only:
            rows = await conn.fetch("SELECT * FROM scheduled_jobs WHERE is_active=TRUE ORDER BY job_name")
        else:
            rows = await conn.fetch("SELECT * FROM scheduled_jobs ORDER BY job_name")
        return {"jobs": [dict(r) for r in rows]}

@app.post("/api/v1/scheduler/jobs/{job_id}/trigger")
async def trigger_job(job_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM scheduled_jobs WHERE id=$1", uuid.UUID(job_id))
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        import time
        start = time.time()
        result = {"triggered": True, "job_name": job["job_name"], "at": datetime.utcnow().isoformat()}
        elapsed = int((time.time() - start) * 1000)
        await conn.execute(
            "INSERT INTO job_executions (job_id, status, completed_at, duration_ms, result) VALUES ($1,'completed',NOW(),$2,$3)",
            uuid.UUID(job_id), elapsed, json.dumps(result)
        )
        await conn.execute("UPDATE scheduled_jobs SET last_run_at=NOW(), last_status='completed' WHERE id=$1", uuid.UUID(job_id))
        return result

@app.put("/api/v1/scheduler/jobs/{job_id}/toggle")
async def toggle_job(job_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("UPDATE scheduled_jobs SET is_active=NOT is_active WHERE id=$1 RETURNING *", uuid.UUID(job_id))
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(row)

@app.get("/api/v1/scheduler/jobs/{job_id}/history")
async def job_history(job_id: str, limit: int = 20, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM job_executions WHERE job_id=$1 ORDER BY started_at DESC LIMIT $2", uuid.UUID(job_id), limit)
        return {"executions": [dict(r) for r in rows]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8131)
