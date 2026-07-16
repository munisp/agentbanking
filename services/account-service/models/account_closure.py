import uuid
import datetime

from database import Base
from sqlalchemy import String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


class AccountClosureRequest(Base):
    __tablename__ = "account_closure_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    account_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    closure_type: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String, nullable=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    keycloak_id: Mapped[str] = mapped_column(String, nullable=False)
    requested_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow
    )
    closed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "accountId": self.account_id,
            "accountName": self.account_name,
            "accountType": self.account_type,
            "status": self.status,
            "closureType": self.closure_type,
            "reason": self.reason,
            "requestedBy": self.requested_by,
            "tenantId": self.tenant_id,
            "requestedAt": self.requested_at.isoformat() if self.requested_at else None,
            "closedAt": self.closed_at.isoformat() if self.closed_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
