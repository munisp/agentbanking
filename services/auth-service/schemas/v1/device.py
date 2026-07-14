from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    device_ip: str
    user_agent: str
    user_email: str
    tenant_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeleteDeviceResponse(BaseModel):
    message: str
    device_id: str
