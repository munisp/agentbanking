from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import Integer, String, Boolean
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column


# v2.perm platform entity roles (54agent platform-level admins)
PLATFORM_ROLES = [
    "super_admin",
    "tenant_manager",
    "operations_manager",
    "risk_manager",
    "internal_auditor",
    "it_admin",
    "relationship_manager",
    "compliance_officer",
    "support_agent",
]

# v2.perm tenants entity roles (bank/tenant-level staff)
TENANT_ROLES = [
    "super_admin",
    "branch_manager",
    "operations_manager",
    "risk_manager",
    "internal_auditor",
    "it_admin",
    "relationship_manager",
    "trade_finance_admin",
    "vault_manager",
    "treasury_manager",
    "loan_officer",
    "compliance_officer",
    "support_agent",
]


class Admin(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    uin: Mapped[str] = mapped_column(String, nullable=False)

    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    keycloak_id: Mapped[str] = mapped_column(String, nullable=False)
    kyc_url: Mapped[str] = mapped_column(String, nullable=True)

    # Stores v2.perm named role — either a platform role or a tenant role
    access_level: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="support_agent",
    )

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "uin": self.uin,
            "tenant_id": self.tenant_id,
            "keycloak_id": self.keycloak_id,
            "kyc_url": self.kyc_url,
            "is_verified": self.is_verified,
            "is_suspended": self.is_suspended,
            "access_level": self.access_level,  # kept for API backward compat
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
