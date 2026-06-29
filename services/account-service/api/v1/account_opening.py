import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from database import get_session
from models.account_opening import AccountOpeningApplication

opening_router = APIRouter()


class CreateApplicationPayload(BaseModel):
    fullName: str
    productType: str
    bvn: str
    nin: Optional[str] = None
    phoneNumber: str
    email: Optional[str] = None
    dateOfBirth: Optional[str] = None
    address: Optional[str] = None
    tier: Optional[str] = None


@opening_router.get("/list")
def list_applications(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    q = db.query(AccountOpeningApplication).filter(
        AccountOpeningApplication.tenant_id == tenant_id
    )
    if status:
        q = q.filter(AccountOpeningApplication.status == status)
    total = q.count()
    items = q.order_by(AccountOpeningApplication.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [a.to_dict() for a in items], "total": total, "page": page, "limit": limit}


@opening_router.get("/stats")
def get_stats(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    q = db.query(AccountOpeningApplication).filter(
        AccountOpeningApplication.tenant_id == tenant_id
    )
    total = q.count()
    by_status = {}
    for row in q.all():
        by_status[row.status] = by_status.get(row.status, 0) + 1
    return {"total": total, **by_status}


@opening_router.get("/{application_id}")
def get_application(
    application_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    app = db.query(AccountOpeningApplication).filter(
        AccountOpeningApplication.id == application_id,
        AccountOpeningApplication.tenant_id == tenant_id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.to_dict()


@opening_router.post("")
def create_application(
    payload: CreateApplicationPayload,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    app_ref = f"ACOP-{uuid.uuid4().hex[:8].upper()}"
    record = AccountOpeningApplication(
        id=str(uuid.uuid4()),
        application_ref=app_ref,
        full_name=payload.fullName,
        product_type=payload.productType,
        bvn=payload.bvn,
        nin=payload.nin,
        phone_number=payload.phoneNumber,
        email=payload.email,
        date_of_birth=payload.dateOfBirth,
        address=payload.address,
        tier=payload.tier,
        status="pending",
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"message": "success", "data": record.to_dict()}
