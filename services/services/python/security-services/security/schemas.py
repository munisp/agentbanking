from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from fastapi.security import OAuth2PasswordRequestForm

# --- Base Schemas ---

class PermissionBase(BaseModel):
    name: str = Field(..., description="Unique name for the permission (e.g., 'user:read', 'document:create')")
    description: Optional[str] = Field(None, description="A brief description of what the permission allows.")

class RoleBase(BaseModel):
    name: str = Field(..., description="Unique name for the role (e.g., 'Admin', 'Editor')")
    description: Optional[str] = Field(None, description="A brief description of the role.")
    is_default: bool = Field(False, description="If true, this role is assigned to new users by default.")

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's unique email address.")

# --- Read Schemas (Output) ---

class PermissionRead(PermissionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class RoleRead(RoleBase):
    id: int
    permissions: List[PermissionRead] = Field([], description="List of permissions associated with this role.")
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    roles: List[RoleRead] = Field([], description="List of roles assigned to the user.")
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# --- Create Schemas (Input) ---

class PermissionCreate(PermissionBase):
    pass

class RoleCreate(RoleBase):
    permission_ids: List[int] = Field([], description="List of permission IDs to assign to the role upon creation.")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User's password.")
    is_superuser: bool = Field(False, description="Set to true to grant superuser privileges.")
    role_ids: List[int] = Field([], description="List of role IDs to assign to the user upon creation.")

# --- Update Schemas (Input) ---

class PermissionUpdate(PermissionBase):
    name: Optional[str] = None
    description: Optional[str] = None

class RoleUpdate(RoleBase):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None

class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, description="New password for the user.")
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

# --- Authentication Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    scopes: List[str] = []

# Re-export OAuth2PasswordRequestForm for use in router
__all__ = [
    "PermissionBase", "RoleBase", "UserBase",
    "PermissionRead", "RoleRead", "UserRead",
    "PermissionCreate", "RoleCreate", "UserCreate",
    "PermissionUpdate", "RoleUpdate", "UserUpdate",
    "Token", "TokenData", "OAuth2PasswordRequestForm"
]
