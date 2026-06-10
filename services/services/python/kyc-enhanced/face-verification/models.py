import uuid
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Integer,
    Float,
    Enum,
    JSON,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declared_attr

# --- Base and Mixins ---

Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        comment="Timestamp of creation"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Timestamp of last update"
    )

class AuditMixin:
    """Mixin for created_by and updated_by audit fields."""
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of the user/system that created the record"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of the user/system that last updated the record"
    )

class SoftDeleteMixin:
    """Mixin for soft deletion support."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of deletion (soft delete)"
    )

class BaseTable(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """Base class for all tables, providing common fields and conventions."""
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        """Generates table name from class name in snake_case and plural form."""
        import re
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        # Simple pluralization for common cases, adjust if needed
        if name.endswith('y'):
            return name[:-1] + 'ies'
        elif name.endswith('s'):
            return name
        else:
            return name + 's'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="Primary key, UUID"
    )

# --- Enums ---

import enum

class VerificationStatus(enum.Enum):
    """Status of a face verification attempt."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"

class LivenessResult(enum.Enum):
    """Result of the liveness detection check."""
    NOT_PERFORMED = "not_performed"
    PASS = "pass"
    FAIL = "fail"
    SUSPICIOUS = "suspicious"

class VerificationType(enum.Enum):
    """Type of verification being performed."""
    ONE_TO_ONE = "1:1"  # Verification (e.g., ID photo vs selfie)
    ONE_TO_MANY = "1:N" # Identification (e.g., selfie vs database)
    LIVENESS_ONLY = "liveness_only"

# --- Models ---

class BiometricData(BaseTable):
    """
    Stores the raw biometric data (e.g., face template/vector) for a user.
    This data is sensitive and should be encrypted at rest.
    """
    __tablename__ = 'biometric_data'
    __table_args__ = (
        Index('ix_biometric_data_user_id', 'user_id', unique=True),
        {'comment': 'Stores face templates and related biometric data'}
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Foreign key to the user/entity this data belongs to"
    )
    template_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Version of the biometric template algorithm used"
    )
    face_template: Mapped[bytes] = mapped_column(
        # Use bytea for storing the binary face template/vector
        # In a real system, this would be a large binary field or a reference to a secure storage
        Column('face_template', JSONB), # Using JSONB to simulate a vector/template for simplicity in ORM, but should be bytea or a dedicated vector type in production
        nullable=False,
        comment="The actual face template/vector (should be encrypted)"
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata about the data capture (e.g., source image quality)"
    )

    # Relationships (assuming a 'users' table exists elsewhere)
    # user: Mapped["User"] = relationship("User", back_populates="biometric_data")


class VerificationAttempt(BaseTable):
    """
    Records every attempt at face verification.
    """
    __tablename__ = 'verification_attempts'
    __table_args__ = (
        Index('ix_verification_attempts_user_id', 'user_id'),
        Index('ix_verification_attempts_status', 'status'),
        {'comment': 'Records every face verification attempt'}
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Foreign key to the user/entity being verified"
    )
    verification_type: Mapped[VerificationType] = mapped_column(
        Enum(VerificationType, name="verification_type_enum", create_type=True),
        nullable=False,
        comment="Type of verification performed (1:1, 1:N, Liveness Only)"
    )
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status_enum", create_type=True),
        nullable=False,
        default=VerificationStatus.PENDING,
        comment="Overall status of the verification attempt"
    )
    source_image_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Secure URL or path to the source image used for verification"
    )
    target_data_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('biometric_data.id', ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key to the BiometricData record used as the target (for 1:1 verification)"
    )
    target_data: Mapped[Optional["BiometricData"]] = relationship(
        "BiometricData",
        backref="verification_attempts",
        foreign_keys=[target_data_id]
    )
    client_ip: Mapped[Optional[str]] = mapped_column(
        String(45), # Supports IPv4 and IPv6
        nullable=True,
        comment="IP address of the client making the request"
    )
    device_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON object containing device and browser information"
    )
    verification_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed JSON response from the face verification engine"
    )


class MatchScore(BaseTable):
    """
    Stores the match score and related metrics for a verification attempt.
    This is typically a sub-record of a successful 1:1 or 1:N attempt.
    """
    __tablename__ = 'match_scores'
    __table_args__ = (
        Index('ix_match_scores_attempt_id', 'attempt_id', unique=True),
        Index('ix_match_scores_score', 'score'),
        {'comment': 'Stores the face match score and confidence metrics'}
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('verification_attempts.id', ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to the VerificationAttempt this score belongs to"
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="The similarity score between the source and target faces (e.g., 0.0 to 1.0)"
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence level of the score, if provided by the engine"
    )
    threshold_used: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="The minimum score threshold applied for a 'SUCCESS' result"
    )
    is_match: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Boolean flag indicating if the score met the threshold"
    )
    match_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed metrics from the matching algorithm (e.g., feature distances)"
    )

    # Relationships
    attempt: Mapped["VerificationAttempt"] = relationship(
        "VerificationAttempt",
        backref="match_score",
        foreign_keys=[attempt_id]
    )


class LivenessDetection(BaseTable):
    """
    Stores the results of the liveness detection check for a verification attempt.
    """
    __tablename__ = 'liveness_detections'
    __table_args__ = (
        Index('ix_liveness_detections_attempt_id', 'attempt_id', unique=True),
        Index('ix_liveness_detections_result', 'result'),
        {'comment': 'Stores the results of the liveness detection check'}
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('verification_attempts.id', ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to the VerificationAttempt this liveness check belongs to"
    )
    result: Mapped[LivenessResult] = mapped_column(
        Enum(LivenessResult, name="liveness_result_enum", create_type=True),
        nullable=False,
        default=LivenessResult.NOT_PERFORMED,
        comment="The final result of the liveness check"
    )
    score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Liveness score/probability (e.g., 0.0 to 1.0)"
    )
    threshold_used: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="The minimum score threshold applied for a 'PASS' result"
    )
    is_live: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Boolean flag indicating if the check passed the threshold"
    )
    detection_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed metrics from the liveness detection algorithm (e.g., frame analysis)"
    )

    # Relationships
    attempt: Mapped["VerificationAttempt"] = relationship(
        "VerificationAttempt",
        backref="liveness_detection",
        foreign_keys=[attempt_id]
    )

# Example of how to create the tables (for reference, not part of the schema file)
# from sqlalchemy import create_engine
# engine = create_engine("postgresql+psycopg2://user:pass@host/dbname")
# Base.metadata.create_all(engine)
