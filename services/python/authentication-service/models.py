import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

# --- SQLAlchemy Base Setup ---

Base = declarative_base()

# --- Database Models ---

class User(Base):
    """
    SQLAlchemy model for a User in the authentication service.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    activity_logs = relationship("AuthActivityLog", back_populates="user")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_user_email_active", email, is_active),
    )

class AuthActivityLog(Base):
    """
    SQLAlchemy model for logging authentication-related activities.
    """
    __tablename__ = "auth_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    activity_type = Column(String, nullable=False)  # e.g., "LOGIN", "LOGOUT", "PASSWORD_CHANGE"
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    details = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="activity_logs")

    # Constraints and Indexes
    __table_args__ = (
        Index("ix_log_user_activity", user_id, activity_type),
    )

# --- Pydantic Schemas ---

# Base Schemas
class UserBase(BaseModel):
    """Base schema for User."""
    email: EmailStr = Field(..., example="user@example.com")
    first_name: Optional[str] = Field(None, example="John")
    last_name: Optional[str] = Field(None, example="Doe")

class AuthActivityLogBase(BaseModel):
    """Base schema for AuthActivityLog."""
    user_id: int
    activity_type: str = Field(..., example="LOGIN_SUCCESS")
    ip_address: Optional[str] = Field(None, example="192.168.1.1")
    user_agent: Optional[str] = None
    details: Optional[str] = None

# Create Schemas
class UserCreate(UserBase):
    """Schema for creating a new User."""
    password: str = Field(..., min_length=8)
    is_superuser: bool = False

class AuthActivityLogCreate(AuthActivityLogBase):
    """Schema for creating a new AuthActivityLog entry."""
    pass

# Update Schemas
class UserUpdate(BaseModel):
    """Schema for updating an existing User."""
    email: Optional[EmailStr] = Field(None, example="new.user@example.com")
    first_name: Optional[str] = Field(None, example="Jane")
    last_name: Optional[str] = Field(None, example="Smith")
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserPasswordUpdate(BaseModel):
    """Schema for updating a user's password."""
    old_password: str
    new_password: str = Field(..., min_length=8)

# Response Schemas
class UserResponse(UserBase):
    """Schema for responding with User data."""
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class AuthActivityLogResponse(AuthActivityLogBase):
    """Schema for responding with AuthActivityLog data."""
    id: int
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    """Schema for listing multiple users."""
    users: List[UserResponse]
    total: int

class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema for data contained in the JWT token."""
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None
