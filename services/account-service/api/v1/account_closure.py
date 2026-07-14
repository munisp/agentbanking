import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from database import get_session
from models.account_closure import AccountClosureRequest

closure_router = APIRouter()


class CreateClosurePayload(BaseModel):
    accountId: str
    accountName: Optional[str] = None
    closureType: str
    reason: str
    requestedBy: Optional[str] = None


@closure_router.get("/list")
def list_closures(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    q = db.query(AccountClosureRequest).filter(
        AccountClosureRequest.tenant_id == tenant_id
    )
    if status:
        q = q.filter(AccountClosureRequest.status == status)
    total = q.count()
    items = q.order_by(AccountClosureRequest.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [r.to_dict() for r in items], "total": total, "page": page, "limit": limit}


@closure_router.get("/stats")
def get_stats(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    q = db.query(AccountClosureRequest).filter(
        AccountClosureRequest.tenant_id == tenant_id
    )
    total = q.count()
    by_status = {}
    for row in q.all():
        by_status[row.status] = by_status.get(row.status, 0) + 1
    return {"total": total, **by_status}


@closure_router.get("/{closure_id}")
def get_closure(
    closure_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    req = db.query(AccountClosureRequest).filter(
        AccountClosureRequest.id == closure_id,
        AccountClosureRequest.tenant_id == tenant_id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Closure request not found")
    return req.to_dict()


@closure_router.post("")
def create_closure(
    payload: CreateClosurePayload,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    record = AccountClosureRequest(
        id=str(uuid.uuid4()),
        account_id=payload.accountId,
        account_name=payload.accountName,
        closure_type=payload.closureType,
        reason=payload.reason,
        requested_by=payload.requestedBy or keycloak_id,
        status="pending",
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"message": "success", "data": record.to_dict()}
