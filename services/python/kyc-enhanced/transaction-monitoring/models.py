import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Boolean,
    JSON,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

# --- Base Setup ---
Base = declarative_base()

class PasswordStrength(enum.Enum):
    """Enum for password strength levels."""
    VERY_WEAK = "VERY_WEAK"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"

class BreachStatus(enum.Enum):
    """Enum for the status of a password breach check."""
    PENDING = "PENDING"
    CLEAN = "CLEAN"
    BREACHED = "BREACHED"
    ERROR = "ERROR"

class ResetTokenStatus(enum.Enum):
    """Enum for the status of a password reset token."""
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class BaseModel(Base):
    """
    Abstract base class providing common fields for all models.

    Includes:
    - UUID primary key
    - Timestamps (created_at, updated_at)
    - Soft delete support (deleted_at)
    - Audit fields (created_by, updated_by)
    """
    __abstract__ = True

    id: uuid.UUID = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    created_at: datetime = Column(
        DateTime(timezone=True), default=func.now(), index=True, nullable=False
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Optional[datetime] = Column(DateTime(timezone=True), index=True)

    # Audit fields - Assuming a 'users' table exists for foreign key constraint
    created_by: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="ID of the user who created the record.",
    )
    updated_by: Optional[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="ID of the user who last updated the record.",
    )

    # Relationships for audit fields (assuming a User model exists)
    # creator = relationship("User", foreign_keys=[created_by], backref="created_records")
    # updater = relationship("User", foreign_keys=[updated_by], backref="updated_records")


class PasswordHistory(BaseModel):
    """
    Stores a history of a user's previous passwords to prevent reuse.
    """
    __tablename__ = "password_history"
    __table_args__ = (
        UniqueConstraint("user_id", "password_hash", name="uq_password_history_user_hash"),
        {"comment": "Stores previous password hashes for a user to enforce reuse policies."},
    )

    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The ID of the user whose password history is being recorded.",
    )
    password_hash: str = Column(
        String(255),
        nullable=False,
        doc="The hashed version of the previous password.",
    )
    # The date the password was set (and thus recorded in history)
    set_at: datetime = Column(
        DateTime(timezone=True), default=func.now(), nullable=False, index=True
    )

    # Relationship to the User model (assuming a User model exists)
    # user = relationship("User", back_populates="password_history")


class PasswordStrengthScore(BaseModel):
    """
    Stores the calculated strength score and details for a user's current password.
    """
    __tablename__ = "password_strength_scores"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_password_strength_user_id"),
        {"comment": "Stores the strength score and metadata for a user's current password."},
    )

    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The ID of the user whose password strength is being scored.",
    )
    score: int = Column(
        Integer,
        nullable=False,
        doc="A numerical score representing password strength (e.g., 0-100).",
    )
    strength_level: PasswordStrength = Column(
        Enum(PasswordStrength, name="password_strength_enum", create_type=True),
        nullable=False,
        index=True,
        doc="Categorical strength level (e.g., WEAK, STRONG).",
    )
    feedback: Optional[dict] = Column(
        JSONB,
        doc="JSON field for detailed feedback or suggestions from the strength checker.",
    )
    last_checked_at: datetime = Column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # Relationship to the User model (assuming a User model exists)
    # user = relationship("User", back_populates="password_strength_score")


class PasswordBreachCheck(BaseModel):
    """
    Records the results of checks against known password breaches (e.g., Pwned Passwords).
    """
    __tablename__ = "password_breach_checks"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_password_breach_user_id"),
        {"comment": "Records the results of checks against known password breaches."},
    )

    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The ID of the user whose password was checked.",
    )
    status: BreachStatus = Column(
        Enum(BreachStatus, name="breach_status_enum", create_type=True),
        nullable=False,
        default=BreachStatus.PENDING,
        index=True,
        doc="The status of the breach check (CLEAN, BREACHED, etc.).",
    )
    breach_count: int = Column(
        Integer,
        nullable=False,
        default=0,
        doc="The number of times the password was found in known breaches.",
    )
    details: Optional[dict] = Column(
        JSONB,
        doc="JSON field for detailed breach information (e.g., list of breach names).",
    )
    last_checked_at: datetime = Column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    is_notified: bool = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flag to track if the user has been notified about a breach.",
    )

    # Relationship to the User model (assuming a User model exists)
    # user = relationship("User", back_populates="password_breach_check")


class PasswordResetToken(BaseModel):
    """
    Manages password reset tokens, including their status and expiration.
    """
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_password_reset_token"),
        CheckConstraint("expires_at > created_at", name="cc_reset_token_expiration"),
        {"comment": "Manages one-time password reset tokens."},
    )

    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The ID of the user requesting the password reset.",
    )
    token: str = Column(
        String(64),
        nullable=False,
        index=True,
        doc="The unique, cryptographically secure token sent to the user.",
    )
    expires_at: datetime = Column(
        DateTime(timezone=True), nullable=False, index=True,
        doc="The time when the token becomes invalid.",
    )
    status: ResetTokenStatus = Column(
        Enum(ResetTokenStatus, name="reset_token_status_enum", create_type=True),
        nullable=False,
        default=ResetTokenStatus.ACTIVE,
        index=True,
        doc="The current status of the token (ACTIVE, USED, EXPIRED, REVOKED).",
    )
    used_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        doc="The time the token was successfully used.",
    )
    ip_address: Optional[str] = Column(
        String(45),
        doc="The IP address from which the reset request was initiated.",
    )

    # Relationship to the User model (assuming a User model exists)
    # user = relationship("User", back_populates="password_reset_tokens")

# --- Example of how to import and use the models ---
# if __name__ == "__main__":
#     from sqlalchemy import create_engine
#     from sqlalchemy.orm import sessionmaker
#
#     # Example usage (replace with your actual connection string)
#     # engine = create_engine("postgresql+psycopg2://user:pass@host/dbname")
#     # Base.metadata.create_all(engine)
#     print("Schema file generated successfully.")
