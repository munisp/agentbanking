import uuid
import datetime

from database import Base
from sqlalchemy import String, Numeric, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


class DepositBox(Base):
    __tablename__ = "safe_deposit_boxes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    box_size: Mapped[str] = mapped_column(String, nullable=False)  # small | medium | large
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    annual_rent: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="NGN")
    renewal_date: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="available")  # occupied | available | maintenance
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "box_size": self.box_size,
            "customer_name": self.customer_name or "",
            "branch": self.branch,
            "annual_rent": float(self.annual_rent),
            "currency": self.currency,
            "renewal_date": self.renewal_date,
            "status": self.status,
        }
