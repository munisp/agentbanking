from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from database import get_session
from models.safe_deposit import DepositBox

safe_deposit_router = APIRouter()


@safe_deposit_router.get("/list")
def list_boxes(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    boxes = (
        db.query(DepositBox)
        .filter(DepositBox.tenant_id == tenant_id)
        .order_by(DepositBox.created_at.desc())
        .all()
    )
    return {"items": [b.to_dict() for b in boxes], "total": len(boxes)}


@safe_deposit_router.get("/stats")
def get_stats(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    boxes = db.query(DepositBox).filter(DepositBox.tenant_id == tenant_id).all()
    occupied = sum(1 for b in boxes if b.status == "occupied")
    available = sum(1 for b in boxes if b.status == "available")
    return {
        "total_boxes": len(boxes),
        "occupied": occupied,
        "available": available,
    }
