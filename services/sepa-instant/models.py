import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column

# --- Base Class ---
class Base(DeclarativeBase):
    """Base class which provides automated table name
    and primary key column.
    """
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- Enums ---
class TransactionStatus(PyEnum):
    INITIATED = "INITIATED"
    VALIDATED = "VALIDATED"
    PENDING_CSM = "PENDING_CSM"
    REJECTED = "REJECTED"
    DEBITED = "DEBITED"
    CREDITED = "CREDITED"
    FAILED = "FAILED"
    RECALLED = "RECALLED"

class RecallReason(PyEnum):
    DUPLICATE = "DUPLICATE"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"
    FRAUDULENT = "FRAUDULENT"
    OTHER = "OTHER"

class RecallStatus(PyEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"

# --- Models ---
class SCTInstTransaction(Base):
    __tablename__ = "sct_inst_transactions"

    # Core Transaction Fields
    end_to_end_id: Mapped[str] = mapped_column(String(35), index=True, unique=True)
    instruction_id: Mapped[str] = mapped_column(String(35), index=True)
    transaction_status: Mapped[TransactionStatus] = mapped_column(
        ENUM(TransactionStatus, name="transaction_status_enum", create_type=False),
        default=TransactionStatus.INITIATED
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    requested_execution_date: Mapped[datetime] = mapped_column(DateTime)
    execution_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Rejection Information
    rejection_reason_code: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    rejection_reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Remittance Information
    remittance_information: Mapped[Optional[str]] = mapped_column(String(140), nullable=True)

    # Originator (Payer) Information
    originator_name: Mapped[str] = mapped_column(String(100))
    originator_iban: Mapped[str] = mapped_column(String(34), index=True)
    originator_bic: Mapped[str] = mapped_column(String(11))

    # Beneficiary (Payee) Information
    beneficiary_name: Mapped[str] = mapped_column(String(100))
    beneficiary_iban: Mapped[str] = mapped_column(String(34), index=True)
    beneficiary_bic: Mapped[str] = mapped_column(String(11))

    # Relationships
    recalls: Mapped[List["TransactionRecall"]] = relationship(
        "TransactionRecall", back_populates="transaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sct_inst_originator_iban", "originator_iban"),
        Index("idx_sct_inst_beneficiary_iban", "beneficiary_iban"),
        # Constraint to ensure amount is positive
        # CheckConstraint(amount > 0, name="ck_sct_inst_amount_positive"), # Not supported by all SQL dialects
    )

    def __repr__(self) -> str:
        return f"SCTInstTransaction(id={self.id}, end_to_end_id='{self.end_to_end_id}', status='{self.transaction_status.value}')"


class TransactionRecall(Base):
    __tablename__ = "transaction_recalls"

    # Foreign Key to Transaction
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sct_inst_transactions.id"))

    # Recall Details
    recall_request_date: Mapped[datetime] = mapped_column(DateTime)
    recall_reason: Mapped[RecallReason] = mapped_column(
        ENUM(RecallReason, name="recall_reason_enum", create_type=False)
    )
    recall_status: Mapped[RecallStatus] = mapped_column(
        ENUM(RecallStatus, name="recall_status_enum", create_type=False),
        default=RecallStatus.PENDING
    )
    
    # Response Details
    response_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    return_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    return_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Relationships
    transaction: Mapped["SCTInstTransaction"] = relationship("SCTInstTransaction", back_populates="recalls")

    __table_args__ = (
        Index("idx_recall_transaction_id", "transaction_id"),
    )

    def __repr__(self) -> str:
        return f"TransactionRecall(id={self.id}, transaction_id={self.transaction_id}, status='{self.recall_status.value}')"