import uuid
from database import Base
from utils import UserRole, UserStatus, KycVerificationStatus
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import String, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column

class User(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """User Model Definition"""

    __tablename__ = "user"

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
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    user_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    kyc_verification_status: Mapped[KycVerificationStatus] = mapped_column(Enum(KycVerificationStatus), nullable=True, default=KycVerificationStatus.NOT_VERIFIED)
    kyc_verification_url: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self):
        return f"<User(email={self.email}), keycloak_id={self.keycloak_id}, tenant_id={self.tenant_id})>"
