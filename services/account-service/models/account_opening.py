import uuid
import datetime

from database import Base
from sqlalchemy import String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


class AccountOpeningApplication(Base):
    __tablename__ = "account_opening_applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_ref: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    product_type: Mapped[str] = mapped_column(String, nullable=False)
    bvn: Mapped[str] = mapped_column(String, nullable=False)
    nin: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    tier: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    keycloak_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "applicationRef": self.application_ref,
            "fullName": self.full_name,
            "productType": self.product_type,
            "bvn": self.bvn,
            "nin": self.nin,
            "phoneNumber": self.phone_number,
            "email": self.email,
            "dateOfBirth": self.date_of_birth,
            "address": self.address,
            "tier": self.tier,
            "status": self.status,
            "tenantId": self.tenant_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
