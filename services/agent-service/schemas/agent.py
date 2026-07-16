from pydantic import BaseModel
from typing import Optional
from utils import AgentRole, AgentStatus


class CreateAgentSchema(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    uin: str
    business_name: Optional[str] = None
    business_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    lga: Optional[str] = None
    agent_role: Optional[AgentRole] = AgentRole.AGENT
    invited_by: Optional[str] = None  # keycloak_id of the inviting agent/admin
    inviter_type: Optional[str] = None  # "agent" | "super_agent" | "admin" | "system"


class UpdateAgentSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    business_name: Optional[str] = None
    business_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    lga: Optional[str] = None
    agent_role: Optional[AgentRole] = None
    status: Optional[AgentStatus] = None


class AgentOnboardingSchema(BaseModel):
    business_name: str
    business_address: str
    city: str
    state: str
    postal_code: str
    lga: Optional[str] = None
