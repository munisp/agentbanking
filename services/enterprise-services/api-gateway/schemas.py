from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, Any
from datetime import datetime

# --- Custom JSON Type for SQLAlchemy/Pydantic Compatibility ---
class JSONType(BaseModel):
    __root__: dict[str, Any] = Field(default_factory=dict)

    @validator('__root__', pre=True)
    def validate_json(cls, v):
        if v is None:
            return {}
        return v

# --- Base Schema for Route ---
class RouteBase(BaseModel):
    service_name: str = Field(..., min_length=3, max_length=100, description="Unique name of the service (e.g., 'user-service').")
    source_path_prefix: str = Field(..., regex=r"^\/[a-zA-Z0-9\-\/]+$", description="The path prefix to match (e.g., '/users'). Must start with '/'.")
    target_url: HttpUrl = Field(..., description="The base URL of the target service (e.g., 'http://localhost:8080').")
    is_active: bool = Field(True, description="Whether the route is currently active.")
    auth_required: bool = Field(False, description="Whether authentication is required for this route.")
    rate_limit_per_minute: int = Field(0, ge=0, description="Rate limit in requests per minute (0 for no limit).")
    config: dict[str, Any] = Field(default_factory=dict, description="Advanced configuration settings (e.g., headers, timeouts).")

    class Config:
        from_attributes = True

# --- Schema for Route Creation ---
class RouteCreate(RouteBase):
    pass

# --- Schema for Route Update ---
class RouteUpdate(BaseModel):
    service_name: Optional[str] = Field(None, min_length=3, max_length=100, description="Unique name of the service (e.g., 'user-service').")
    source_path_prefix: Optional[str] = Field(None, regex=r"^\/[a-zA-Z0-9\-\/]+$", description="The path prefix to match (e.g., '/users'). Must start with '/'.")
    target_url: Optional[HttpUrl] = Field(None, description="The base URL of the target service (e.g., 'http://localhost:8080').")
    is_active: Optional[bool] = Field(None, description="Whether the route is currently active.")
    auth_required: Optional[bool] = Field(None, description="Whether authentication is required for this route.")
    rate_limit_per_minute: Optional[int] = Field(None, ge=0, description="Rate limit in requests per minute (0 for no limit).")
    config: Optional[dict[str, Any]] = Field(None, description="Advanced configuration settings (e.g., headers, timeouts).")

    class Config:
        from_attributes = True

# --- Schema for Route Response (In DB) ---
class RouteInDB(RouteBase):
    id: int = Field(..., description="The unique ID of the route configuration.")
    created_at: datetime = Field(..., description="Timestamp of when the route was created.")
    updated_at: datetime = Field(..., description="Timestamp of the last update.")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }