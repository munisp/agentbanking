from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

# Association table for the many-to-many relationship between Role and Permission
role_permission_association = Table(
    "role_permission_association",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True, index=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True, index=True),
)

# Association table for the many-to-many relationship between User and Role
user_role_association = Table(
    "user_role_association",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, index=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True, index=True),
)

class User(Base):
    """
    Represents a user in the system.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    roles = relationship(
        "Role",
        secondary=user_role_association,
        back_populates="users",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"

class Role(Base):
    """
    Represents a role that can be assigned to users (e.g., Admin, Editor, Viewer).
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship(
        "User",
        secondary=user_role_association,
        back_populates="roles",
        lazy="selectin"
    )
    permissions = relationship(
        "Permission",
        secondary=role_permission_association,
        back_populates="roles",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"

class Permission(Base):
    """
    Represents a specific action or resource access (e.g., 'user:read', 'document:create').
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False) # e.g., 'user:read', 'document:create'
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    roles = relationship(
        "Role",
        secondary=role_permission_association,
        back_populates="permissions",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}')>"
