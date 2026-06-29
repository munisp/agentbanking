import uuid
from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import String, Boolean, Text, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any
import datetime


class AgentBusiness(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Agent Business Model - Represents verified businesses linked to agents"""

    __tablename__ = "agent_businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Core KYB fields
    business_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    tin: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Agent linkage
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent.id"), nullable=True, index=True
    )
    agent_keycloak_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Verification fields (synced from KYB)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    verification_date: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP, nullable=True
    )
    verification_path: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Contact information
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Documents uploaded for verification (array of {title, url})
    documents: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Additional metadata
    business_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    # Relationship with agent
    agent = relationship("Agent", backref="businesses")

    # Prevent sqlalchemy_serializer circular recursion (Agent.businesses -> AgentBusiness.agent)
    serialize_rules = ("-agent.businesses", "-agent.pos_requests")

    def __repr__(self):
        return f"<AgentBusiness {self.business_name} (ID: {self.business_id}, Agent: {self.agent_keycloak_id}, Verified: {self.is_verified})>"
