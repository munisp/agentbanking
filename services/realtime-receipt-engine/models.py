"""Models for Real-Time Receipt Engine."""
from datetime import datetime, timezone
from typing import Optional, Dict, List
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Receipt(Base):
    __tablename__ = "transaction_receipts"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    transaction_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_phone = Column(String(20), nullable=False)
    customer_name = Column(String(200))
    transaction_type = Column(String(50))
    txn_label = Column(String(100))
    amount = Column(Numeric(18, 2), nullable=False)
    fee = Column(Numeric(18, 2), default=0)
    new_balance = Column(Numeric(18, 2))
    reference = Column(String(100), unique=True, nullable=False, index=True)
    currency = Column(String(3), default="NGN")
    status = Column(String(20))
    language = Column(String(5), default="en")
    receipt_text = Column(Text)
    receipt_link = Column(String(500))
    receipt_hash = Column(String(64))
    extra_data = Column(JSONB, default={})
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReceiptDelivery(Base):
    __tablename__ = "receipt_deliveries"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    receipt_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    recipient = Column(String(200))
    status = Column(String(20), default="pending")
    error_message = Column(Text)
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReceiptTemplate(Base):
    __tablename__ = "receipt_templates"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_code = Column(String(20), index=True)
    template_name = Column(String(100))
    header_text = Column(Text)
    footer_text = Column(Text)
    logo_url = Column(String(500))
    primary_color = Column(String(10))
    is_active = Column(String(5), default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class GenerateReceiptRequest(BaseModel):
    transaction_id: UUID
    agent_id: UUID
    agent_name: str
    agent_code: str
    customer_phone: str
    customer_name: Optional[str] = None
    transaction_type: str
    amount: Decimal
    fee: Decimal = Decimal("0")
    new_balance: Optional[Decimal] = None
    reference: str
    status: str
    currency: str = "NGN"
    language: str = "en"
    channels: Optional[List[str]] = None
    extra_data: Optional[Dict] = None


class ResendRequest(BaseModel):
    reference: str
    channel: str


class ReceiptResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    agent_id: UUID
    customer_phone: str
    amount: Decimal
    reference: str
    status: str
    receipt_link: Optional[str]
    generated_at: datetime

    class Config:
        from_attributes = True


class DeliveryChannel:
    SMS = "sms"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    PUSH = "push"


class DeliveryStatus:
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
