from typing import List, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, root_validator

class ApiKeyBase(BaseModel):
    """Base schema for API Key attributes."""
    owner_id: str = Field(..., description="Identifier for the owner of the key (e.g., user ID, client ID).")
    name: str = Field(..., description="Human-readable name for the key.")
    scopes: List[str] = Field(default_factory=list, description="List of permissions/scopes associated with the key.")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date for the key.")
    metadata_json: Optional[str] = Field(None, description="JSON string for additional metadata.")

class ApiKeyCreate(ApiKeyBase):
    """Schema for creating a new API Key."""
    pass

class ApiKeyUpdate(BaseModel):
    """Schema for updating an existing API Key."""
    name: Optional[str] = Field(None, description="Human-readable name for the key.")
    scopes: Optional[List[str]] = Field(None, description="List of permissions/scopes associated with the key.")
    is_active: Optional[bool] = Field(None, description="Whether the key is active.")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date for the key.")
    metadata_json: Optional[str] = Field(None, description="JSON string for additional metadata.")

class ApiKeyResponse(BaseModel):
    """Schema for returning an API Key's public information."""
    id: UUID
    owner_id: str
    name: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    metadata_json: Optional[str]

    class Config:
        orm_mode = True
        json_encoders = {
            UUID: str,
        }

class ApiKeyCreatedResponse(ApiKeyResponse):
    """Special schema for the response immediately after key creation, including the secret key."""
    secret_key: str = Field(..., description="The newly generated secret API key. **This is only shown once.**")

class ApiKeyDeleteResponse(BaseModel):
    """Schema for the response after deleting an API Key."""
    id: UUID
    message: str = "API Key successfully deleted."
    
    class Config:
        json_encoders = {
            UUID: str,
        }