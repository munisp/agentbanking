from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import uuid

from database import get_session

savings_router = APIRouter()


class GoalCreate(BaseModel):
    name: str = ""
    target_amount: float = 0
    category: str = "other"
    target_date: Optional[str] = None
    auto_save: bool = False
    auto_amount: Optional[float] = None
    agent_id: str = ""


class ContributeBody(BaseModel):
    amount: float


def _row(r) -> dict:
    d = dict(r)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@savings_router.get("/goals")
def list_goals(
    agent_id: Optional[str] = None,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    params: dict = {"tid": tenant_id}
    filters = ["tenant_id = :tid"]
    if agent_id and agent_id != "undefined":
        filters.append("agent_keycloak_id = :kid")
        params["kid"] = agent_id
    where = " AND ".join(filters)
    rows = db.execute(
        text(f"SELECT * FROM agent_savings_goals WHERE {where} ORDER BY created_at DESC"),
        params,
    ).mappings().all()
    return {"goals": [_row(r) for r in rows]}


@savings_router.post("/goals", status_code=201)
def create_goal(
    body: GoalCreate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    agent_id = body.agent_id or keycloak_id
    row = db.execute(
        text("""
            INSERT INTO agent_savings_goals
              (id, tenant_id, agent_keycloak_id, name, target_amount, current_amount,
               category, target_date, auto_save, auto_amount, status)
            VALUES
              (:id, :tid, :kid, :name, :target_amount, 0,
               :category, :target_date, :auto_save, :auto_amount, 'active')
            RETURNING *
        """),
        {
            "id": str(uuid.uuid4()),
            "tid": tenant_id,
            "kid": agent_id,
            "name": body.name,
            "target_amount": body.target_amount,
            "category": body.category,
            "target_date": body.target_date,
            "auto_save": body.auto_save,
            "auto_amount": body.auto_amount or 0,
        },
    ).mappings().first()
    db.commit()
    return _row(row)


@savings_router.post("/goals/{goal_id}/contribute")
def contribute(
    goal_id: str,
    body: ContributeBody,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    row = db.execute(
        text("""
            UPDATE agent_savings_goals
            SET current_amount = current_amount + :amount,
                status = CASE WHEN current_amount + :amount >= target_amount THEN 'completed' ELSE status END,
                updated_at = NOW()
            WHERE id = :id AND tenant_id = :tid
            RETURNING *
        """),
        {"id": goal_id, "tid": tenant_id, "amount": body.amount},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.commit()
    return _row(row)


@savings_router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(
    goal_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    result = db.execute(
        text("DELETE FROM agent_savings_goals WHERE id = :id AND tenant_id = :tid"),
        {"id": goal_id, "tid": tenant_id},
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
