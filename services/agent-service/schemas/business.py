import uuid
import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class DocumentItem(BaseModel):
    """Document item for business verification"""

    title: str
    url: str


class BusinessCreate(BaseModel):
    """Schema for creating a business from KYB verification"""

    business_id: Optional[str] = None
    tenant_id: Optional[str] = None
    business_name: str
    registration_number: Optional[str] = None
    tin: Optional[str] = None
    business_type: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    documents: Optional[List[Dict[str, str]]] = None
    verification_path: Optional[str] = None
    is_verified: bool = False
    verification_status: Optional[str] = None
    verification_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BusinessLinkAgent(BaseModel):
    """Schema for linking a business to an agent"""

    agent_keycloak_id: str
    business_id: str


class BusinessResponse(BaseModel):
    """Schema for business response"""

    id: uuid.UUID
    business_id: str
    tenant_id: str
    business_name: str
    registration_number: Optional[str] = None
    tin: Optional[str] = None
    business_type: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    agent_id: Optional[uuid.UUID] = None
    agent_keycloak_id: Optional[str] = None
    is_verified: bool
    verification_status: Optional[str] = None
    verification_date: Optional[datetime.datetime] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    documents: Optional[List[Dict[str, str]]] = None
    business_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True
