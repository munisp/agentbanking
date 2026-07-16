from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column


class TrustedDevice(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Trusted Device Model Definition"""

    __tablename__ = "trusted_devices"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "keycloak_id", "tenant_id", name="uix_device_user_tenant"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    device_ip: Mapped[str] = mapped_column(String, nullable=False)
    user_agent: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    user_email: Mapped[str] = mapped_column(String, nullable=False)
    keycloak_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    def __repr__(self):
        return f"<Device ID: {self.device_id}, User Email: {self.user_email}, Tenant ID: {self.tenant_id}>"
