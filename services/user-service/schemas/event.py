from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class UserEvent(BaseModel):
    """User domain event"""
    type: str = Field(..., description="Event type")
    user_id: str = Field(..., description="User ID")
    tenant_id: str = Field(..., description="Tenant ID")
    status: Optional[str] = Field(None, description="User status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = Field(default_factory=lambda: f"corr-{uuid.uuid4()}")
    causation_id: Optional[str] = Field(None, description="ID of the event that caused this event")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional event metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
