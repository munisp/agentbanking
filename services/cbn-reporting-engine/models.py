"""Models for CBN Reporting Engine."""
from datetime import datetime, timezone, date
from typing import Optional, Dict, List, Any
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, Numeric, Text, Date
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CBNReport(Base):
    __tablename__ = "cbn_reports"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_type = Column(String(50), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    institution_code = Column(String(20), nullable=False)
    data = Column(JSONB, nullable=False)
    status = Column(String(30), default="generated", index=True)
    submission_deadline = Column(Date)
    cbn_reference = Column(String(100))
    generated_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SuspiciousActivityReport(Base):
    __tablename__ = "suspicious_activity_reports"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    transaction_ids = Column(JSONB, default=[])
    total_amount = Column(Numeric(18, 2))
    reason = Column(String(100))
    description = Column(Text)
    customer_details = Column(JSONB, default={})
    status = Column(String(30), default="pending_submission")
    submission_deadline = Column(Date)
    cbn_reference = Column(String(100))
    filed_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class MonthlyReportRequest(BaseModel):
    year: int
    month: int
    institution_code: str
    institution_name: str


class QuarterlyFraudReportRequest(BaseModel):
    year: int
    quarter: int
    institution_code: str


class SARRequest(BaseModel):
    agent_id: UUID
    transaction_ids: List[UUID]
    total_amount: Decimal
    reason: str
    description: str
    customer_details: Optional[Dict] = None


class ReportResponse(BaseModel):
    id: UUID
    report_type: str
    period_start: datetime
    period_end: datetime
    institution_code: str
    status: str
    submission_deadline: Optional[date]
    cbn_reference: Optional[str]
    generated_at: Optional[datetime]
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True


class SARResponse(BaseModel):
    id: UUID
    agent_id: UUID
    total_amount: Optional[Decimal]
    reason: Optional[str]
    status: str
    submission_deadline: Optional[date]
    filed_at: Optional[datetime]

    class Config:
        from_attributes = True


class CBNReportType:
    MONTHLY_ACTIVITY = "monthly_activity"
    QUARTERLY_FRAUD = "quarterly_fraud"
    ANNUAL_KYC = "annual_kyc"
    SAR = "sar"
    NETWORK_EXPANSION = "network_expansion"


class CBNReportStatus:
    GENERATED = "generated"
    PENDING_SUBMISSION = "pending_submission"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
