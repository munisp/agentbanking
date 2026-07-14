"""POS Request API endpoints for agent-service"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from database import get_session
from models import POSRequest, POSRequestStatus, Agent, AgentBusiness
from adapters import AuditServiceAdapter
from schemas import (
    POSRequestCreate,
    POSRequestUpdate,
    POSRequestReview,
    POSRequestAssign,
    POSRequestResponse,
    Context,
    AuditEventSchema,
)
import logging

logger = logging.getLogger(__name__)

pos_request_router = APIRouter(prefix="/pos-requests", tags=["pos-requests"])


# ============================================================================
# AGENT ENDPOINTS - Agents can create and manage their own POS requests
# ============================================================================


@pos_request_router.post("", response_model=POSRequestResponse, status_code=201)
def create_pos_request(
    payload: POSRequestCreate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Create a new POS terminal request (agent action)"""

    # Get agent info
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id, Agent.tenant_id == tenant_id)
        .first()
    )

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # If business_id provided, validate it belongs to this agent
    business_name = None
    if payload.business_id:
        business = (
            db.query(AgentBusiness)
            .filter(
                AgentBusiness.business_id == payload.business_id,
                AgentBusiness.agent_keycloak_id == keycloak_id,
                AgentBusiness.tenant_id == tenant_id,
            )
            .first()
        )
        if business:
            business_name = business.business_name

    # Create request
    pos_request = POSRequest(
        agent_id=agent.id,
        agent_keycloak_id=agent.keycloak_id,
        agent_name=agent.name,
        agent_email=agent.email,
        agent_phone=agent.phone_number,
        business_id=payload.business_id,
        business_name=business_name,
        preferred_model=payload.preferred_model,
        quantity=payload.quantity,
        deployment_location=payload.deployment_location,
        deployment_address=payload.deployment_address,
        city=payload.city,
        state=payload.state,
        justification=payload.justification,
        status=POSRequestStatus.PENDING,
        tenant_id=tenant_id,
    )

    db.add(pos_request)
    db.commit()
    db.refresh(pos_request)

    logger.info(f"POS request created: {pos_request.id} by agent {agent.keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="CREATE",
            event_data={
                "resource": "pos_request",
                "request_id": pos_request.id,
                "quantity": pos_request.quantity,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return pos_request


@pos_request_router.get("/my-requests", response_model=List[POSRequestResponse])
def get_my_pos_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get all POS requests for the current agent"""

    query = db.query(POSRequest).filter(
        POSRequest.agent_keycloak_id == keycloak_id,
        POSRequest.tenant_id == tenant_id,
        POSRequest.deleted_at.is_(None),
    )

    if status:
        try:
            status_enum = POSRequestStatus(status)
            query = query.filter(POSRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    requests = query.order_by(POSRequest.created_at.desc()).all()

    return requests


@pos_request_router.get("/{request_id}", response_model=POSRequestResponse)
def get_pos_request(
    request_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get a specific POS request (agent can only see their own)"""

    pos_request = (
        db.query(POSRequest)
        .filter(
            POSRequest.id == request_id,
            POSRequest.agent_keycloak_id == keycloak_id,
            POSRequest.tenant_id == tenant_id,
            POSRequest.deleted_at.is_(None),
        )
        .first()
    )

    if not pos_request:
        raise HTTPException(status_code=404, detail="POS request not found")

    return pos_request


@pos_request_router.patch("/{request_id}", response_model=POSRequestResponse)
def update_pos_request(
    request_id: str,
    payload: POSRequestUpdate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Update a POS request (only allowed for pending requests)"""

    pos_request = (
        db.query(POSRequest)
        .filter(
            POSRequest.id == request_id,
            POSRequest.agent_keycloak_id == keycloak_id,
            POSRequest.tenant_id == tenant_id,
            POSRequest.deleted_at.is_(None),
        )
        .first()
    )

    if not pos_request:
        raise HTTPException(status_code=404, detail="POS request not found")

    if pos_request.status != POSRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only update pending requests")

    # Update fields
    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pos_request, field, value)

    db.commit()
    db.refresh(pos_request)

    logger.info(f"POS request updated: {request_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "pos_request",
                "request_id": pos_request.id,
                "updated_fields": list(update_data.keys()),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return pos_request


@pos_request_router.delete("/{request_id}", status_code=204)
def cancel_pos_request(
    request_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Cancel a POS request (only allowed for pending requests)"""

    pos_request = (
        db.query(POSRequest)
        .filter(
            POSRequest.id == request_id,
            POSRequest.agent_keycloak_id == keycloak_id,
            POSRequest.tenant_id == tenant_id,
            POSRequest.deleted_at.is_(None),
        )
        .first()
    )

    if not pos_request:
        raise HTTPException(status_code=404, detail="POS request not found")

    if pos_request.status != POSRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only cancel pending requests")

    pos_request.status = POSRequestStatus.CANCELLED
    db.commit()

    logger.info(f"POS request cancelled: {request_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "pos_request",
                "request_id": pos_request.id,
                "status": str(pos_request.status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return None


# ============================================================================
# ADMIN ENDPOINTS - Admins can view all requests and approve/assign
# ============================================================================


@pos_request_router.get("/admin/all", response_model=List[POSRequestResponse])
def get_all_pos_requests_admin(
    status: Optional[str] = Query(None, description="Filter by status"),
    agent_id: Optional[str] = Query(None, description="Filter by agent keycloak ID"),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get all POS requests (admin only)"""

    query = db.query(POSRequest).filter(
        POSRequest.tenant_id == tenant_id,
        POSRequest.deleted_at.is_(None),
    )

    if status:
        try:
            status_enum = POSRequestStatus(status)
            query = query.filter(POSRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if agent_id:
        query = query.filter(POSRequest.agent_keycloak_id == agent_id)

    requests = query.order_by(POSRequest.created_at.desc()).all()

    return requests


@pos_request_router.post("/{request_id}/review", response_model=POSRequestResponse)
def review_pos_request(
    request_id: str,
    payload: POSRequestReview,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Approve or reject a POS request (admin only)"""

    pos_request = (
        db.query(POSRequest)
        .filter(
            POSRequest.id == request_id,
            POSRequest.tenant_id == tenant_id,
            POSRequest.deleted_at.is_(None),
        )
        .first()
    )

    if not pos_request:
        raise HTTPException(status_code=404, detail="POS request not found")

    if pos_request.status != POSRequestStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot review request with status: {pos_request.status.value}",
        )

    # Update status based on action
    if payload.action == "approve":
        pos_request.status = POSRequestStatus.APPROVED
    elif payload.action == "reject":
        pos_request.status = POSRequestStatus.REJECTED
        if not payload.rejection_reason:
            raise HTTPException(
                status_code=400, detail="Rejection reason is required when rejecting"
            )
        pos_request.rejection_reason = payload.rejection_reason

    pos_request.reviewed_by = keycloak_id
    pos_request.reviewed_at = datetime.utcnow()
    pos_request.admin_notes = payload.admin_notes

    db.commit()
    db.refresh(pos_request)

    logger.info(f"POS request {request_id} {payload.action}ed by {keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "pos_request_review",
                "request_id": pos_request.id,
                "action": payload.action,
                "status": str(pos_request.status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return pos_request


@pos_request_router.post("/{request_id}/assign", response_model=POSRequestResponse)
def assign_terminal_to_request(
    request_id: str,
    payload: POSRequestAssign,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Assign a POS terminal to an approved request (admin only)"""

    pos_request = (
        db.query(POSRequest)
        .filter(
            POSRequest.id == request_id,
            POSRequest.tenant_id == tenant_id,
            POSRequest.deleted_at.is_(None),
        )
        .first()
    )

    if not pos_request:
        raise HTTPException(status_code=404, detail="POS request not found")

    if pos_request.status != POSRequestStatus.APPROVED:
        raise HTTPException(
            status_code=400, detail="Can only assign terminals to approved requests"
        )

    # Update request with assignment info
    pos_request.status = POSRequestStatus.ASSIGNED
    pos_request.assigned_terminal_id = payload.terminal_id
    pos_request.assigned_terminal_serial = payload.terminal_serial
    pos_request.assigned_at = datetime.utcnow()
    if payload.admin_notes:
        pos_request.admin_notes = (
            f"{pos_request.admin_notes or ''}\n{payload.admin_notes}".strip()
        )
    # Store geo-fence if provided
    if hasattr(payload, "geofence_latitude"):
        pos_request.geofence_latitude = payload.geofence_latitude
        pos_request.geofence_longitude = payload.geofence_longitude
        pos_request.geofence_radius_m = payload.geofence_radius_m

    db.commit()
    db.refresh(pos_request)

    logger.info(
        f"Terminal {payload.terminal_id} assigned to request {request_id} by {keycloak_id}"
    )

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "pos_request_assignment",
                "request_id": pos_request.id,
                "terminal_id": payload.terminal_id,
                "status": str(pos_request.status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return pos_request


@pos_request_router.get("/admin/stats")
def get_pos_request_stats(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get POS request statistics (admin only)"""

    base_query = db.query(POSRequest).filter(
        POSRequest.tenant_id == tenant_id,
        POSRequest.deleted_at.is_(None),
    )

    total = base_query.count()
    pending = base_query.filter(POSRequest.status == POSRequestStatus.PENDING).count()
    approved = base_query.filter(POSRequest.status == POSRequestStatus.APPROVED).count()
    assigned = base_query.filter(POSRequest.status == POSRequestStatus.ASSIGNED).count()
    rejected = base_query.filter(POSRequest.status == POSRequestStatus.REJECTED).count()

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "assigned": assigned,
        "rejected": rejected,
    }
