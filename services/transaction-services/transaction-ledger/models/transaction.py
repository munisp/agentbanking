import uuid
import datetime
from database import Base
from utils import TransactionStatus, CurrencyEnum
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import String, Enum, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column

class Transaction(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Transaction Model Definition"""

    __tablename__ = "transaction"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    payer: Mapped[str] = mapped_column(String, nullable=False)
    payer_account_number: Mapped[str] = mapped_column(String, nullable=True)
    payer_name: Mapped[str] = mapped_column(String, nullable=True)
    payee: Mapped[str] = mapped_column(String, nullable=False)
    payee_account_number: Mapped[str] = mapped_column(String, nullable=True)
    payee_name: Mapped[str] = mapped_column(String, nullable=True)
    amount: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)
    currency: Mapped[CurrencyEnum] = mapped_column(Enum(CurrencyEnum), nullable=False, default=CurrencyEnum.NGN)
    completed_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=True)
    note: Mapped[str] = mapped_column(String, nullable=True)
    tag: Mapped[str] = mapped_column(String, nullable=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    ledger_id: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self):
        return f"<Transaction(id={self.id}), payer={self.payer}, payee={self.payee}, amount={self.amount})>"