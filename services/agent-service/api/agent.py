from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from datetime import datetime

from utils import (
    create_logger,
    AgentStatus,
    AgentOnboardingStatus,
    KycVerificationStatus,
)
from adapters import AuditServiceAdapter, ComplianceServiceAdapter
from database import get_session
from models import Agent
from schemas import (
    CreateAgentSchema,
    UpdateAgentSchema,
    AgentOnboardingSchema,
    Context,
    AuditEventSchema,
)

logger = create_logger(__name__)

agent_router = APIRouter()


@agent_router.post("")
def create_agent(
    payload: CreateAgentSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Create a new agent profile (called by orchestrator after Keycloak registration)."""
    if payload.agent_role == AgentRole.AGENT:
        raise HTTPException(
            status_code=400,
            detail="Agent is not allowed as an agent creation role.",
        )
    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    existing = (
        db.query(Agent)
        .filter(Agent.email == payload.email, Agent.tenant_id == context.tenant_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Agent already exists.")

    agent = Agent(
        first_name=payload.first_name,
        last_name=payload.last_name,
        name=f"{payload.first_name} {payload.last_name}",
        email=payload.email,
        phone_number=payload.phone,
        uin=payload.uin,
        keycloak_id=context.keycloak_id,
        tenant_id=context.tenant_id,
        agent_role=payload.agent_role,
        business_name=payload.business_name,
        business_address=payload.business_address,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        lga=payload.lga,
        status=AgentStatus.PENDING_APPROVAL,
        kyc_verification_status=KycVerificationStatus.PENDING,
        onboarding_status=AgentOnboardingStatus.IN_PROGRESS,
        invited_by=payload.invited_by,
        inviter_type=payload.inviter_type,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    logger.info(f"Agent created: {agent}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=context.keycloak_id,
            tenant_id=context.tenant_id,
            event_type="CREATE",
            event_data={
                "resource": "agent",
                "agent_keycloak_id": agent.keycloak_id,
                "email": agent.email,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=context,
    )

    ComplianceServiceAdapter().push_kyc_update(
        agent_id=str(agent.id),
        kyc_status=agent.kyc_verification_status.value,
        tenant_id=context.tenant_id,
        agent_name=agent.name,
    )

    return responses.JSONResponse(
        content={"message": "success", "agent": agent.to_dict()},
        status_code=200,
    )


@agent_router.get("/tenant")
def get_tenant_agents(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get all agents for a tenant."""
    agents = (
        db.query(Agent)
        .filter(Agent.tenant_id == tenant_id)
        .order_by(Agent.created_at)
        .all()
    )
    return {"message": "success", "agents": [a.to_dict(rules=("-businesses",)) for a in agents]}


@agent_router.get("/invited")
def get_invited_agents(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get all agents invited by the current user."""
    agents = (
        db.query(Agent)
        .filter(Agent.tenant_id == tenant_id, Agent.invited_by == keycloak_id)
        .order_by(Agent.created_at)
        .all()
    )
    return {"message": "success", "agents": [a.to_dict() for a in agents]}


@agent_router.get("/{keycloak_id_param}")
def get_agent(
    keycloak_id_param: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get a specific agent by keycloak_id."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id_param, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return {"message": "success", "agent": agent.to_dict()}


@agent_router.patch("/{keycloak_id_param}")
def update_agent(
    keycloak_id_param: str,
    payload: UpdateAgentSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Update an agent's profile."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id_param, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent",
                "agent_keycloak_id": agent.keycloak_id,
                "updated_fields": list(update_data.keys()),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return {"message": "success", "agent": agent.to_dict()}


@agent_router.post("/{keycloak_id_param}/onboarding")
def complete_onboarding(
    keycloak_id_param: str,
    payload: AgentOnboardingSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Complete an agent's onboarding with business details."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id_param, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.business_name = payload.business_name
    agent.business_address = payload.business_address
    agent.city = payload.city
    agent.state = payload.state
    agent.postal_code = payload.postal_code
    agent.lga = payload.lga
    agent.onboarding_status = AgentOnboardingStatus.COMPLETED

    db.commit()
    db.refresh(agent)

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent_onboarding",
                "agent_keycloak_id": agent.keycloak_id,
                "onboarding_status": str(agent.onboarding_status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return {"message": "success", "agent": agent.to_dict()}


@agent_router.post("/{keycloak_id_param}/approve")
def approve_agent(
    keycloak_id_param: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Approve an agent (admin action)."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id_param, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.status = AgentStatus.ACTIVE
    agent.is_approved = True
    agent.approved_by = keycloak_id

    db.commit()
    db.refresh(agent)

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent_approval",
                "agent_keycloak_id": agent.keycloak_id,
                "approved": True,
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return {"message": "success", "agent": agent.to_dict()}


@agent_router.post("/{keycloak_id_param}/suspend")
def suspend_agent(
    keycloak_id_param: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Suspend an agent."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id_param, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.status = AgentStatus.SUSPENDED
    db.commit()
    db.refresh(agent)

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent_status",
                "agent_keycloak_id": agent.keycloak_id,
                "status": str(agent.status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    return {"message": "success", "agent": agent.to_dict()}


@agent_router.post("/kyc/save")
def save_agent_kyc_state(
    payload: dict,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Save KYC URL for an agent (called by orchestrator)."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.kyc_verification_url = payload.get("kyc_url")
    db.commit()
    db.refresh(agent)

    logger.info(f"KYC URL saved for agent {keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent_kyc",
                "agent_keycloak_id": agent.keycloak_id,
                "kyc_url_saved": bool(payload.get("kyc_url")),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    ComplianceServiceAdapter().push_kyc_update(
        agent_id=str(agent.id),
        kyc_status=agent.kyc_verification_status.value,
        tenant_id=tenant_id,
        agent_name=agent.name,
    )

    return {"message": "success"}


@agent_router.post("/kyc/complete")
def mark_agent_kyc_complete(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Mark agent KYC as complete (called by KYC callback)."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.kyc_verification_status = KycVerificationStatus.VERIFIED
    db.commit()
    db.refresh(agent)

    logger.info(f"KYC completed for agent {keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent_kyc",
                "agent_keycloak_id": agent.keycloak_id,
                "kyc_verification_status": str(agent.kyc_verification_status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    ComplianceServiceAdapter().push_kyc_update(
        agent_id=str(agent.id),
        kyc_status=KycVerificationStatus.VERIFIED.value,
        tenant_id=tenant_id,
        agent_name=agent.name,
    )

    return {"message": "success", "agent": agent.to_dict()}


@agent_router.post("/kyc/fail")
def mark_agent_kyc_failed(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Mark agent KYC as failed (called by KYC callback on verification failure)."""
    agent = (
        db.query(Agent)
        .filter(Agent.keycloak_id == keycloak_id, Agent.tenant_id == tenant_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.kyc_verification_status = KycVerificationStatus.FAILED_VERIFICATION
    db.commit()
    db.refresh(agent)

    logger.info(f"KYC failed for agent {keycloak_id}")

    AuditServiceAdapter().create_audit(
        payload=AuditEventSchema(
            actor_id=keycloak_id,
            tenant_id=tenant_id,
            event_type="UPDATE",
            event_data={
                "resource": "agent_kyc",
                "agent_keycloak_id": agent.keycloak_id,
                "kyc_verification_status": str(agent.kyc_verification_status),
            },
            timestamp=datetime.utcnow().isoformat(),
        ),
        context=Context(tenant_id=tenant_id, keycloak_id=keycloak_id),
    )

    ComplianceServiceAdapter().push_kyc_update(
        agent_id=str(agent.id),
        kyc_status=KycVerificationStatus.FAILED_VERIFICATION.value,
        tenant_id=tenant_id,
        agent_name=agent.name,
    )

    return {"message": "success", "agent": agent.to_dict()}
