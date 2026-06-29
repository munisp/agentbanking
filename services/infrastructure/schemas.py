from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, IPvAnyAddress

# --- Base Schemas ---

class InfrastructureBase(BaseModel):
    """Base schema for common fields."""
    pass

# --- Location Schemas ---

class LocationCreate(InfrastructureBase):
    name: str = Field(..., max_length=100, description="Name of the infrastructure location (e.g., 'Data Center A', 'Cloud Region East').")
    address: Optional[str] = Field(None, max_length=255, description="Physical or virtual address of the location.")
    description: Optional[str] = Field(None, description="Detailed description of the location.")

class LocationUpdate(LocationCreate):
    pass

class Location(LocationCreate):
    id: int = Field(..., description="Unique identifier for the location.")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Status Schemas ---

class StatusCreate(InfrastructureBase):
    name: str = Field(..., max_length=50, description="Name of the component status (e.g., 'Operational', 'Maintenance', 'Degraded', 'Offline').")
    description: Optional[str] = Field(None, description="Detailed description of the status.")

class StatusUpdate(StatusCreate):
    pass

class Status(StatusCreate):
    id: int = Field(..., description="Unique identifier for the status.")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Component Schemas ---

class ComponentBase(InfrastructureBase):
    name: str = Field(..., max_length=100, description="Name of the infrastructure component.")
    type: str = Field(..., max_length=50, description="Type of the component (e.g., 'Server', 'Router', 'Database', 'Application').")
    serial_number: Optional[str] = Field(None, max_length=100, description="Unique serial number of the component.")
    ip_address: Optional[IPvAnyAddress] = Field(None, description="IP address (IPv4 or IPv6) of the component.")
    description: Optional[str] = Field(None, description="Detailed description of the component.")
    location_id: int = Field(..., description="ID of the location where the component is housed.")
    status_id: int = Field(..., description="ID of the current status of the component.")

class ComponentCreate(ComponentBase):
    pass

class ComponentUpdate(ComponentBase):
    # For updates, all fields are optional, but we inherit for structure
    name: Optional[str] = Field(None, max_length=100, description="Name of the infrastructure component.")
    type: Optional[str] = Field(None, max_length=50, description="Type of the component (e.g., 'Server', 'Router', 'Database', 'Application').")
    location_id: Optional[int] = Field(None, description="ID of the location where the component is housed.")
    status_id: Optional[int] = Field(None, description="ID of the current status of the component.")
    # All other fields are already Optional in ComponentBase

class Component(ComponentBase):
    id: int = Field(..., description="Unique identifier for the component.")
    created_at: datetime
    updated_at: datetime
    
    # Nested schemas for full response
    location: Location
    status: Status

    class Config:
        from_attributes = True

# --- List Schemas ---

class ComponentList(BaseModel):
    __root__: List[Component]

class LocationList(BaseModel):
    __root__: List[Location]

class StatusList(BaseModel):
    __root__: List[Status]