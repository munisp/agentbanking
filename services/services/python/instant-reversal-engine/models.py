"""Models for Instant Reversal Engine."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ReversalRequest(Base):
    __tablename__ = "reversal_requests"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    original_transaction_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_phone = Column(String(20))
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default="NGN")
    reversal_reason = Column(String(100), nullable=False)
    status = Column(String(30), default="pending", index=True)
    auto_triggered = Column(Boolean, default=False)
    detection_source = Column(String(50))
    bank_reference = Column(String(100))
    reversal_reference = Column(String(100))
    initiated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True))
    sla_deadline = Column(DateTime(timezone=True), index=True)
    sla_breached = Column(Boolean, default=False)
    notification_sent = Column(Boolean, default=False)
    escalated_at = Column(DateTime(timezone=True))
    escalation_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReversalAuditLog(Base):
    __tablename__ = "reversal_audit_log"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    reversal_id = Column(PGUUID(as_uuid=True), ForeignKey("reversal_requests.id"), nullable=False)
    action = Column(String(50), nullable=False)
    actor = Column(String(100))
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class InitiateReversalRequest(BaseModel):
    original_transaction_id: UUID
    agent_id: UUID
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., description="double_debit|failed_dispense|network_error|timeout")
    customer_phone: Optional[str] = None
    auto_triggered: bool = False
    detection_source: str = "agent_report"


class ReversalResponse(BaseModel):
    id: UUID
    original_transaction_id: UUID
    agent_id: UUID
    amount: Decimal
    status: str
    reversal_reason: str
    sla_deadline: Optional[datetime]
    sla_breached: bool
    initiated_at: datetime
    completed_at: Optional[datetime]
    reversal_reference: Optional[str]

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    actor: Optional[str]
    details: Optional[Dict]
    created_at: datetime

    class Config:
        from_attributes = True


# Enums
class ReversalStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class ReversalReason:
    DOUBLE_DEBIT = "double_debit"
    FAILED_DISPENSE = "failed_dispense"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"


class DetectionSource:
    SYSTEM_AUTO = "system_auto"
    AGENT_REPORT = "agent_report"
    CUSTOMER_REPORT = "customer_report"
