from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator

# --- Base Schemas ---

class IntegrationBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Unique name for the integration.")
    type: str = Field(..., min_length=2, max_length=50, description="Type of the integration (e.g., PAYMENT, CRM).")
    description: Optional[str] = Field(None, max_length=500, description="A brief description of the integration.")
    is_active: bool = Field(True, description="Whether the integration is currently active.")

    class Config:
        from_attributes = True

class IntegrationLogBase(BaseModel):
    endpoint: str = Field(..., description="The API endpoint called.")
    method: str = Field(..., description="The HTTP method used (e.g., GET, POST).")
    status_code: str = Field(..., description="The HTTP status code of the response.")
    request_body: Optional[Any] = Field(None, description="The request payload sent.")
    response_body: Optional[Any] = Field(None, description="The response payload received.")
    is_success: bool = Field(..., description="Whether the call was considered successful.")
    error_message: Optional[str] = Field(None, description="Any error message if the call failed.")

    class Config:
        from_attributes = True

# --- Create/Update Schemas ---

class IntegrationCreate(IntegrationBase):
    # api_key_encrypted is required for creation but should be handled securely
    # For this schema, we'll use a plain text key which the service layer will "encrypt"
    api_key: str = Field(..., min_length=10, description="The API key for the third-party service.")
    config_json: Optional[dict[str, Any]] = Field(None, description="Flexible configuration data for the integration.")

class IntegrationUpdate(IntegrationBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100, description="Unique name for the integration.")
    type: Optional[str] = Field(None, min_length=2, max_length=50, description="Type of the integration (e.g., PAYMENT, CRM).")
    api_key: Optional[str] = Field(None, min_length=10, description="New API key for the third-party service.")
    config_json: Optional[dict[str, Any]] = Field(None, description="Flexible configuration data for the integration.")

    @validator('name', 'type', pre=True)
    def check_at_least_one_field(cls, v, values, **kwargs) -> None:
        # Check if any field is provided for update
        # This is a simple check, a more robust one would inspect the model_dump(exclude_unset=True)
        # in the router/service layer, but this provides basic Pydantic validation.
        if not any(values.values()):
            raise ValueError("At least one field must be provided for update.")
        return v

class IntegrationLogCreate(IntegrationLogBase):
    integration_id: UUID = Field(..., description="The ID of the integration this log belongs to.")

# --- Read Schemas (Response) ---

class Integration(IntegrationBase):
    id: UUID
    # api_key_encrypted is NOT returned for security reasons
    config_json: Optional[dict[str, Any]] = None # Configuration is returned, but not the key
    created_at: datetime
    updated_at: datetime

class IntegrationLog(IntegrationLogBase):
    id: UUID
    integration_id: UUID
    logged_at: datetime

# --- Utility Schemas ---

class Message(BaseModel):
    message: str
