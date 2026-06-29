import uuid
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models.pos_request import POSRequestStatus


class POSRequestCreate(BaseModel):
    """Schema for creating a POS request (agent action)"""

    business_id: Optional[str] = None
    preferred_model: Optional[str] = None
    quantity: int = Field(default=1, ge=1, le=10)
    deployment_location: Optional[str] = None
    deployment_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    justification: Optional[str] = Field(None, max_length=1000)


class POSRequestUpdate(BaseModel):
    """Schema for updating a POS request (agent can update pending requests)"""

    preferred_model: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1, le=10)
    deployment_location: Optional[str] = None
    deployment_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    justification: Optional[str] = Field(None, max_length=1000)


class POSRequestReview(BaseModel):
    """Schema for admin to review (approve/reject) a POS request"""

    action: str = Field(..., pattern="^(approve|reject)$")
    admin_notes: Optional[str] = Field(None, max_length=1000)
    rejection_reason: Optional[str] = Field(None, max_length=500)


class POSRequestAssign(BaseModel):
    """Schema for admin to assign a terminal to an approved request"""

    terminal_id: str
    terminal_serial: str
    admin_notes: Optional[str] = Field(None, max_length=1000)
    # Geo-fence fields
    geofence_latitude: Optional[float] = None
    geofence_longitude: Optional[float] = None
    geofence_radius_m: Optional[float] = None  # meters


class POSRequestResponse(BaseModel):
    """Schema for POS request response"""

    id: uuid.UUID
    agent_id: uuid.UUID
    agent_keycloak_id: str
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    preferred_model: Optional[str] = None
    quantity: int
    deployment_location: Optional[str] = None
    deployment_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    justification: Optional[str] = None
    status: POSRequestStatus
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    assigned_terminal_id: Optional[str] = None
    assigned_terminal_serial: Optional[str] = None
    assigned_at: Optional[datetime] = None
    tenant_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Geo-fence (optional)
    geofence_latitude: Optional[float] = None
    geofence_longitude: Optional[float] = None
    geofence_radius_m: Optional[float] = None

    class Config:
        from_attributes = True
        use_enum_values = True
