from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from config import Base

# --- SQLAlchemy Models ---

class PayoutBatch(Base):
    """SQLAlchemy model for a batch of payouts."""
    __tablename__ = "payout_batches"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(
        Enum(
            "PENDING",
            "APPROVED",
            "PROCESSING",
            "COMPLETED",
            "FAILED",
            name="batch_status",
        ),
        default="PENDING",
        nullable=False,
        index=True,
    )
    total_amount = Column(Numeric(10, 2), nullable=False)
    payout_count = Column(Integer, nullable=False)
    
    # Relationships
    payouts = relationship("Payout", back_populates="batch", cascade="all, delete-orphan")
    approval = relationship("PayoutApproval", uselist=False, back_populates="batch", cascade="all, delete-orphan")
    reconciliation = relationship("ReconciliationRecord", uselist=False, back_populates="batch", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PayoutBatch(id='{self.id}', status='{self.status}', count={self.payout_count})>"


class Payout(Base):
    """SQLAlchemy model for an individual payout transaction."""
    __tablename__ = "payouts"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String, ForeignKey("payout_batches.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(
        Enum(
            "PENDING",
            "PROCESSING",
            "PAID",
            "FAILED",
            "CANCELLED",
            name="payout_status",
        ),
        default="PENDING",
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    recipient_id = Column(String, nullable=False, index=True)
    payment_method = Column(String, nullable=False)
    external_reference_id = Column(String, unique=True, nullable=True, index=True)

    # Relationships
    batch = relationship("PayoutBatch", back_populates="payouts")

    def __repr__(self):
        return f"<Payout(id='{self.id}', recipient='{self.recipient_id}', status='{self.status}')>"


class PayoutApproval(Base):
    """SQLAlchemy model for the approval record of a payout batch."""
    __tablename__ = "payout_approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String, ForeignKey("payout_batches.id"), unique=True, nullable=False, index=True)
    approved_by_id = Column(String, nullable=False)
    approved_at = Column(DateTime, default=datetime.utcnow)
    status = Column(
        Enum("PENDING", "APPROVED", "REJECTED", name="approval_status"),
        default="PENDING",
        nullable=False,
        index=True,
    )
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    batch = relationship("PayoutBatch", back_populates="approval")

    def __repr__(self):
        return f"<PayoutApproval(batch_id='{self.batch_id}', status='{self.status}')>"


class ReconciliationRecord(Base):
    """SQLAlchemy model for the reconciliation record of a payout batch."""
    __tablename__ = "reconciliation_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String, ForeignKey("payout_batches.id"), unique=True, nullable=False, index=True)
    reconciled_at = Column(DateTime, default=datetime.utcnow)
    status = Column(
        Enum("PENDING", "MATCHED", "MISMATCH", "MANUAL_REVIEW", name="reco_status"),
        default="PENDING",
        nullable=False,
        index=True,
    )
    details = Column(JSON, nullable=True)  # Store JSON details about the reconciliation process

    # Relationships
    batch = relationship("PayoutBatch", back_populates="reconciliation")

    def __repr__(self):
        return f"<ReconciliationRecord(batch_id='{self.batch_id}', status='{self.status}')>"


# --- Pydantic Schemas ---

# Base Schemas
class PayoutBase(BaseModel):
    """Base Pydantic schema for Payout."""
    amount: float = Field(..., gt=0, description="The amount of the payout.")
    currency: str = Field("USD", max_length=3, description="The currency code (e.g., USD).")
    recipient_id: str = Field(..., description="The ID of the recipient.")
    payment_method: str = Field(..., description="The payment method (e.g., bank_transfer, paypal).")
    external_reference_id: Optional[str] = Field(None, description="An optional external reference ID.")

class PayoutBatchBase(BaseModel):
    """Base Pydantic schema for PayoutBatch."""
    # Note: total_amount and payout_count are calculated, so they are not in the Create schema
    pass

class PayoutApprovalBase(BaseModel):
    """Base Pydantic schema for PayoutApproval."""
    approved_by_id: str = Field(..., description="The ID of the user who approved the batch.")

class ReconciliationRecordBase(BaseModel):
    """Base Pydantic schema for ReconciliationRecord."""
    details: Optional[dict] = Field(None, description="Details of the reconciliation process.")


# Create Schemas
class PayoutCreate(PayoutBase):
    """Pydantic schema for creating a single Payout."""
    pass

class PayoutBatchCreate(PayoutBatchBase):
    """Pydantic schema for creating a PayoutBatch with a list of Payouts."""
    payouts: List[PayoutCreate] = Field(..., description="List of individual payouts in the batch.")

class PayoutApprovalCreate(PayoutApprovalBase):
    """Pydantic schema for approving a PayoutBatch."""
    status: str = Field("APPROVED", description="The approval status (APPROVED or REJECTED).")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection, if applicable.")


# Read Schemas
class PayoutRead(PayoutBase):
    """Pydantic schema for reading a Payout."""
    id: str
    batch_id: str
    created_at: datetime
    status: str

    class Config:
        orm_mode = True

class PayoutApprovalRead(PayoutApprovalBase):
    """Pydantic schema for reading a PayoutApproval."""
    id: str
    batch_id: str
    approved_at: datetime
    status: str
    rejection_reason: Optional[str]

    class Config:
        orm_mode = True

class ReconciliationRecordRead(ReconciliationRecordBase):
    """Pydantic schema for reading a ReconciliationRecord."""
    id: str
    batch_id: str
    reconciled_at: datetime
    status: str

    class Config:
        orm_mode = True

class PayoutBatchRead(PayoutBatchBase):
    """Pydantic schema for reading a PayoutBatch, including related records."""
    id: str
    created_at: datetime
    status: str
    total_amount: float
    payout_count: int
    
    payouts: List[PayoutRead] = []
    approval: Optional[PayoutApprovalRead] = None
    reconciliation: Optional[ReconciliationRecordRead] = None

    class Config:
        orm_mode = True
