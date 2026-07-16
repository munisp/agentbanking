from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator

# --- Base Schemas ---

class ConfigurationBase(BaseModel):
    """Base schema for Configuration, used for creation and update."""
    key: str = Field(..., min_length=1, max_length=100, description="Unique key for the configuration setting.")
    value: str = Field(..., description="The value of the configuration setting (stored as string/text).")
    type: str = Field("string", description="The expected data type of the value (e.g., 'string', 'integer', 'boolean', 'json').")
    is_active: bool = Field(True, description="Whether the configuration setting is currently active.")
    description: Optional[str] = Field(None, max_length=500, description="A brief description of the setting.")

    @validator('key')
    def key_must_be_alphanumeric_or_underscores(cls, v) -> None:
        if not v.replace('_', '').isalnum():
            raise ValueError('Key must be alphanumeric with optional underscores.')
        return v

    class Config:
        from_attributes = True

# --- History Schemas ---

class ConfigurationHistoryRead(BaseModel):
    """Schema for reading ConfigurationHistory records."""
    id: int
    config_id: int
    old_value: Optional[str]
    new_value: str
    changed_by: str
    changed_at: datetime

    class Config:
        from_attributes = True

# --- Configuration Schemas ---

class ConfigurationCreate(ConfigurationBase):
    """Schema for creating a new Configuration."""
    pass

class ConfigurationUpdate(ConfigurationBase):
    """Schema for updating an existing Configuration. All fields are optional for partial update."""
    key: Optional[str] = Field(None, min_length=1, max_length=100, description="Unique key for the configuration setting.")
    value: Optional[str] = Field(None, description="The value of the configuration setting (stored as string/text).")
    type: Optional[str] = Field(None, description="The expected data type of the value.")
    is_active: Optional[bool] = Field(None, description="Whether the configuration setting is currently active.")
    description: Optional[str] = Field(None, max_length=500, description="A brief description of the setting.")

class ConfigurationRead(ConfigurationBase):
    """Schema for reading a Configuration record."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    # Optional field to include history when requested
    history: List[ConfigurationHistoryRead] = []