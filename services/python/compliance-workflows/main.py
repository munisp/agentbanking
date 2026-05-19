"""
Compliance Workflows
Port: 8117
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

app = FastAPI(title="Compliance Workflows", description="Compliance Workflows for Remittance Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS compliance_workflows (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(255) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                current_step VARCHAR(50) DEFAULT 'initiated',
                status VARCHAR(20) DEFAULT 'in_progress',
                steps_completed JSONB DEFAULT '[]',
                assigned_to VARCHAR(255),
                priority VARCHAR(20) DEFAULT 'normal',
                due_date TIMESTAMPTZ,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_cw_status ON compliance_workflows(status);
            CREATE INDEX IF NOT EXISTS idx_cw_assigned ON compliance_workflows(assigned_to)
        """)

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "compliance-workflows", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "compliance-workflows", "error": str(e)}


class WorkflowCreate(BaseModel):
    workflow_type: str
    entity_id: str
    entity_type: str
    assigned_to: Optional[str] = None
    priority: str = "normal"
    due_date: Optional[datetime] = None

class WorkflowStepUpdate(BaseModel):
    step_name: str
    status: str
    notes: Optional[str] = None

@app.post("/api/v1/compliance-workflows")
async def create_workflow(wf: WorkflowCreate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO compliance_workflows (workflow_type, entity_id, entity_type, assigned_to, priority, due_date)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            wf.workflow_type, wf.entity_id, wf.entity_type, wf.assigned_to, wf.priority, wf.due_date
        )
        return dict(row)

@app.get("/api/v1/compliance-workflows")
async def list_workflows(status: Optional[str] = None, assigned_to: Optional[str] = None,
                         skip: int = 0, limit: int = 50, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conditions, params = [], []
        idx = 1
        if status:
            conditions.append(f"status=${idx}"); params.append(status); idx += 1
        if assigned_to:
            conditions.append(f"assigned_to=${idx}"); params.append(assigned_to); idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([limit, skip])
        rows = await conn.fetch(f"SELECT * FROM compliance_workflows {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}", *params)
        return {"workflows": [dict(r) for r in rows]}

@app.put("/api/v1/compliance-workflows/{wf_id}/step")
async def advance_step(wf_id: str, step: WorkflowStepUpdate, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        wf = await conn.fetchrow("SELECT * FROM compliance_workflows WHERE id=$1", uuid.UUID(wf_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        steps = json.loads(wf["steps_completed"]) if isinstance(wf["steps_completed"], str) else list(wf["steps_completed"])
        steps.append({"step": step.step_name, "status": step.status, "notes": step.notes, "completed_at": datetime.utcnow().isoformat(), "by": token[:36]})
        new_status = "completed" if step.status == "final" else "in_progress"
        row = await conn.fetchrow(
            "UPDATE compliance_workflows SET current_step=$1, steps_completed=$2, status=$3, updated_at=NOW() WHERE id=$4 RETURNING *",
            step.step_name, json.dumps(steps), new_status, uuid.UUID(wf_id)
        )
        return dict(row)

@app.get("/api/v1/compliance-workflows/{wf_id}")
async def get_workflow(wf_id: str, token: str = Depends(verify_token)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM compliance_workflows WHERE id=$1", uuid.UUID(wf_id))
        if not row:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return dict(row)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8117)
