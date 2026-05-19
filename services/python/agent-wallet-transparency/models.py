"""Models for Agent Wallet Transparency Service."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class WalletBalance(Base):
    __tablename__ = "agent_wallet_balances"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    available_balance = Column(Numeric(18, 2), default=Decimal("0.00"))
    ledger_balance = Column(Numeric(18, 2), default=Decimal("0.00"))
    float_balance = Column(Numeric(18, 2), default=Decimal("0.00"))
    commission_balance = Column(Numeric(18, 2), default=Decimal("0.00"))
    pending_debit = Column(Numeric(18, 2), default=Decimal("0.00"))
    pending_credit = Column(Numeric(18, 2), default=Decimal("0.00"))
    currency = Column(String(3), default="NGN")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WalletLedgerEntry(Base):
    __tablename__ = "agent_wallet_ledger"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    entry_type = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)  # credit | debit
    amount = Column(Numeric(18, 2), nullable=False)
    fee_amount = Column(Numeric(18, 2), default=Decimal("0.00"))
    commission_amount = Column(Numeric(18, 2), default=Decimal("0.00"))
    net_amount = Column(Numeric(18, 2))
    running_balance = Column(Numeric(18, 2))
    description = Column(Text, nullable=False)
    reference = Column(String(100), unique=True)
    transaction_id = Column(PGUUID(as_uuid=True))
    customer_phone = Column(String(20))
    extra_metadata = Column(JSONB, default={})
    value_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_wallet_ledger_agent_date", "agent_id", "value_date"),
    )


class WalletStatement(Base):
    __tablename__ = "agent_wallet_statements"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    opening_balance = Column(Numeric(18, 2))
    closing_balance = Column(Numeric(18, 2))
    total_credits = Column(Numeric(18, 2))
    total_debits = Column(Numeric(18, 2))
    total_fees = Column(Numeric(18, 2))
    total_commissions = Column(Numeric(18, 2))
    transaction_count = Column(Numeric(10, 0))
    format = Column(String(10), default="json")
    generated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class BalanceResponse(BaseModel):
    agent_id: UUID
    available_balance: Decimal
    ledger_balance: Decimal
    float_balance: Decimal
    commission_balance: Decimal
    pending_debit: Decimal
    pending_credit: Decimal
    currency: str
    updated_at: datetime

    class Config:
        from_attributes = True


class LedgerEntryResponse(BaseModel):
    id: UUID
    entry_type: str
    direction: str
    amount: Decimal
    fee_amount: Optional[Decimal]
    commission_amount: Optional[Decimal]
    net_amount: Optional[Decimal]
    running_balance: Optional[Decimal]
    description: str
    reference: Optional[str]
    transaction_id: Optional[UUID]
    customer_phone: Optional[str]
    value_date: datetime

    class Config:
        from_attributes = True


class StatementResponse(BaseModel):
    id: UUID
    agent_id: UUID
    period_start: datetime
    period_end: datetime
    opening_balance: Optional[Decimal]
    closing_balance: Optional[Decimal]
    total_credits: Optional[Decimal]
    total_debits: Optional[Decimal]
    total_fees: Optional[Decimal]
    total_commissions: Optional[Decimal]
    transaction_count: Optional[Decimal]
    generated_at: Optional[datetime]

    class Config:
        from_attributes = True


class RecordEntryRequest(BaseModel):
    agent_id: UUID
    entry_type: str
    amount: Decimal = Field(..., gt=0)
    direction: str = Field(..., pattern="^(credit|debit)$")
    description: str
    transaction_id: Optional[UUID] = None
    reference: Optional[str] = None
    customer_phone: Optional[str] = None


class StatementRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    format: str = "json"


class EntryType:
    CASH_WITHDRAWAL = "cash_withdrawal"
    TRANSFER = "transfer"
    BILL_PAYMENT = "bill_payment"
    AIRTIME = "airtime"
    FLOAT_TOP_UP = "float_top_up"
    COMMISSION = "commission"
    REVERSAL = "reversal"
    FEE = "fee"
