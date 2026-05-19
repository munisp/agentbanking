"""Models for NFC/QR Self-Service Payments."""
from datetime import datetime, timezone
from typing import Optional, Dict
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class QRCode(Base):
    __tablename__ = "agent_qr_codes"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    qr_type = Column(String(20), nullable=False)  # static | dynamic
    amount = Column(Numeric(18, 2))
    transaction_type = Column(String(50))
    reference = Column(String(100), unique=True)
    payload = Column(JSONB)
    qr_data = Column(Text)
    qr_image_base64 = Column(Text)
    status = Column(String(20), default="active", index=True)
    customer_phone = Column(String(20))
    expires_at = Column(DateTime(timezone=True))
    used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NFCToken(Base):
    __tablename__ = "nfc_tokens"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    token_value = Column(String(64), unique=True, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    transaction_type = Column(String(50))
    customer_phone = Column(String(20))
    status = Column(String(20), default="active")
    expires_at = Column(DateTime(timezone=True))
    used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SelfServiceTransaction(Base):
    __tablename__ = "self_service_transactions"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_phone = Column(String(20))
    customer_bvn = Column(String(20))
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="NGN")
    transaction_type = Column(String(50))
    description = Column(Text)
    reference = Column(String(100), unique=True)
    channel = Column(String(10))  # qr | nfc
    status = Column(String(20), default="pending", index=True)
    gateway_reference = Column(String(100))
    failure_reason = Column(Text)
    qr_payload = Column(JSONB)
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class StaticQRRequest(BaseModel):
    agent_id: UUID
    agent_name: str
    agent_code: str
    bank_code: str
    account_number: str


class DynamicQRRequest(BaseModel):
    agent_id: UUID
    amount: Decimal = Field(..., gt=0)
    transaction_type: str
    description: str
    customer_phone: Optional[str] = None


class QRScanRequest(BaseModel):
    qr_data: str
    customer_phone: str
    customer_bvn: Optional[str] = None
    override_amount: Optional[Decimal] = None


class NFCTokenRequest(BaseModel):
    agent_id: UUID
    amount: Decimal = Field(..., gt=0)
    transaction_type: str
    customer_phone: str


class NFCValidateRequest(BaseModel):
    token_value: str
    agent_id: UUID


class QRCodeResponse(BaseModel):
    id: UUID
    agent_id: UUID
    qr_type: str
    amount: Optional[Decimal]
    reference: Optional[str]
    status: str
    qr_image_base64: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    amount: Decimal
    transaction_type: Optional[str]
    reference: Optional[str]
    channel: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class QRType:
    STATIC = "static"
    DYNAMIC = "dynamic"


class QRStatus:
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"


class TransactionStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
