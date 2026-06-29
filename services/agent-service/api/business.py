"""Business API endpoints for agent-service"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from database import get_session
from models import AgentBusiness, Agent
from schemas import (
    BusinessCreate,
    BusinessLinkAgent,
    BusinessResponse,
    Context,
    AuditEventSchema,
)
from adapters import AuditServiceAdapter
import logging
import uuid

logger = logging.getLogger(__name__)

business_router = APIRouter(prefix="/businesses", tags=["businesses"])


@business_router.post("/create", response_model=BusinessResponse)
def create_business_for_agent(
    payload: BusinessCreate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """
    Create a new business for the current agent.
    This creates an unverified business that can go through KYB verification.
    """
    # Verify agent exists
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id, Agent.tenant_id == tenant_id)
        .first()
    )

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Generate business ID if not provided
    business_id = payload.business_id or f"BUS_{uuid.uuid4().hex[:8].upper()}"

    # Check if business already exists
    existing = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.business_id == business_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=409, detail="Business already exists")

    # Create new business (unverified by default)
    new_business = AgentBusiness(
        business_id=business_id,
        tenant_id=tenant_id,
        agent_id=agent.id,
        agent_keycloak_id=keycloak_id,
        business_name=payload.business_name,
        registration_number=payload.registration_number,
        tin=payload.tin,
        business_type=payload.business_type,
        industry=payload.industry,
        country=payload.country,
        address=payload.address,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        documents=payload.documents,
        is_verified=False,  # Agent-created businesses start unverified
        verification_status="pending",
        verification_date=None,
        verification_path=None,
        business_metadata=payload.metadata,
    )

    db.add(new_business)
    db.commit()
    db.refresh(new_business)
    logger.info(
        f"Created new business {business_id} for agent {keycloak_id} in tenant {tenant_id}"
    )

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="CREATE",
            event_data={
                "resource": "business",
                "business_id": new_business.business_id,
                "business_name": new_business.business_name,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return new_business


@business_router.post("/sync", response_model=BusinessResponse)
def sync_business_from_kyb(
    payload: BusinessCreate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Sync a verified business from KYB service to agent service.
    This is called when a business is verified through KYB.
    """
    # Check if business already exists
    existing_business = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.business_id == payload.business_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .first()
    )

    if existing_business:
        # Update existing business
        existing_business.business_name = payload.business_name
        existing_business.registration_number = payload.registration_number
        existing_business.tin = payload.tin
        existing_business.business_type = payload.business_type
        existing_business.industry = payload.industry
        existing_business.country = payload.country
        existing_business.address = payload.address
        existing_business.contact_email = payload.contact_email
        existing_business.contact_phone = payload.contact_phone
        existing_business.documents = payload.documents
        existing_business.is_verified = payload.is_verified
        existing_business.verification_status = payload.verification_status
        existing_business.verification_date = payload.verification_date
        existing_business.verification_path = payload.verification_path
        existing_business.business_metadata = payload.metadata

        db.commit()
        db.refresh(existing_business)
        logger.info(
            f"Updated business {payload.business_id} from KYB for tenant {tenant_id}"
        )

        AuditServiceAdapter().create_audit(
            payload=AuditEventSchema(
                actor_id="system",
                tenant_id=tenant_id,
                event_type="UPDATE",
                event_data={
                    "resource": "business_sync",
                    "business_id": existing_business.business_id,
                    "verification_status": existing_business.verification_status,
                },
                timestamp=datetime.utcnow().isoformat(),
            ),
            context=Context(tenant_id=tenant_id, keycloak_id="system"),
        )

        return existing_business

    # Create new business
    new_business = AgentBusiness(
        business_id=payload.business_id,
        tenant_id=tenant_id,
        business_name=payload.business_name,
        registration_number=payload.registration_number,
        tin=payload.tin,
        business_type=payload.business_type,
        industry=payload.industry,
        country=payload.country,
        address=payload.address,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        documents=payload.documents,
        is_verified=payload.is_verified,
        verification_status=payload.verification_status,
        verification_date=payload.verification_date,
        verification_path=payload.verification_path,
        business_metadata=payload.metadata,
    )

    db.add(new_business)
    db.commit()
    db.refresh(new_business)
    logger.info(
        f"Created new business {payload.business_id} from KYB for tenant {tenant_id}"
    )

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id="system",
            tenant_id=tenant_id,
            event_type="CREATE",
            event_data={
                "resource": "business_sync",
                "business_id": new_business.business_id,
                "verification_status": new_business.verification_status,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id="system"),
    )

    return new_business


@business_router.post("/link-agent", response_model=BusinessResponse)
def link_business_to_agent(
    payload: BusinessLinkAgent,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Link a verified business to an agent"""
    # Find the business
    business = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.business_id == payload.business_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .first()
    )

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if not business.is_verified:
        raise HTTPException(
            status_code=400, detail="Business must be verified before linking to agent"
        )

    # Find the agent
    agent = (
        db.query(Agent)
        .filter(
            Agent.keycloak_id == payload.agent_keycloak_id,
            Agent.tenant_id == tenant_id,
        )
        .first()
    )

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Link business to agent
    business.agent_id = agent.id
    business.agent_keycloak_id = agent.keycloak_id

    db.commit()
    db.refresh(business)
    logger.info(f"Linked business {business.business_id} to agent {agent.keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=payload.agent_keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "business_link",
                "business_id": business.business_id,
                "agent_keycloak_id": agent.keycloak_id,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=payload.agent_keycloak_id),
    )

    return business


@business_router.get("/tenant", response_model=List[BusinessResponse])
def get_all_tenant_businesses(
    verified_only: bool = False,
    agent_keycloak_id: Optional[str] = None,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get all businesses for the current tenant, optionally filtered by verification status or agent"""
    query = db.query(AgentBusiness).filter(AgentBusiness.tenant_id == tenant_id)

    if verified_only:
        query = query.filter(AgentBusiness.is_verified == True)

    if agent_keycloak_id:
        query = query.filter(AgentBusiness.agent_keycloak_id == agent_keycloak_id)

    businesses = query.order_by(AgentBusiness.created_at.desc()).all()

    return businesses


@business_router.get("", response_model=List[BusinessResponse])
def get_all_businesses(
    verified_only: bool = False,
    agent_keycloak_id: Optional[str] = None,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get all businesses, optionally filtered by verification status or agent (alias for /tenant)"""
    query = db.query(AgentBusiness).filter(AgentBusiness.tenant_id == tenant_id)

    if verified_only:
        query = query.filter(AgentBusiness.is_verified == True)

    if agent_keycloak_id:
        query = query.filter(AgentBusiness.agent_keycloak_id == agent_keycloak_id)

    businesses = query.order_by(AgentBusiness.created_at.desc()).all()

    return businesses


@business_router.get("/{business_id}", response_model=BusinessResponse)
def get_business(
    business_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get a specific business by ID"""
    business = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.business_id == business_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .first()
    )

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    return business


@business_router.get(
    "/agent/{agent_keycloak_id}", response_model=List[BusinessResponse]
)
def get_agent_businesses(
    agent_keycloak_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get all businesses for a specific agent"""
    # Verify agent exists
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == agent_keycloak_id, Agent.tenant_id == tenant_id)
        .first()
    )

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    businesses = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.agent_keycloak_id == agent_keycloak_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .order_by(AgentBusiness.created_at.desc())
        .all()
    )

    return businesses


@business_router.delete("/unlink/{business_id}")
def unlink_business_from_agent(
    business_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Unlink a business from its agent"""
    business = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.business_id == business_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .first()
    )

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    business.agent_id = None
    business.agent_keycloak_id = None

    db.commit()
    db.refresh(business)
    logger.info(f"Unlinked business {business_id} from agent")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "business_unlink",
                "business_id": business.business_id,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return {"message": "Business unlinked successfully"}


@business_router.patch("/{business_id}", response_model=BusinessResponse)
def update_business(
    business_id: str,
    payload: BusinessCreate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Update a business (agent can only update their own businesses)"""
    business = (
        db.query(AgentBusiness)
        .filter(
            AgentBusiness.business_id == business_id,
            AgentBusiness.tenant_id == tenant_id,
        )
        .first()
    )

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Check if agent owns this business
    if business.agent_keycloak_id != keycloak_id:
        raise HTTPException(
            status_code=403, detail="You can only update your own businesses"
        )

    # Update fields if provided
    if payload.business_name:
        business.business_name = payload.business_name
    if payload.registration_number:
        business.registration_number = payload.registration_number
    if payload.tin:
        business.tin = payload.tin
    if payload.business_type:
        business.business_type = payload.business_type
    if payload.industry:
        business.industry = payload.industry
    if payload.country:
        business.country = payload.country
    if payload.address:
        business.address = payload.address
    if payload.contact_email:
        business.contact_email = payload.contact_email
    if payload.contact_phone:
        business.contact_phone = payload.contact_phone
    if payload.documents:
        business.documents = payload.documents
    if payload.metadata:
        business.business_metadata = payload.metadata

    db.commit()
    db.refresh(business)
    logger.info(f"Updated business {business_id} for agent {keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "business",
                "business_id": business.business_id,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return business

