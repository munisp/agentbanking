import uuid

from database import Base
from utils import AgentRole, AgentStatus, AgentOnboardingStatus, KycVerificationStatus
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import String, Enum, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column


class Agent(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Agent Model Definition"""

    __tablename__ = "agent"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    uin: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    keycloak_id: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Agent-specific fields
    agent_role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole), nullable=False, default=AgentRole.AGENT
    )
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus), nullable=False, default=AgentStatus.PENDING_APPROVAL
    )
    onboarding_status: Mapped[AgentOnboardingStatus] = mapped_column(
        Enum(AgentOnboardingStatus),
        nullable=False,
        default=AgentOnboardingStatus.NOT_STARTED,
    )
    kyc_verification_status: Mapped[KycVerificationStatus] = mapped_column(
        Enum(KycVerificationStatus),
        nullable=True,
        default=KycVerificationStatus.NOT_VERIFIED,
    )
    kyc_verification_url: Mapped[str] = mapped_column(String, nullable=True)

    # Business / location info
    business_name: Mapped[str] = mapped_column(String, nullable=True)
    business_address: Mapped[str] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=True)
    postal_code: Mapped[str] = mapped_column(String, nullable=True)
    lga: Mapped[str] = mapped_column(String, nullable=True)

    # Approval
    approved_by: Mapped[str] = mapped_column(String, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Invitation tracking
    invited_by: Mapped[str] = mapped_column(
        String, nullable=True
    )  # keycloak_id of the inviter
    inviter_type: Mapped[str] = mapped_column(
        String, nullable=True
    )  # "agent" | "super_agent" | "admin" | "system"

    # Prevent sqlalchemy_serializer circular recursion via businesses backref
    serialize_rules = ("-businesses.agent",)

    def __repr__(self):
        return (
            f"<Agent(email={self.email}), keycloak_id={self.keycloak_id}, "
            f"tenant_id={self.tenant_id})>"
        )
