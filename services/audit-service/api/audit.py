from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from services import AuditService
from schemas import AuditEventSchema, Pagination
from database import get_session
from utils import create_logger

audit_router = APIRouter()

logger = create_logger(__name__)

@audit_router.post("")
def create_audit(
    payload: AuditEventSchema,
    db: Session = Depends(get_session),
):
    try:
        service = AuditService(db)
        return service.create_audit(payload)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during create_audit: {str(e)}")
        raise HTTPException(status_code=500, detail="Create audit failed.")

@audit_router.get("/tenant/{tenant_id}")
def fetch_tenant_audits(
    tenant_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_session),
):
    try:
        pagination = Pagination(page=page, limit=limit)
        service = AuditService(db)

        return service.fetch_tenant_audits(
            tenant_id=tenant_id,
            pagination=pagination,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_tenant_audits: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch tenant audits failed.")

@audit_router.get("")
def fetch_all_audits(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_session),
):
    try:
        pagination = Pagination(page=page, limit=limit)
        service = AuditService(db)

        return service.fetch_all_audits(pagination)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_all_audits: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch all audits failed.")
