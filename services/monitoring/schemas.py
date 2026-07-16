from pydantic import BaseModel, Field, conint, constr
from typing import Optional, List
from datetime import datetime

# --- Base Schemas ---

class ServiceBase(BaseModel):
    name: constr(min_length=1, max_length=100) = Field(..., example="UserAuthService")
    description: Optional[str] = Field(None, example="Handles user authentication and authorization.")
    status: Optional[str] = Field("Operational", example="Operational", description="Overall status: Operational, Degraded, Offline")

class EndpointBase(BaseModel):
    url: constr(min_length=1, max_length=255) = Field(..., example="/health")
    method: constr(min_length=1, max_length=10) = Field("GET", example="GET")
    check_interval_seconds: conint(ge=10) = Field(60, example=60, description="Minimum check interval is 10 seconds.")
    expected_status_code: conint(ge=100, le=599) = Field(200, example=200)
    is_active: Optional[bool] = Field(True, example=True)

class MonitorRecordBase(BaseModel):
    status_code: conint(ge=100, le=599) = Field(..., example=200)
    response_time_ms: float = Field(..., example=150.5)
    is_success: bool = Field(..., example=True)
    error_message: Optional[str] = Field(None, example=None)

# --- Create Schemas ---

class ServiceCreate(ServiceBase):
    pass

class EndpointCreate(EndpointBase):
    service_id: int = Field(..., example=1)

class MonitorRecordCreate(MonitorRecordBase):
    endpoint_id: int = Field(..., example=1)

# --- Update Schemas ---

class ServiceUpdate(ServiceBase):
    name: Optional[constr(min_length=1, max_length=100)] = None
    description: Optional[str] = None
    status: Optional[str] = None

class EndpointUpdate(EndpointBase):
    url: Optional[constr(min_length=1, max_length=255)] = None
    method: Optional[constr(min_length=1, max_length=10)] = None
    check_interval_seconds: Optional[conint(ge=10)] = None
    expected_status_code: Optional[conint(ge=100, le=599)] = None
    is_active: Optional[bool] = None

# --- Read Schemas (Response Models) ---

class MonitorRecord(MonitorRecordBase):
    id: int
    endpoint_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class Endpoint(EndpointBase):
    id: int
    service_id: int
    created_at: datetime
    updated_at: datetime
    
    # Relationship fields (optional for read)
    records: List[MonitorRecord] = []

    class Config:
        from_attributes = True

class Service(ServiceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    # Relationship fields (optional for read)
    endpoints: List[Endpoint] = []

    class Config:
        from_attributes = True

# --- Utility Schemas ---

class HealthCheck(BaseModel):
    status: str = "ok"
    database_connection: str = "ok"
    service_name: str = "monitoring"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Message(BaseModel):
    detail: str