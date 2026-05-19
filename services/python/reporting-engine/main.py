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
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        template = await conn.fetchrow("SELECT * FROM report_templates WHERE id=$1", uuid.UUID(template_id))
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        import time
        start = time.time()
        result = {"template": template["name"], "parameters": parameters, "generated_at": datetime.utcnow().isoformat()}
        elapsed = int((time.time() - start) * 1000)
        row = await conn.fetchrow(
            """INSERT INTO report_executions (template_id, status, parameters, result, execution_time_ms, completed_at)
               VALUES ($1, 'completed', $2, $3, $4, NOW()) RETURNING *""",
            uuid.UUID(template_id), json.dumps(parameters or {}), json.dumps(result), elapsed
        )
        return dict(row)

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
