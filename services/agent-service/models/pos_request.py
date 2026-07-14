import uuid
from datetime import datetime

from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import String, Enum, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column
import enum


class POSRequestStatus(enum.Enum):
    """POS Request Status"""

    PENDING = "pending"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class POSRequest(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """POS Request Model - Agents request POS terminals"""

    __tablename__ = "pos_request"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Agent Information
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_keycloak_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=True)
    agent_email: Mapped[str] = mapped_column(String, nullable=True)
    agent_phone: Mapped[str] = mapped_column(String, nullable=True)

    # Business Information (if linked)
    business_id: Mapped[str] = mapped_column(String, nullable=True)
    business_name: Mapped[str] = mapped_column(String, nullable=True)

    # Request Details
    preferred_model: Mapped[str] = mapped_column(String, nullable=True)
    quantity: Mapped[int] = mapped_column(default=1)
    deployment_location: Mapped[str] = mapped_column(String, nullable=True)
    deployment_address: Mapped[str] = mapped_column(Text, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=True)

    # Status and Processing
    status: Mapped[POSRequestStatus] = mapped_column(
        Enum(POSRequestStatus), nullable=False, default=POSRequestStatus.PENDING
    )

    # Admin Actions
    reviewed_by: Mapped[str] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    admin_notes: Mapped[str] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)

    # Assigned POS Terminal Info
    assigned_terminal_id: Mapped[str] = mapped_column(String, nullable=True)
    assigned_terminal_serial: Mapped[str] = mapped_column(String, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Geo-fence (optional)
    geofence_latitude: Mapped[float] = mapped_column(String, nullable=True)
    geofence_longitude: Mapped[float] = mapped_column(String, nullable=True)
    geofence_radius_m: Mapped[float] = mapped_column(String, nullable=True)

    # Tenant
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    def __repr__(self):
        return (
            f"<POSRequest(id={self.id}, agent={self.agent_name}, "
            f"status={self.status.value}, tenant={self.tenant_id})>"
        )
