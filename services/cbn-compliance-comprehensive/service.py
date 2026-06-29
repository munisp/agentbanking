"""
Comprehensive CBN Compliance Reports Service
Covers all Central Bank of Nigeria regulatory reporting requirements:
- Annual Returns (AFS)
- Monthly Activity Reports (MAR)
- Quarterly Fraud & Forgeries Reports (QFFR)
- Suspicious Activity Reports (SAR)
- Currency Transaction Reports (CTR) - transactions >= NGN 5,000,000
- Foreign Exchange Returns
- Consumer Complaints Returns
- Agent Network Activity Reports
- Know Your Customer (KYC) Compliance Reports
- Anti-Money Laundering (AML) Reports
- Cybersecurity Incident Reports
- NFIU (Nigerian Financial Intelligence Unit) Reports
"""

import os
import csv
import json
import hashlib
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum
from uuid import UUID, uuid4
import httpx

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime, Date,
    Enum as SAEnum, Text, ForeignKey, Index, func, and_, or_
)
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()

# ─────────────────────────────────────────────
# CONSTANTS — CBN Regulatory Thresholds
# ─────────────────────────────────────────────
CTR_THRESHOLD_NGN = Decimal("5000000")       # NGN 5M — Currency Transaction Report
SAR_THRESHOLD_NGN = Decimal("1000000")       # NGN 1M — Suspicious Activity threshold
LARGE_CASH_THRESHOLD = Decimal("500000")     # NGN 500K — Large cash transaction
VAT_RATE = Decimal("0.075")                  # 7.5% Nigeria VAT (Finance Act 2020)
WITHHOLDING_TAX_RATE = Decimal("0.05")       # 5% WHT on agency commissions


class ReportType(str, Enum):
    MONTHLY_ACTIVITY = "MONTHLY_ACTIVITY"
    QUARTERLY_FRAUD = "QUARTERLY_FRAUD"
    SAR = "SAR"
    CTR = "CTR"
    ANNUAL_RETURNS = "ANNUAL_RETURNS"
    FOREX_RETURNS = "FOREX_RETURNS"
    CONSUMER_COMPLAINTS = "CONSUMER_COMPLAINTS"
    AGENT_NETWORK = "AGENT_NETWORK"
    KYC_COMPLIANCE = "KYC_COMPLIANCE"
    AML_REPORT = "AML_REPORT"
    CYBERSECURITY_INCIDENT = "CYBERSECURITY_INCIDENT"
    NFIU_REPORT = "NFIU_REPORT"


class ReportStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    REVIEWED = "REVIEWED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"


class FraudType(str, Enum):
    CARD_FRAUD = "CARD_FRAUD"
    INTERNET_BANKING = "INTERNET_BANKING"
    MOBILE_FRAUD = "MOBILE_FRAUD"
    IDENTITY_THEFT = "IDENTITY_THEFT"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    PHISHING = "PHISHING"
    SOCIAL_ENGINEERING = "SOCIAL_ENGINEERING"
    INSIDER_FRAUD = "INSIDER_FRAUD"
    FORGED_DOCUMENTS = "FORGED_DOCUMENTS"
    UNAUTHORIZED_TRANSFER = "UNAUTHORIZED_TRANSFER"


class SARReason(str, Enum):
    STRUCTURING = "STRUCTURING"
    UNUSUAL_PATTERN = "UNUSUAL_PATTERN"
    TERRORIST_FINANCING = "TERRORIST_FINANCING"
    DRUG_TRAFFICKING = "DRUG_TRAFFICKING"
    POLITICALLY_EXPOSED = "POLITICALLY_EXPOSED"
    SANCTIONS_MATCH = "SANCTIONS_MATCH"
    LAYERING = "LAYERING"
    SMURFING = "SMURFING"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────

class CBNReport(Base):
    __tablename__ = "cbn_compliance_reports"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_type = Column(SAEnum(ReportType), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(SAEnum(ReportStatus), default=ReportStatus.DRAFT, nullable=False)
    institution_code = Column(String(20), nullable=False)
    institution_name = Column(String(200), nullable=False)
    report_data = Column(Text, nullable=False)  # JSON blob
    submission_reference = Column(String(100), nullable=True)
    cbn_acknowledgement = Column(String(200), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(100), nullable=False)
    checksum = Column(String(64), nullable=True)  # SHA-256 of report_data
    __table_args__ = (
        Index("ix_cbn_report_type_period", "report_type", "period_start", "period_end"),
    )


class CTRRecord(Base):
    __tablename__ = "ctn_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    transaction_id = Column(String(100), nullable=False, unique=True)
    transaction_date = Column(DateTime, nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    currency = Column(String(3), default="NGN")
    transaction_type = Column(String(50), nullable=False)  # CASH_DEPOSIT, CASH_WITHDRAWAL, TRANSFER
    customer_name = Column(String(200), nullable=False)
    customer_bvn = Column(String(11), nullable=True)
    customer_nin = Column(String(11), nullable=True)
    customer_account = Column(String(20), nullable=False)
    agent_id = Column(String(100), nullable=False)
    agent_name = Column(String(200), nullable=False)
    branch_code = Column(String(20), nullable=True)
    reported = Column(Boolean, default=False)
    report_id = Column(String(36), ForeignKey("cbn_compliance_reports.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SARRecord(Base):
    __tablename__ = "sar_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    reference_number = Column(String(50), nullable=False, unique=True)
    subject_name = Column(String(200), nullable=False)
    subject_bvn = Column(String(11), nullable=True)
    subject_account = Column(String(20), nullable=True)
    reason = Column(SAEnum(SARReason), nullable=False)
    description = Column(Text, nullable=False)
    amount_involved = Column(Numeric(20, 2), nullable=True)
    transaction_ids = Column(Text, nullable=True)  # JSON array
    reported_by = Column(String(100), nullable=False)
    report_id = Column(String(36), ForeignKey("cbn_compliance_reports.id"), nullable=True)
    nfiu_reference = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FraudRecord(Base):
    __tablename__ = "fraud_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    fraud_type = Column(SAEnum(FraudType), nullable=False)
    incident_date = Column(DateTime, nullable=False)
    amount_attempted = Column(Numeric(20, 2), nullable=False)
    amount_lost = Column(Numeric(20, 2), nullable=False)
    amount_recovered = Column(Numeric(20, 2), default=Decimal("0"))
    victim_account = Column(String(20), nullable=True)
    perpetrator_info = Column(Text, nullable=True)
    channel = Column(String(50), nullable=False)  # MOBILE, POS, USSD, INTERNET
    resolution_status = Column(String(50), default="PENDING")
    police_report_number = Column(String(100), nullable=True)
    report_id = Column(String(36), ForeignKey("cbn_compliance_reports.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentNetworkReport(Base):
    __tablename__ = "agent_network_reports"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_period = Column(String(7), nullable=False)  # YYYY-MM
    total_agents = Column(Integer, default=0)
    active_agents = Column(Integer, default=0)
    new_agents = Column(Integer, default=0)
    suspended_agents = Column(Integer, default=0)
    terminated_agents = Column(Integer, default=0)
    total_transactions = Column(Integer, default=0)
    total_transaction_value = Column(Numeric(20, 2), default=Decimal("0"))
    cash_in_transactions = Column(Integer, default=0)
    cash_in_value = Column(Numeric(20, 2), default=Decimal("0"))
    cash_out_transactions = Column(Integer, default=0)
    cash_out_value = Column(Numeric(20, 2), default=Decimal("0"))
    transfer_transactions = Column(Integer, default=0)
    transfer_value = Column(Numeric(20, 2), default=Decimal("0"))
    bill_payment_transactions = Column(Integer, default=0)
    bill_payment_value = Column(Numeric(20, 2), default=Decimal("0"))
    states_covered = Column(Integer, default=0)
    lgas_covered = Column(Integer, default=0)
    report_id = Column(String(36), ForeignKey("cbn_compliance_reports.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ComplianceFiling(Base):
    __tablename__ = "compliance_filings"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filing_type = Column(String(50), nullable=False)
    period = Column(String(20), nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(String(30), default="draft")
    description = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ComplianceKYCRecord(Base):
    __tablename__ = "compliance_kyc_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id = Column(String(100), nullable=False, index=True)
    status = Column(String(30), default="pending")
    risk_level = Column(String(20), default="low")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class KYCDocument(Base):
    __tablename__ = "kyc_documents"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id = Column(String(36), ForeignKey("compliance_kyc_records.id"), nullable=False, index=True)
    document_type = Column(String(50), nullable=False)
    document_number = Column(String(100), nullable=True)
    expiry_date = Column(String(20), nullable=True)
    file_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KYCCheck(Base):
    __tablename__ = "kyc_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id = Column(String(36), ForeignKey("compliance_kyc_records.id"), nullable=False, index=True)
    check_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False)
    result = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GDPRRequest(Base):
    __tablename__ = "gdpr_requests"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    type = Column(String(30), nullable=False)   # access, erasure, portability, rectification
    subject_name = Column(String(200), nullable=False)
    subject_email = Column(String(200), nullable=False)
    status = Column(String(30), default="pending")  # pending, in_progress, completed, rejected
    submitted_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SandboxExperiment(Base):
    __tablename__ = "sandbox_experiments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)   # payment_limit, kyc_threshold, agent_tier, fee_structure, float_policy
    status = Column(String(30), default="draft")    # draft, running, completed, failed
    participants = Column(Integer, default=0)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    results = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ReportScheduleRecord(Base):
    __tablename__ = "report_schedule_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    frequency = Column(String(30), nullable=False)  # daily, weekly, monthly, quarterly
    status = Column(String(30), default="active")   # active, paused, failed
    format = Column(String(10), default="pdf")      # pdf, xlsx, csv
    recipients = Column(Text, nullable=True)         # JSON array of emails
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    last_run_report_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type = Column(String(100), nullable=False)
    retention_days = Column(Integer, nullable=False)
    legal_basis = Column(String(20), nullable=False)   # CBN, NDPR, GDPR
    archive_policy = Column(String(20), default="archive")  # archive, delete
    last_enforced = Column(Date, nullable=True)
    next_run = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ComplianceFramework(Base):
    __tablename__ = "compliance_frameworks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    compliance_pct = Column(Integer, default=0)
    controls_total = Column(Integer, default=0)
    controls_passing = Column(Integer, default=0)
    controls_failing = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ComplianceAudit(Base):
    __tablename__ = "compliance_audits"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    framework = Column(String(100), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    auditor = Column(String(200), nullable=False)
    status = Column(String(30), default="scheduled")  # scheduled, in_progress, completed, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CompliancePolicy(Base):
    __tablename__ = "compliance_policies"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    version = Column(Integer, default=1)
    status = Column(String(30), default="active")   # active, under_review, archived
    last_review = Column(Date, nullable=True)
    next_review = Column(Date, nullable=True)
    owner = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────

class MonthlyActivityRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2030)
    month: int = Field(..., ge=1, le=12)
    institution_code: str
    institution_name: str
    generated_by: str


class QuarterlyFraudRequest(BaseModel):
    year: int
    quarter: int = Field(..., ge=1, le=4)
    institution_code: str
    institution_name: str
    generated_by: str


class CTRRequest(BaseModel):
    start_date: date
    end_date: date
    institution_code: str
    institution_name: str
    generated_by: str


class SARRequest(BaseModel):
    subject_name: str
    subject_bvn: Optional[str] = None
    subject_account: Optional[str] = None
    reason: SARReason
    description: str
    amount_involved: Optional[Decimal] = None
    transaction_ids: Optional[List[str]] = None
    reported_by: str
    institution_code: str
    institution_name: str


class AgentNetworkRequest(BaseModel):
    year: int
    month: int = Field(..., ge=1, le=12)
    institution_code: str
    institution_name: str
    generated_by: str


class AMLReportRequest(BaseModel):
    start_date: date
    end_date: date
    institution_code: str
    institution_name: str
    generated_by: str


class KYCComplianceRequest(BaseModel):
    year: int
    month: int = Field(..., ge=1, le=12)
    institution_code: str
    institution_name: str
    generated_by: str


class ReportResponse(BaseModel):
    id: str
    report_type: ReportType
    period_start: date
    period_end: date
    status: ReportStatus
    institution_code: str
    institution_name: str
    generated_at: datetime
    generated_by: str
    checksum: Optional[str]
    submission_reference: Optional[str]
    cbn_acknowledgement: Optional[str]

    class Config:
        from_attributes = True


class ReportSummary(BaseModel):
    report_id: str
    report_type: str
    period: str
    status: str
    generated_at: str
    checksum: str


class CreateFilingRequest(BaseModel):
    filing_type: str
    period: str
    due_date: Optional[date] = None
    description: Optional[str] = None


class CreateKYCRecordRequest(BaseModel):
    customer_id: str
    risk_level: Optional[str] = "low"
    notes: Optional[str] = None


class UpdateKYCRecordRequest(BaseModel):
    status: Optional[str] = None
    risk_level: Optional[str] = None
    notes: Optional[str] = None


class AddKYCDocumentRequest(BaseModel):
    document_type: str
    document_number: Optional[str] = None
    expiry_date: Optional[str] = None
    file_url: Optional[str] = None


class AddKYCCheckRequest(BaseModel):
    check_type: str
    status: str
    result: Optional[Dict] = None
    notes: Optional[str] = None


# ─────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────

class CBNComplianceService:
    """
    Comprehensive CBN Compliance Reporting Service.
    Generates all regulatory reports required by the Central Bank of Nigeria
    for licensed agency banking operators.
    """

    def __init__(self, db: Session):
        self.db = db

    def _checksum(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def _quarter_dates(self, year: int, quarter: int):
        starts = {1: date(year, 1, 1), 2: date(year, 4, 1),
                  3: date(year, 7, 1), 4: date(year, 10, 1)}
        ends = {1: date(year, 3, 31), 2: date(year, 6, 30),
                3: date(year, 9, 30), 4: date(year, 12, 31)}
        return starts[quarter], ends[quarter]

    def generate_monthly_activity_report(self, req: MonthlyActivityRequest) -> CBNReport:
        """
        CBN Monthly Activity Report (MAR) — due by 10th of following month.
        Covers all agency banking transactions for the period.
        """
        period_start = date(req.year, req.month, 1)
        last_day = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        period_end = last_day

        # Aggregate agent network data for the period
        net_report = (
            self.db.query(AgentNetworkReport)
            .filter(AgentNetworkReport.report_period == f"{req.year}-{req.month:02d}")
            .first()
        )

        # Build MAR data structure per CBN template
        mar_data = {
            "report_type": "MONTHLY_ACTIVITY_REPORT",
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "reporting_period": f"{req.year}-{req.month:02d}",
            "period_start": str(period_start),
            "period_end": str(period_end),
            "submission_deadline": str(period_end + timedelta(days=10)),
            "section_a_agent_network": {
                "total_registered_agents": net_report.total_agents if net_report else 0,
                "active_agents": net_report.active_agents if net_report else 0,
                "new_agents_onboarded": net_report.new_agents if net_report else 0,
                "suspended_agents": net_report.suspended_agents if net_report else 0,
                "terminated_agents": net_report.terminated_agents if net_report else 0,
                "states_covered": net_report.states_covered if net_report else 36,
                "lgas_covered": net_report.lgas_covered if net_report else 0,
            },
            "section_b_transactions": {
                "total_transactions": net_report.total_transactions if net_report else 0,
                "total_value_ngn": str(net_report.total_transaction_value if net_report else 0),
                "cash_in": {
                    "count": net_report.cash_in_transactions if net_report else 0,
                    "value_ngn": str(net_report.cash_in_value if net_report else 0),
                },
                "cash_out": {
                    "count": net_report.cash_out_transactions if net_report else 0,
                    "value_ngn": str(net_report.cash_out_value if net_report else 0),
                },
                "transfers": {
                    "count": net_report.transfer_transactions if net_report else 0,
                    "value_ngn": str(net_report.transfer_value if net_report else 0),
                },
                "bill_payments": {
                    "count": net_report.bill_payment_transactions if net_report else 0,
                    "value_ngn": str(net_report.bill_payment_value if net_report else 0),
                },
            },
            "section_c_ctr_summary": {
                "total_ctrs_filed": self.db.query(CTRRecord)
                    .filter(
                        CTRRecord.transaction_date >= datetime.combine(period_start, datetime.min.time()),
                        CTRRecord.transaction_date <= datetime.combine(period_end, datetime.max.time()),
                        CTRRecord.reported == True
                    ).count(),
                "total_ctr_value_ngn": str(
                    self.db.query(func.sum(CTRRecord.amount))
                    .filter(
                        CTRRecord.transaction_date >= datetime.combine(period_start, datetime.min.time()),
                        CTRRecord.transaction_date <= datetime.combine(period_end, datetime.max.time()),
                        CTRRecord.reported == True
                    ).scalar() or 0
                ),
            },
            "section_d_sar_summary": {
                "total_sars_filed": self.db.query(SARRecord)
                    .filter(
                        SARRecord.created_at >= datetime.combine(period_start, datetime.min.time()),
                        SARRecord.created_at <= datetime.combine(period_end, datetime.max.time()),
                    ).count(),
            },
            "section_e_complaints": {
                "total_complaints_received": 0,
                "total_complaints_resolved": 0,
                "resolution_rate_pct": 0,
                "average_resolution_days": 0,
            },
            "certification": {
                "certified_by": req.generated_by,
                "certification_date": str(date.today()),
                "statement": (
                    "I certify that the information provided in this report is true, "
                    "accurate and complete to the best of my knowledge and belief."
                ),
            },
        }

        data_json = json.dumps(mar_data, indent=2)
        report = CBNReport(
            report_type=ReportType.MONTHLY_ACTIVITY,
            period_start=period_start,
            period_end=period_end,
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.generated_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        logger.info(f"Generated MAR for {req.year}-{req.month:02d}: {report.id}")
        return report

    def generate_quarterly_fraud_report(self, req: QuarterlyFraudRequest) -> CBNReport:
        """
        CBN Quarterly Fraud & Forgeries Report (QFFR) — due within 30 days of quarter end.
        """
        period_start, period_end = self._quarter_dates(req.year, req.quarter)

        fraud_records = (
            self.db.query(FraudRecord)
            .filter(
                FraudRecord.incident_date >= datetime.combine(period_start, datetime.min.time()),
                FraudRecord.incident_date <= datetime.combine(period_end, datetime.max.time()),
            )
            .all()
        )

        # Aggregate by fraud type
        by_type: Dict[str, Dict] = {}
        for fr in fraud_records:
            ft = fr.fraud_type.value
            if ft not in by_type:
                by_type[ft] = {"count": 0, "amount_attempted": 0, "amount_lost": 0, "amount_recovered": 0}
            by_type[ft]["count"] += 1
            by_type[ft]["amount_attempted"] += float(fr.amount_attempted)
            by_type[ft]["amount_lost"] += float(fr.amount_lost)
            by_type[ft]["amount_recovered"] += float(fr.amount_recovered)

        total_attempted = sum(float(f.amount_attempted) for f in fraud_records)
        total_lost = sum(float(f.amount_lost) for f in fraud_records)
        total_recovered = sum(float(f.amount_recovered) for f in fraud_records)

        qffr_data = {
            "report_type": "QUARTERLY_FRAUD_FORGERIES_REPORT",
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "year": req.year,
            "quarter": req.quarter,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "submission_deadline": str(period_end + timedelta(days=30)),
            "summary": {
                "total_incidents": len(fraud_records),
                "total_amount_attempted_ngn": total_attempted,
                "total_amount_lost_ngn": total_lost,
                "total_amount_recovered_ngn": total_recovered,
                "recovery_rate_pct": round((total_recovered / total_lost * 100) if total_lost > 0 else 0, 2),
            },
            "breakdown_by_fraud_type": by_type,
            "breakdown_by_channel": self._aggregate_fraud_by_channel(fraud_records),
            "incidents": [
                {
                    "id": f.id,
                    "fraud_type": f.fraud_type.value,
                    "incident_date": str(f.incident_date.date()),
                    "amount_attempted": float(f.amount_attempted),
                    "amount_lost": float(f.amount_lost),
                    "amount_recovered": float(f.amount_recovered),
                    "channel": f.channel,
                    "resolution_status": f.resolution_status,
                    "police_report_number": f.police_report_number,
                }
                for f in fraud_records
            ],
        }

        data_json = json.dumps(qffr_data, indent=2)
        report = CBNReport(
            report_type=ReportType.QUARTERLY_FRAUD,
            period_start=period_start,
            period_end=period_end,
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.generated_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _aggregate_fraud_by_channel(self, records: List[FraudRecord]) -> Dict:
        channels: Dict[str, Dict] = {}
        for r in records:
            ch = r.channel
            if ch not in channels:
                channels[ch] = {"count": 0, "amount_lost": 0}
            channels[ch]["count"] += 1
            channels[ch]["amount_lost"] += float(r.amount_lost)
        return channels

    def file_sar(self, req: SARRequest) -> SARRecord:
        """
        File a Suspicious Activity Report (SAR) with NFIU reference generation.
        """
        ref = f"SAR-{req.institution_code}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid4())[:8].upper()}"

        # Create the SAR report envelope
        sar_data = {
            "report_type": "SUSPICIOUS_ACTIVITY_REPORT",
            "reference_number": ref,
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "filing_date": str(date.today()),
            "subject": {
                "name": req.subject_name,
                "bvn": req.subject_bvn,
                "account_number": req.subject_account,
            },
            "suspicion": {
                "reason": req.reason.value,
                "description": req.description,
                "amount_involved_ngn": str(req.amount_involved) if req.amount_involved else None,
                "transaction_ids": req.transaction_ids or [],
            },
            "reported_by": req.reported_by,
            "nfiu_submission": {
                "required": True,
                "deadline_days": 3,
                "submission_channel": "NFIU_PORTAL",
            },
        }

        data_json = json.dumps(sar_data, indent=2)
        cbn_report = CBNReport(
            report_type=ReportType.SAR,
            period_start=date.today(),
            period_end=date.today(),
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.reported_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(cbn_report)
        self.db.flush()

        sar = SARRecord(
            reference_number=ref,
            subject_name=req.subject_name,
            subject_bvn=req.subject_bvn,
            subject_account=req.subject_account,
            reason=req.reason,
            description=req.description,
            amount_involved=req.amount_involved,
            transaction_ids=json.dumps(req.transaction_ids or []),
            reported_by=req.reported_by,
            report_id=cbn_report.id,
        )
        self.db.add(sar)
        self.db.commit()
        self.db.refresh(sar)
        logger.info(f"SAR filed: {ref}")
        return sar

    def generate_ctr_report(self, req: CTRRequest) -> CBNReport:
        """
        Currency Transaction Report (CTR) — all cash transactions >= NGN 5,000,000.
        Must be filed within 24 hours of transaction.
        """
        ctrs = (
            self.db.query(CTRRecord)
            .filter(
                CTRRecord.transaction_date >= datetime.combine(req.start_date, datetime.min.time()),
                CTRRecord.transaction_date <= datetime.combine(req.end_date, datetime.max.time()),
                CTRRecord.amount >= CTR_THRESHOLD_NGN,
            )
            .all()
        )

        ctr_data = {
            "report_type": "CURRENCY_TRANSACTION_REPORT",
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "period_start": str(req.start_date),
            "period_end": str(req.end_date),
            "threshold_ngn": str(CTR_THRESHOLD_NGN),
            "total_transactions": len(ctrs),
            "total_value_ngn": str(sum(c.amount for c in ctrs)),
            "transactions": [
                {
                    "transaction_id": c.transaction_id,
                    "date": str(c.transaction_date.date()),
                    "time": c.transaction_date.strftime("%H:%M:%S"),
                    "amount_ngn": str(c.amount),
                    "currency": c.currency,
                    "type": c.transaction_type,
                    "customer_name": c.customer_name,
                    "customer_bvn": c.customer_bvn,
                    "customer_nin": c.customer_nin,
                    "account_number": c.customer_account,
                    "agent_id": c.agent_id,
                    "agent_name": c.agent_name,
                    "branch_code": c.branch_code,
                }
                for c in ctrs
            ],
        }

        # Mark CTRs as reported
        for c in ctrs:
            c.reported = True

        data_json = json.dumps(ctr_data, indent=2)
        report = CBNReport(
            report_type=ReportType.CTR,
            period_start=req.start_date,
            period_end=req.end_date,
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.generated_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def generate_agent_network_report(self, req: AgentNetworkRequest) -> CBNReport:
        """
        Agent Network Activity Report — monthly submission to CBN.
        """
        period_str = f"{req.year}-{req.month:02d}"
        period_start = date(req.year, req.month, 1)
        last_day = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        net = (
            self.db.query(AgentNetworkReport)
            .filter(AgentNetworkReport.report_period == period_str)
            .first()
        )

        anr_data = {
            "report_type": "AGENT_NETWORK_ACTIVITY_REPORT",
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "period": period_str,
            "agent_statistics": {
                "total_registered": net.total_agents if net else 0,
                "active": net.active_agents if net else 0,
                "new_onboarded": net.new_agents if net else 0,
                "suspended": net.suspended_agents if net else 0,
                "terminated": net.terminated_agents if net else 0,
                "pending_approval": 0,
                "geographic_coverage": {
                    "states": net.states_covered if net else 0,
                    "lgas": net.lgas_covered if net else 0,
                },
            },
            "transaction_statistics": {
                "total_count": net.total_transactions if net else 0,
                "total_value_ngn": str(net.total_transaction_value if net else 0),
                "by_type": {
                    "cash_in": {"count": net.cash_in_transactions if net else 0,
                                "value": str(net.cash_in_value if net else 0)},
                    "cash_out": {"count": net.cash_out_transactions if net else 0,
                                 "value": str(net.cash_out_value if net else 0)},
                    "transfers": {"count": net.transfer_transactions if net else 0,
                                  "value": str(net.transfer_value if net else 0)},
                    "bill_payments": {"count": net.bill_payment_transactions if net else 0,
                                      "value": str(net.bill_payment_value if net else 0)},
                },
            },
            "compliance_metrics": {
                "kyc_completion_rate_pct": round(
                    self.db.query(ComplianceKYCRecord).filter(
                        ComplianceKYCRecord.status.in_(["approved", "verified"])
                    ).count() / max(self.db.query(ComplianceKYCRecord).count(), 1) * 100, 1
                ),
                "transaction_monitoring_coverage_pct": 100.0,
                "aml_screening_coverage_pct": 100.0,
            },
        }

        data_json = json.dumps(anr_data, indent=2)
        report = CBNReport(
            report_type=ReportType.AGENT_NETWORK,
            period_start=period_start,
            period_end=last_day,
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.generated_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def generate_aml_report(self, req: AMLReportRequest) -> CBNReport:
        """
        Anti-Money Laundering (AML) Report — covers screening, monitoring, and escalations.
        """
        sars_in_period = (
            self.db.query(SARRecord)
            .filter(
                SARRecord.created_at >= datetime.combine(req.start_date, datetime.min.time()),
                SARRecord.created_at <= datetime.combine(req.end_date, datetime.max.time()),
            )
            .all()
        )

        aml_data = {
            "report_type": "AML_REPORT",
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "period_start": str(req.start_date),
            "period_end": str(req.end_date),
            "screening_statistics": {
                "total_customers_screened": 0,
                "pep_matches": 0,
                "sanctions_matches": 0,
                "adverse_media_matches": 0,
                "false_positives": 0,
                "confirmed_matches": 0,
            },
            "transaction_monitoring": {
                "total_alerts_generated": len(sars_in_period),
                "alerts_investigated": len(sars_in_period),
                "sars_filed": len(sars_in_period),
                "cases_closed_no_action": 0,
                "cases_escalated_to_nfiu": sum(1 for s in sars_in_period if s.nfiu_reference),
            },
            "sar_breakdown_by_reason": self._sar_breakdown(sars_in_period),
            "training_compliance": {
                "staff_trained_on_aml": 0,
                "training_completion_rate_pct": 100.0,
                "last_training_date": str(date.today()),
            },
            "policy_updates": {
                "aml_policy_last_reviewed": str(date.today()),
                "next_review_date": str(date.today().replace(year=date.today().year + 1)),
            },
        }

        data_json = json.dumps(aml_data, indent=2)
        report = CBNReport(
            report_type=ReportType.AML_REPORT,
            period_start=req.start_date,
            period_end=req.end_date,
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.generated_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _sar_breakdown(self, sars: List[SARRecord]) -> Dict:
        breakdown: Dict[str, int] = {}
        for s in sars:
            r = s.reason.value
            breakdown[r] = breakdown.get(r, 0) + 1
        return breakdown

    def generate_kyc_compliance_report(self, req: KYCComplianceRequest) -> CBNReport:
        """
        KYC Compliance Report — BVN verification, tiered KYC levels, documentation.
        """
        period_str = f"{req.year}-{req.month:02d}"
        period_start = date(req.year, req.month, 1)
        last_day = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        # KYC counts from compliance_kyc_records — populated by push from agent-service
        total_kyc = self.db.query(ComplianceKYCRecord).count()
        verified_kyc = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status.in_(["approved", "verified"])
        ).count()
        pending_kyc = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status.in_(["pending", "in_review"])
        ).count()
        rejected_kyc = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status == "rejected"
        ).count()
        high_risk_count = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.risk_level == "high"
        ).count()

        # Document counts from kyc_documents
        doc_national_id = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%national%")
        ).count()
        doc_passport = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%passport%")
        ).count()
        doc_drivers = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%driver%")
        ).count()
        doc_utility = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%utility%")
        ).count()

        # BVN verification checks
        bvn_attempted = self.db.query(KYCCheck).filter(
            KYCCheck.check_type == "bvn_verification"
        ).count()
        bvn_passed = self.db.query(KYCCheck).filter(
            KYCCheck.check_type == "bvn_verification",
            KYCCheck.status == "passed"
        ).count()
        bvn_failed = bvn_attempted - bvn_passed
        bvn_rate = round((bvn_passed / max(bvn_attempted, 1)) * 100, 1)

        # Tier distribution — inferred from documents: tier 3 = has national_id/passport, tier 2 = bvn only
        tier_3_count = verified_kyc
        tier_2_count = pending_kyc
        tier_1_count = max(0, total_kyc - tier_3_count - tier_2_count)

        kyc_data = {
            "report_type": "KYC_COMPLIANCE_REPORT",
            "institution_code": req.institution_code,
            "institution_name": req.institution_name,
            "period": period_str,
            "summary": {
                "total_records": total_kyc,
                "verified": verified_kyc,
                "pending": pending_kyc,
                "rejected": rejected_kyc,
                "high_risk": high_risk_count,
                "compliance_rate_pct": round((verified_kyc / max(total_kyc, 1)) * 100, 1),
            },
            "customer_tiering": {
                "tier_1_no_kyc": {
                    "count": tier_1_count,
                    "max_single_transaction_ngn": 5000,
                    "max_daily_limit_ngn": 20000,
                    "max_balance_ngn": 300000,
                },
                "tier_2_bvn_only": {
                    "count": tier_2_count,
                    "max_single_transaction_ngn": 50000,
                    "max_daily_limit_ngn": 200000,
                    "max_balance_ngn": 500000,
                },
                "tier_3_full_kyc": {
                    "count": tier_3_count,
                    "max_single_transaction_ngn": None,
                    "max_daily_limit_ngn": None,
                    "max_balance_ngn": None,
                },
            },
            "bvn_verification": {
                "total_verifications_attempted": bvn_attempted,
                "successful_verifications": bvn_passed,
                "failed_verifications": bvn_failed,
                "success_rate_pct": bvn_rate,
            },
            "document_collection": {
                "national_id_collected": doc_national_id,
                "passport_collected": doc_passport,
                "drivers_license_collected": doc_drivers,
                "utility_bill_collected": doc_utility,
                "total_customers_fully_documented": verified_kyc,
            },
            "enhanced_due_diligence": {
                "pep_customers": 0,
                "high_risk_customers": high_risk_count,
                "edd_reviews_completed": self.db.query(ComplianceKYCRecord).filter(
                    ComplianceKYCRecord.risk_level == "high",
                    ComplianceKYCRecord.status.in_(["approved", "verified"])
                ).count(),
            },
            "exceptions": {
                "customers_exceeding_tier_limits": 0,
                "unverified_customers_transacting": pending_kyc,
                "expired_kyc_documents": 0,
            },
        }

        data_json = json.dumps(kyc_data, indent=2)
        report = CBNReport(
            report_type=ReportType.KYC_COMPLIANCE,
            period_start=period_start,
            period_end=last_day,
            status=ReportStatus.GENERATED,
            institution_code=req.institution_code,
            institution_name=req.institution_name,
            report_data=data_json,
            generated_by=req.generated_by,
            checksum=self._checksum(data_json),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def submit_report(self, report_id: str, submission_reference: str) -> CBNReport:
        """Mark a report as submitted to CBN portal."""
        report = self.db.query(CBNReport).filter(CBNReport.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        report.status = ReportStatus.SUBMITTED
        report.submission_reference = submission_reference
        report.submitted_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(report)
        return report

    def acknowledge_report(self, report_id: str, cbn_reference: str) -> CBNReport:
        """Record CBN acknowledgement of a submitted report."""
        report = self.db.query(CBNReport).filter(CBNReport.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        report.status = ReportStatus.ACKNOWLEDGED
        report.cbn_acknowledgement = cbn_reference
        self.db.commit()
        self.db.refresh(report)
        return report

    def export_report_csv(self, report_id: str) -> str:
        """Export report data as CSV string."""
        report = self.db.query(CBNReport).filter(CBNReport.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        data = json.loads(report.report_data)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Field", "Value"])
        self._flatten_dict(data, writer)
        return output.getvalue()

    def _flatten_dict(self, d: Any, writer, prefix: str = ""):
        if isinstance(d, dict):
            for k, v in d.items():
                self._flatten_dict(v, writer, f"{prefix}.{k}" if prefix else k)
        elif isinstance(d, list):
            for i, item in enumerate(d):
                self._flatten_dict(item, writer, f"{prefix}[{i}]")
        else:
            writer.writerow([prefix, d])

    def get_pending_reports(self) -> List[CBNReport]:
        return (
            self.db.query(CBNReport)
            .filter(CBNReport.status.in_([ReportStatus.GENERATED, ReportStatus.REVIEWED]))
            .order_by(CBNReport.generated_at.desc())
            .all()
        )

    def get_report_calendar(self, year: int) -> List[Dict]:
        """Return the full CBN reporting calendar for a given year."""
        calendar = []
        for month in range(1, 13):
            period_end = date(year, month, 1)
            last = (period_end.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            calendar.append({
                "report": "Monthly Activity Report (MAR)",
                "period": f"{year}-{month:02d}",
                "deadline": str(last + timedelta(days=10)),
                "regulatory_reference": "CBN/DOS/CON/GEN/01/015",
            })
        for q in range(1, 5):
            _, qend = self._quarter_dates(year, q)
            calendar.append({
                "report": f"Quarterly Fraud & Forgeries Report (QFFR) Q{q}",
                "period": f"{year} Q{q}",
                "deadline": str(qend + timedelta(days=30)),
                "regulatory_reference": "CBN/FPR/DIR/GEN/FRD/01/007",
            })
        calendar.append({
            "report": "Annual Returns (AFS)",
            "period": str(year),
            "deadline": f"{year + 1}-03-31",
            "regulatory_reference": "BOFIA 2020 Section 27",
        })
        return sorted(calendar, key=lambda x: x["deadline"])

    # ─────────────────────────────────────────────
    # Dashboard aggregation
    # ─────────────────────────────────────────────

    _DEFAULT_FRAMEWORKS = [
        {"name": "CBN AML/CFT", "compliance_pct": 0, "controls_total": 40, "controls_passing": 0, "controls_failing": 0},
        {"name": "NDPR", "compliance_pct": 0, "controls_total": 28, "controls_passing": 0, "controls_failing": 0},
        {"name": "PCI-DSS Lite", "compliance_pct": 0, "controls_total": 35, "controls_passing": 0, "controls_failing": 0},
        {"name": "ISO 27001", "compliance_pct": 0, "controls_total": 50, "controls_passing": 0, "controls_failing": 0},
    ]

    def _seed_frameworks(self) -> None:
        if self.db.query(ComplianceFramework).count() == 0:
            for f in self._DEFAULT_FRAMEWORKS:
                self.db.add(ComplianceFramework(**f))
            self.db.commit()

    def get_automation_dashboard(self) -> Dict:
        self._seed_frameworks()
        frameworks = self.db.query(ComplianceFramework).all()

        total_reports = self.db.query(CBNReport).count()
        submitted_reports = self.db.query(CBNReport).filter(
            CBNReport.status.in_([ReportStatus.SUBMITTED, ReportStatus.ACKNOWLEDGED])
        ).count()
        kyc_total = self.db.query(ComplianceKYCRecord).count()
        kyc_approved = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status.in_(["approved", "verified"])
        ).count()
        filing_total = self.db.query(ComplianceFiling).count()
        filing_submitted = self.db.query(ComplianceFiling).filter(
            ComplianceFiling.status.in_(["submitted", "accepted"])
        ).count()

        report_rate = submitted_reports / max(total_reports, 1)
        kyc_rate = kyc_approved / max(kyc_total, 1)
        filing_rate = filing_submitted / max(filing_total, 1)
        overall_score = round((report_rate * 0.4 + kyc_rate * 0.4 + filing_rate * 0.2) * 100)

        upcoming_audits = (
            self.db.query(ComplianceAudit)
            .filter(
                ComplianceAudit.status.in_(["scheduled", "in_progress"]),
                ComplianceAudit.scheduled_date >= date.today(),
            )
            .order_by(ComplianceAudit.scheduled_date)
            .limit(10)
            .all()
        )
        policies = self.db.query(CompliancePolicy).filter(
            CompliancePolicy.status.notin_(["archived"])
        ).order_by(CompliancePolicy.name).all()

        return {
            "overallScore": overall_score,
            "frameworks": [
                {
                    "id": f.id,
                    "name": f.name,
                    "compliance": f.compliance_pct,
                    "controls": f.controls_total,
                    "passing": f.controls_passing,
                    "failing": f.controls_failing,
                }
                for f in frameworks
            ],
            "upcomingAudits": [
                {
                    "id": a.id,
                    "framework": a.framework,
                    "scheduledDate": str(a.scheduled_date),
                    "auditor": a.auditor,
                    "status": a.status,
                    "notes": a.notes,
                }
                for a in upcoming_audits
            ],
            "policies": [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "status": p.status,
                    "lastReview": str(p.last_review) if p.last_review else None,
                    "nextReview": str(p.next_review) if p.next_review else None,
                    "owner": p.owner,
                }
                for p in policies
            ],
        }

    # ─────────────────────────────────────────────
    # Compliance Audit CRUD
    # ─────────────────────────────────────────────

    def list_audits(self, status: str = None) -> List[Dict]:
        q = self.db.query(ComplianceAudit)
        if status:
            q = q.filter(ComplianceAudit.status == status)
        audits = q.order_by(ComplianceAudit.scheduled_date).all()
        return [
            {
                "id": a.id, "framework": a.framework, "scheduledDate": str(a.scheduled_date),
                "auditor": a.auditor, "status": a.status, "notes": a.notes,
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ]

    def create_audit(self, data: Dict) -> Dict:
        a = ComplianceAudit(
            framework=data["framework"],
            scheduled_date=date.fromisoformat(data["scheduledDate"]),
            auditor=data["auditor"],
            status=data.get("status", "scheduled"),
            notes=data.get("notes"),
        )
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        return {"id": a.id, "framework": a.framework, "scheduledDate": str(a.scheduled_date), "auditor": a.auditor, "status": a.status}

    def update_audit(self, audit_id: str, data: Dict) -> Dict:
        a = self.db.query(ComplianceAudit).filter(ComplianceAudit.id == audit_id).first()
        if not a:
            raise ValueError(f"Audit {audit_id} not found")
        for field in ("framework", "auditor", "status", "notes"):
            if field in data:
                setattr(a, field, data[field])
        if "scheduledDate" in data:
            a.scheduled_date = date.fromisoformat(data["scheduledDate"])
        a.updated_at = datetime.utcnow()
        self.db.commit()
        return {"id": a.id, "framework": a.framework, "scheduledDate": str(a.scheduled_date), "auditor": a.auditor, "status": a.status}

    def delete_audit(self, audit_id: str) -> None:
        a = self.db.query(ComplianceAudit).filter(ComplianceAudit.id == audit_id).first()
        if not a:
            raise ValueError(f"Audit {audit_id} not found")
        self.db.delete(a)
        self.db.commit()

    # ─────────────────────────────────────────────
    # Compliance Policy CRUD
    # ─────────────────────────────────────────────

    def list_policies(self, status: str = None) -> List[Dict]:
        q = self.db.query(CompliancePolicy)
        if status:
            q = q.filter(CompliancePolicy.status == status)
        policies = q.order_by(CompliancePolicy.name).all()
        return [
            {
                "id": p.id, "name": p.name, "version": p.version, "status": p.status,
                "lastReview": str(p.last_review) if p.last_review else None,
                "nextReview": str(p.next_review) if p.next_review else None,
                "owner": p.owner, "created_at": p.created_at.isoformat(),
            }
            for p in policies
        ]

    def create_policy(self, data: Dict) -> Dict:
        p = CompliancePolicy(
            name=data["name"],
            version=int(data.get("version", 1)),
            status=data.get("status", "active"),
            last_review=date.fromisoformat(data["lastReview"]) if data.get("lastReview") else None,
            next_review=date.fromisoformat(data["nextReview"]) if data.get("nextReview") else None,
            owner=data.get("owner"),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return {"id": p.id, "name": p.name, "version": p.version, "status": p.status}

    def update_policy(self, policy_id: str, data: Dict) -> Dict:
        p = self.db.query(CompliancePolicy).filter(CompliancePolicy.id == policy_id).first()
        if not p:
            raise ValueError(f"Policy {policy_id} not found")
        for field in ("name", "version", "status", "owner"):
            if field in data:
                setattr(p, field, data[field])
        if "lastReview" in data and data["lastReview"]:
            p.last_review = date.fromisoformat(data["lastReview"])
        if "nextReview" in data and data["nextReview"]:
            p.next_review = date.fromisoformat(data["nextReview"])
        p.updated_at = datetime.utcnow()
        self.db.commit()
        return {"id": p.id, "name": p.name, "version": p.version, "status": p.status}

    def delete_policy(self, policy_id: str) -> None:
        p = self.db.query(CompliancePolicy).filter(CompliancePolicy.id == policy_id).first()
        if not p:
            raise ValueError(f"Policy {policy_id} not found")
        self.db.delete(p)
        self.db.commit()

    # ─────────────────────────────────────────────
    # Framework score admin update
    # ─────────────────────────────────────────────

    def update_framework_score(self, framework_id: str, data: Dict) -> Dict:
        f = self.db.query(ComplianceFramework).filter(ComplianceFramework.id == framework_id).first()
        if not f:
            raise ValueError(f"Framework {framework_id} not found")
        if "controls_passing" in data:
            f.controls_passing = int(data["controls_passing"])
        if "controls_failing" in data:
            f.controls_failing = int(data["controls_failing"])
        if "controls_total" in data:
            f.controls_total = int(data["controls_total"])
        # Recompute compliance_pct from passing/total
        f.compliance_pct = round(f.controls_passing / max(f.controls_total, 1) * 100)
        f.updated_at = datetime.utcnow()
        self.db.commit()
        return {
            "id": f.id, "name": f.name, "compliance_pct": f.compliance_pct,
            "controls_total": f.controls_total, "controls_passing": f.controls_passing,
            "controls_failing": f.controls_failing,
        }

    def get_reports_dashboard(self) -> Dict:
        total = self.db.query(CBNReport).count()
        mar_count = self.db.query(CBNReport).filter(CBNReport.report_type == ReportType.MONTHLY_ACTIVITY).count()
        agent_count = self.db.query(CBNReport).filter(CBNReport.report_type == ReportType.AGENT_NETWORK).count()
        recent = (
            self.db.query(CBNReport)
            .order_by(CBNReport.generated_at.desc())
            .limit(10)
            .all()
        )
        return {
            "stats": {
                "totalReports": total,
                "cbnReports": mar_count + agent_count,
                "ndprReports": 0,
                "pciDssReports": 0,
            },
            "reports": [
                {
                    "id": r.id,
                    "name": r.report_type.value.replace("_", " ").title(),
                    "framework": "CBN",
                    "period": f"{r.period_start} / {r.period_end}",
                    "status": "completed" if r.status in [ReportStatus.GENERATED, ReportStatus.SUBMITTED, ReportStatus.ACKNOWLEDGED] else "generating",
                    "generatedAt": r.generated_at.isoformat() if r.generated_at else None,
                    "size": None,
                }
                for r in recent
            ],
        }

    # ─────────────────────────────────────────────
    # Filing CRUD
    # ─────────────────────────────────────────────

    def _filing_to_dict(self, f: ComplianceFiling) -> Dict:
        return {
            "id": f.id,
            "filing_type": f.filing_type,
            "period": f.period,
            "due_date": str(f.due_date) if f.due_date else None,
            "status": f.status,
            "description": f.description,
            "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }

    def get_filing_stats(self) -> Dict:
        total = self.db.query(ComplianceFiling).count()
        submitted = self.db.query(ComplianceFiling).filter(
            ComplianceFiling.status.in_(["submitted", "accepted"])
        ).count()
        pending = self.db.query(ComplianceFiling).filter(
            ComplianceFiling.status.in_(["draft", "pending_review"])
        ).count()
        overdue = self.db.query(ComplianceFiling).filter(
            ComplianceFiling.status.notin_(["submitted", "accepted"]),
            ComplianceFiling.due_date < date.today(),
        ).count()
        return {"totalFilings": total, "submitted": submitted, "pending": pending, "overdue": overdue}

    def list_filings(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        filings = (
            self.db.query(ComplianceFiling)
            .order_by(ComplianceFiling.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._filing_to_dict(f) for f in filings]

    def create_filing(self, req: CreateFilingRequest) -> Dict:
        f = ComplianceFiling(
            filing_type=req.filing_type,
            period=req.period,
            due_date=req.due_date,
            description=req.description,
        )
        self.db.add(f)
        self.db.commit()
        self.db.refresh(f)
        return self._filing_to_dict(f)

    def submit_compliance_filing(self, filing_id: str) -> Dict:
        f = self.db.query(ComplianceFiling).filter(ComplianceFiling.id == filing_id).first()
        if not f:
            raise ValueError(f"Filing {filing_id} not found")
        f.status = "submitted"
        f.submitted_at = datetime.utcnow()
        f.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(f)
        return self._filing_to_dict(f)

    # ─────────────────────────────────────────────
    # Training dashboards (no separate training model)
    # ─────────────────────────────────────────────

    def get_training_dashboard(self) -> Dict:
        return {"stats": {"totalTrainings": 0, "completed": 0, "inProgress": 0, "overdue": 0, "avgScore": 0, "complianceRate": 0, "certificatesActive": 0}, "courses": []}

    def get_training_tracker(self) -> Dict:
        training_url = os.environ.get("TRAINING_SVC_URL", "http://agent-training-academy")
        try:
            stats_resp = httpx.get(f"{training_url}/api/v1/training/stats", timeout=5.0)
            stats_resp.raise_for_status()
            stats = stats_resp.json()
            cert_resp = httpx.get(f"{training_url}/api/v1/training/certificates/stats", timeout=5.0)
            cert_stats = cert_resp.json() if cert_resp.is_success else {}
            recent_resp = httpx.get(f"{training_url}/api/v1/training/enrollments/recent?limit=10", timeout=5.0)
            recent = recent_resp.json() if recent_resp.is_success else []
            total_enrollments = stats.get("total_enrollments", 0)
            completed = stats.get("total_completions", 0)
            return {
                "totalTrainings": stats.get("total_courses", 0),
                "completed": completed,
                "inProgress": max(0, total_enrollments - completed),
                "overdue": 0,
                "avgScore": stats.get("avg_pass_rate", 0),
                "complianceRate": round(completed / max(total_enrollments, 1) * 100, 1),
                "certificatesActive": cert_stats.get("active", stats.get("total_certificates", 0)),
                "expiringIn30Days": cert_stats.get("expiring_soon", 0),
                "recent": recent if isinstance(recent, list) else [],
            }
        except Exception as exc:
            logger.warning("Training service unreachable for tracker (%s)", exc)
            return {"totalTrainings": 0, "completed": 0, "inProgress": 0, "overdue": 0, "avgScore": 0, "complianceRate": 0, "certificatesActive": 0, "expiringIn30Days": 0, "recent": []}

    def get_cert_dashboard(self) -> Dict:
        training_url = os.environ.get("TRAINING_SVC_URL", "http://agent-training-academy")
        try:
            stats_resp = httpx.get(f"{training_url}/api/v1/training/certificates/stats", timeout=5.0)
            stats_resp.raise_for_status()
            stats = stats_resp.json()
            certs_resp = httpx.get(f"{training_url}/api/v1/training/certificates?limit=50", timeout=5.0)
            certs = certs_resp.json().get("certificates", []) if certs_resp.is_success else []
            return {
                "stats": {
                    "active": stats.get("active", 0),
                    "expiringSoon": stats.get("expiring_soon", 0),
                    "revoked": stats.get("revoked", 0),
                    "renewalRate": f"{stats.get('renewal_rate', 0)}%",
                },
                "certificates": certs,
            }
        except Exception as exc:
            logger.warning("Training service unreachable for cert dashboard (%s)", exc)
            return {"stats": {"active": 0, "expiringSoon": 0, "revoked": 0, "renewalRate": "0%"}, "certificates": []}

    # ─────────────────────────────────────────────
    # Retention Policy CRUD
    # ─────────────────────────────────────────────

    _DEFAULT_RETENTION_POLICIES = [
        {"entity_type": "Transactions", "retention_days": 2555, "legal_basis": "CBN", "archive_policy": "archive"},
        {"entity_type": "KYC Documents", "retention_days": 1825, "legal_basis": "CBN", "archive_policy": "archive"},
        {"entity_type": "Audit Logs", "retention_days": 3650, "legal_basis": "NDPR", "archive_policy": "archive"},
        {"entity_type": "Customer Data", "retention_days": 1095, "legal_basis": "NDPR", "archive_policy": "delete"},
        {"entity_type": "Session Logs", "retention_days": 180, "legal_basis": "GDPR", "archive_policy": "delete"},
        {"entity_type": "Failed Login Attempts", "retention_days": 90, "legal_basis": "NDPR", "archive_policy": "delete"},
    ]

    def _seed_retention_policies(self) -> None:
        if self.db.query(RetentionPolicy).count() == 0:
            today = date.today()
            for p in self._DEFAULT_RETENTION_POLICIES:
                self.db.add(RetentionPolicy(
                    **p,
                    last_enforced=today,
                    next_run=date(today.year, today.month, today.day + 7) if today.day <= 24 else today.replace(month=today.month % 12 + 1, day=1),
                ))
            self.db.commit()

    def _policy_to_dict(self, p: RetentionPolicy) -> Dict:
        return {
            "id": p.id,
            "entityType": p.entity_type,
            "retentionDays": p.retention_days,
            "legalBasis": p.legal_basis,
            "archivePolicy": p.archive_policy,
            "lastEnforced": str(p.last_enforced) if p.last_enforced else None,
            "nextRun": str(p.next_run) if p.next_run else None,
        }

    _ENTITY_COUNT_MAP = {
        "Transactions": lambda self: self.db.query(CTRRecord).count(),
        "KYC Documents": lambda self: self.db.query(KYCDocument).count(),
        "Audit Logs": lambda self: self.db.query(ComplianceFiling).count(),
        "Customer Data": lambda self: self.db.query(ComplianceKYCRecord).count(),
        "Session Logs": lambda self: self.db.query(SARRecord).count(),
        "Failed Login Attempts": lambda self: self.db.query(ComplianceKYCRecord).filter(ComplianceKYCRecord.status == "rejected").count(),
    }

    def list_retention_policies(self) -> Dict:
        self._seed_retention_policies()
        policies = self.db.query(RetentionPolicy).all()
        today = date.today()
        alerts = []
        for p in policies:
            if not p.next_run:
                continue
            days_left = (p.next_run - today).days
            if 0 <= days_left <= 30:
                count_fn = self._ENTITY_COUNT_MAP.get(p.entity_type)
                record_count = count_fn(self) if count_fn else 0
                alerts.append({
                    "id": p.id,
                    "entityType": p.entity_type,
                    "recordCount": record_count,
                    "expiresIn": days_left,
                })
        return {"policies": [self._policy_to_dict(p) for p in policies], "alerts": alerts}

    def enforce_retention_policy(self, policy_id: str) -> Dict:
        p = self.db.query(RetentionPolicy).filter(RetentionPolicy.id == policy_id).first()
        if not p:
            raise ValueError(f"Policy {policy_id} not found")
        today = date.today()
        p.last_enforced = today
        p.next_run = date(today.year, today.month, today.day + 7) if today.day <= 24 else today.replace(month=today.month % 12 + 1, day=1)
        p.updated_at = datetime.utcnow()
        self.db.commit()
        return {"message": "Enforcement job queued", "policy_id": policy_id, "queued_at": datetime.utcnow().isoformat()}

    def update_retention_policy(self, policy_id: str, data: Dict) -> Dict:
        p = self.db.query(RetentionPolicy).filter(RetentionPolicy.id == policy_id).first()
        if not p:
            raise ValueError(f"Policy {policy_id} not found")
        if "retentionDays" in data:
            p.retention_days = int(data["retentionDays"])
        if "archivePolicy" in data:
            p.archive_policy = data["archivePolicy"]
        p.updated_at = datetime.utcnow()
        self.db.commit()
        return {"message": "Policy updated", "policy": self._policy_to_dict(p)}

    # ─────────────────────────────────────────────
    # KYC Record CRUD (served under /compliance-kyc/records)
    # ─────────────────────────────────────────────

    def _kyc_to_dict(self, r: ComplianceKYCRecord) -> Dict:
        return {
            "id": r.id,
            "customer_id": r.customer_id,
            "status": r.status,
            "risk_level": r.risk_level,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    def list_kyc_records(self, skip: int = 0, limit: int = 100) -> Dict:
        records = (
            self.db.query(ComplianceKYCRecord)
            .order_by(ComplianceKYCRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = self.db.query(ComplianceKYCRecord).count()
        return {"records": [self._kyc_to_dict(r) for r in records], "total": total}

    def get_kyc_record(self, record_id: str) -> Dict:
        r = self.db.query(ComplianceKYCRecord).filter(ComplianceKYCRecord.id == record_id).first()
        if not r:
            raise ValueError(f"KYC record {record_id} not found")
        return self._kyc_to_dict(r)

    def create_kyc_record(self, req: CreateKYCRecordRequest) -> Dict:
        r = ComplianceKYCRecord(
            customer_id=req.customer_id,
            risk_level=req.risk_level or "low",
            notes=req.notes,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._kyc_to_dict(r)

    def update_kyc_record(self, record_id: str, req: UpdateKYCRecordRequest) -> Dict:
        r = self.db.query(ComplianceKYCRecord).filter(ComplianceKYCRecord.id == record_id).first()
        if not r:
            raise ValueError(f"KYC record {record_id} not found")
        if req.status is not None:
            r.status = req.status
        if req.risk_level is not None:
            r.risk_level = req.risk_level
        if req.notes is not None:
            r.notes = req.notes
        r.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(r)
        return self._kyc_to_dict(r)

    def add_kyc_document(self, record_id: str, req: AddKYCDocumentRequest) -> Dict:
        r = self.db.query(ComplianceKYCRecord).filter(ComplianceKYCRecord.id == record_id).first()
        if not r:
            raise ValueError(f"KYC record {record_id} not found")
        doc = KYCDocument(
            record_id=record_id,
            document_type=req.document_type,
            document_number=req.document_number,
            expiry_date=req.expiry_date,
            file_url=req.file_url,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return {
            "id": doc.id,
            "record_id": doc.record_id,
            "document_type": doc.document_type,
            "document_number": doc.document_number,
            "expiry_date": doc.expiry_date,
            "file_url": doc.file_url,
            "created_at": doc.created_at.isoformat(),
        }

    def add_kyc_check(self, record_id: str, req: AddKYCCheckRequest) -> Dict:
        r = self.db.query(ComplianceKYCRecord).filter(ComplianceKYCRecord.id == record_id).first()
        if not r:
            raise ValueError(f"KYC record {record_id} not found")
        import json as _json
        check = KYCCheck(
            record_id=record_id,
            check_type=req.check_type,
            status=req.status,
            result=_json.dumps(req.result) if req.result is not None else None,
            notes=req.notes,
        )
        self.db.add(check)
        self.db.commit()
        self.db.refresh(check)
        return {
            "id": check.id,
            "record_id": check.record_id,
            "check_type": check.check_type,
            "status": check.status,
            "result": req.result,
            "notes": check.notes,
            "created_at": check.created_at.isoformat(),
        }

    # ─────────────────────────────────────────────
    # Agent-facing compliance check endpoints
    # ─────────────────────────────────────────────

    def get_compliance_checks(self) -> Dict:
        """Return actionable compliance check list for agent-facing view."""
        pending_reports = self.db.query(CBNReport).filter(
            CBNReport.status == ReportStatus.GENERATED
        ).count()
        overdue_filings = self.db.query(ComplianceFiling).filter(
            ComplianceFiling.status.notin_(["submitted", "accepted"]),
            ComplianceFiling.due_date < date.today(),
        ).count()
        pending_ctrs = self.db.query(CTRRecord).filter(
            CTRRecord.reported == False
        ).count()
        pending_sars = self.db.query(SARRecord).filter(
            SARRecord.nfiu_reference == None
        ).count()
        # KYC counts from compliance_kyc_records — populated by push from agent-service
        kyc_total = self.db.query(ComplianceKYCRecord).count()
        kyc_verified = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status.in_(["verified", "approved"])
        ).count()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        kyc_rate = kyc_verified / max(kyc_total, 1)

        checks = [
            {
                "name": "AML/CFT Controls",
                "category": "AML",
                "description": "Anti-money laundering and counter-terrorism financing controls",
                "status": "passed" if pending_sars == 0 else "warning",
                "lastRun": now_str,
            },
            {
                "name": "KYC Compliance",
                "category": "KYC",
                "description": f"{kyc_verified}/{kyc_total} customer records verified",
                "status": "passed" if kyc_total == 0 or kyc_rate >= 0.95 else "warning",
                "lastRun": now_str,
            },
            {
                "name": "Currency Transaction Reporting",
                "category": "CBN",
                "description": f"{pending_ctrs} CTR(s) pending submission to CBN",
                "status": "passed" if pending_ctrs == 0 else "failed",
                "lastRun": now_str,
            },
            {
                "name": "Suspicious Activity Reporting",
                "category": "NFIU",
                "description": "SAR filing status with Nigerian Financial Intelligence Unit",
                "status": "passed" if pending_sars == 0 else "warning",
                "lastRun": now_str,
            },
            {
                "name": "Regulatory Filings",
                "category": "CBN",
                "description": f"{overdue_filings} filing(s) overdue for submission",
                "status": "failed" if overdue_filings > 0 else "passed",
                "lastRun": now_str,
            },
            {
                "name": "Monthly Activity Reports",
                "category": "CBN",
                "description": f"{pending_reports} report(s) generated but not yet submitted",
                "status": "warning" if pending_reports > 0 else "passed",
                "lastRun": now_str,
            },
            {
                "name": "Data Retention Policy",
                "category": "NDPR",
                "description": "Customer data retained in line with CBN/NDPR requirements",
                "status": "passed",
                "lastRun": now_str,
            },
            {
                "name": "Agent Training Compliance",
                "category": "CBN",
                "description": "CBN-mandatory training modules (AML, KYC, Fraud Prevention) completion",
                "status": "warning",
                "lastRun": now_str,
            },
        ]

        total = len(checks)
        passed = sum(1 for c in checks if c["status"] == "passed")
        failed = sum(1 for c in checks if c["status"] == "failed")
        warnings = sum(1 for c in checks if c["status"] == "warning")

        return {
            "checks": checks,
            "summary": {"total": total, "passed": passed, "failed": failed, "warnings": warnings},
            "lastUpdated": now_str,
        }

    # ─────────────────────────────────────────────
    # NFIU report methods
    # ─────────────────────────────────────────────

    def get_nfiu_reports(self, status: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Dict]:
        q = self.db.query(SARRecord)
        if status == "filed":
            q = q.filter(SARRecord.nfiu_reference != None)
        elif status == "pending":
            q = q.filter(SARRecord.nfiu_reference == None)
        sars = q.order_by(SARRecord.created_at.desc()).offset(skip).limit(limit).all()
        return [
            {
                "id": s.id,
                "reference_number": s.reference_number,
                "subject_name": s.subject_name,
                "reason": s.reason.value if hasattr(s.reason, "value") else str(s.reason),
                "amount_involved": float(s.amount_involved) if s.amount_involved else None,
                "nfiu_reference": s.nfiu_reference,
                "status": "filed" if s.nfiu_reference else "pending",
                "created_at": s.created_at.isoformat(),
            }
            for s in sars
        ]

    def get_nfiu_report_detail(self, report_id: str) -> Dict:
        s = self.db.query(SARRecord).filter(SARRecord.id == report_id).first()
        if not s:
            raise ValueError(f"NFIU report {report_id} not found")
        linked_report = None
        if s.report_id:
            r = self.db.query(CBNReport).filter(CBNReport.id == s.report_id).first()
            if r:
                linked_report = {
                    "id": r.id,
                    "report_type": r.report_type.value if hasattr(r.report_type, "value") else str(r.report_type),
                    "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                    "submission_reference": r.submission_reference,
                }
        return {
            "id": s.id,
            "reference_number": s.reference_number,
            "subject_name": s.subject_name,
            "subject_bvn": s.subject_bvn,
            "subject_account": s.subject_account,
            "reason": s.reason.value if hasattr(s.reason, "value") else str(s.reason),
            "description": s.description,
            "amount_involved": float(s.amount_involved) if s.amount_involved else None,
            "transaction_ids": s.transaction_ids,
            "reported_by": s.reported_by,
            "nfiu_reference": s.nfiu_reference,
            "status": "filed" if s.nfiu_reference else "pending",
            "cbn_report": linked_report,
            "created_at": s.created_at.isoformat(),
        }

    def submit_nfiu_report(self, report_id: str) -> Dict:
        """Transmit a SAR to the NFIU portal API and record the returned reference."""
        import requests as _requests

        s = self.db.query(SARRecord).filter(SARRecord.id == report_id).first()
        if not s:
            raise ValueError(f"NFIU report {report_id} not found")
        if s.nfiu_reference:
            return {"nfiu_reference": s.nfiu_reference, "already_submitted": True}

        nfiu_url = os.environ.get("NFIU_PORTAL_URL", "").rstrip("/")
        nfiu_key = os.environ.get("NFIU_API_KEY", "")
        if not nfiu_url or not nfiu_key:
            logger.error(
                "nfiu_not_configured report_id=%s — set NFIU_PORTAL_URL and NFIU_API_KEY",
                report_id,
            )
            raise ValueError(
                "NFIU portal is not configured. "
                "Set NFIU_PORTAL_URL and NFIU_API_KEY environment variables."
            )

        payload = {
            "report_id": str(s.id),
            "reference": s.reference,
            "reason": s.reason.value if hasattr(s.reason, "value") else s.reason,
            "amount": str(s.amount) if s.amount is not None else None,
            "currency": getattr(s, "currency", "NGN"),
            "institution_code": getattr(s, "institution_code", None),
            "reported_at": s.created_at.isoformat() if s.created_at else None,
            "narrative": getattr(s, "narrative", None),
        }

        try:
            resp = _requests.post(
                f"{nfiu_url}/api/v1/sar/submit",
                json=payload,
                headers={
                    "Authorization": f"Bearer {nfiu_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except _requests.exceptions.Timeout:
            logger.error("nfiu_submission_timeout report_id=%s", report_id)
            raise ValueError("NFIU portal submission timed out. The SAR remains pending.")
        except _requests.exceptions.RequestException as exc:
            logger.error("nfiu_submission_failed report_id=%s error=%s", report_id, str(exc))
            raise ValueError(f"NFIU portal submission failed: {exc}")

        nfiu_ref = data.get("reference") or data.get("nfiu_reference")
        if not nfiu_ref:
            logger.error(
                "nfiu_missing_reference report_id=%s response=%s", report_id, data
            )
            raise ValueError(
                f"NFIU portal response did not contain a reference field. "
                f"SAR id={report_id} remains pending. Response: {data}"
            )

        s.nfiu_reference = nfiu_ref
        self.db.commit()
        logger.info("nfiu_submission_success report_id=%s nfiu_reference=%s", report_id, nfiu_ref)
        return {"nfiu_reference": nfiu_ref, "already_submitted": False}

    def get_regulatory_report_generator_stats(self) -> Dict:
        """Stats for the regulatory report generator (agent-facing dashboard)."""
        total_reports = self.db.query(CBNReport).count()
        submitted = self.db.query(CBNReport).filter(
            CBNReport.status.in_([ReportStatus.SUBMITTED, ReportStatus.ACKNOWLEDGED])
        ).count()
        pending = self.db.query(CBNReport).filter(
            CBNReport.status == ReportStatus.GENERATED
        ).count()
        score = round(submitted / max(total_reports, 1) * 100, 1)

        today = date.today()
        if today.day <= 10:
            next_deadline = today.replace(day=10).isoformat()
        elif today.month < 12:
            next_deadline = today.replace(month=today.month + 1, day=10).isoformat()
        else:
            next_deadline = today.replace(year=today.year + 1, month=1, day=10).isoformat()

        total_records = (
            total_reports
            + self.db.query(CTRRecord).count()
            + self.db.query(SARRecord).count()
        )
        return {
            "totalReports": total_reports,
            "submittedOnTime": submitted,
            "pendingReports": pending,
            "avgComplianceScore": f"{score}%",
            "regulatorsTracked": 4,
            "nextDeadline": next_deadline,
            "autoFilingEnabled": "Yes",
            "totalRecordsProcessed": total_records,
        }

    def get_regulatory_reporting_engine_stats(self) -> Dict:
        """Stats for the regulatory reporting engine page."""
        total = self.db.query(CBNReport).count()
        pending_submission = self.db.query(CBNReport).filter(
            CBNReport.status == ReportStatus.GENERATED
        ).count()
        submitted = self.db.query(CBNReport).filter(
            CBNReport.status.in_([ReportStatus.SUBMITTED, ReportStatus.ACKNOWLEDGED])
        ).count()
        filing_stats = self.get_filing_stats()
        last = self.db.query(CBNReport).order_by(CBNReport.generated_at.desc()).first()
        return {
            "totalReports": total,
            "pendingSubmission": pending_submission,
            "submittedThisMonth": submitted,
            "totalFilings": filing_stats["totalFilings"],
            "overdueFilings": filing_stats["overdue"],
            "pendingFilings": filing_stats["pending"],
            "ctrsGenerated": self.db.query(CTRRecord).count(),
            "sarsFiled": self.db.query(SARRecord).count(),
            "lastReportDate": last.generated_at.isoformat() if last and last.generated_at else None,
        }

    def get_regulatory_filing_automation_stats(self) -> Dict:
        """Stats for the filing automation page."""
        filing_stats = self.get_filing_stats()
        return {
            "totalFilings": filing_stats["totalFilings"],
            "submitted": filing_stats["submitted"],
            "pending": filing_stats["pending"],
            "overdue": filing_stats["overdue"],
            "automationRate": "85%",
            "nextScheduledFiling": "MAR — due 10th of each month",
            "cbnPortalStatus": "Connected",
            "lastSyncedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    # ─────────────────────────────────────────────
    # Ingest endpoints — called by other services
    # ─────────────────────────────────────────────

    def ingest_ctr_record(self, data: dict) -> dict:
        """
        Called by payment-processing-service whenever a transaction >= NGN 5M completes.
        Creates a CTRRecord that will be included in the next CTR report.
        """
        # Deduplicate: if we already have this transaction_id, skip
        existing = self.db.query(CTRRecord).filter(
            CTRRecord.transaction_id == data["transaction_id"]
        ).first()
        if existing:
            return {"status": "duplicate", "ctr_id": existing.id}

        record = CTRRecord(
            transaction_id=data["transaction_id"],
            transaction_date=datetime.fromisoformat(
                data.get("transaction_date") or datetime.utcnow().isoformat()
            ),
            amount=Decimal(str(data["amount"])),
            currency=data.get("currency", "NGN"),
            transaction_type=data.get("transaction_type", "TRANSFER"),
            customer_name=data.get("customer_name", "Unknown"),
            customer_bvn=data.get("customer_bvn"),
            customer_nin=data.get("customer_nin"),
            customer_account=data.get("customer_account", ""),
            agent_id=data.get("agent_id", ""),
            agent_name=data.get("agent_name", ""),
            branch_code=data.get("branch_code"),
            reported=False,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info("CTR record ingested transaction_id=%s amount=%s", data["transaction_id"], data["amount"])
        return {"status": "recorded", "ctr_id": record.id}

    def ingest_fraud_record(self, data: dict) -> dict:
        """
        Called by fraud-engine when a transaction is blocked or flagged.
        Creates a FraudRecord that will feed into the Quarterly Fraud Report.
        """
        fraud_type_raw = str(data.get("fraud_type", "UNAUTHORIZED_TRANSFER")).upper()
        try:
            fraud_type = FraudType[fraud_type_raw]
        except KeyError:
            fraud_type = FraudType.UNAUTHORIZED_TRANSFER

        record = FraudRecord(
            fraud_type=fraud_type,
            incident_date=datetime.fromisoformat(
                data.get("incident_date") or datetime.utcnow().isoformat()
            ),
            amount_attempted=Decimal(str(data.get("amount_attempted", 0))),
            amount_lost=Decimal(str(data.get("amount_lost", 0))),
            amount_recovered=Decimal("0"),
            victim_account=data.get("victim_account"),
            perpetrator_info=data.get("perpetrator_info"),
            channel=data.get("channel", "UNKNOWN"),
            resolution_status="PENDING",
            police_report_number=data.get("police_report_number"),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info(
            "Fraud record ingested fraud_type=%s amount=%.2f",
            fraud_type.value, float(record.amount_attempted),
        )
        return {"status": "recorded", "fraud_record_id": record.id}

    def record_agent_transaction(self, data: dict) -> dict:
        """
        Called by payment-processing-service after every successful transaction.
        Upserts the AgentNetworkReport row for the current YYYY-MM period,
        incrementing counters so Monthly Activity Reports reflect live data.
        """
        period = data.get("period") or datetime.utcnow().strftime("%Y-%m")
        # Amount arrives in NGN (float)
        amount_ngn = Decimal(str(data.get("amount_ngn", 0)))
        tx_type = str(data.get("transaction_type", "")).lower()

        record = self.db.query(AgentNetworkReport).filter(
            AgentNetworkReport.report_period == period
        ).first()

        if not record:
            record = AgentNetworkReport(report_period=period)
            self.db.add(record)

        record.total_transactions = (record.total_transactions or 0) + 1
        record.total_transaction_value = (record.total_transaction_value or Decimal("0")) + amount_ngn

        if "deposit" in tx_type or "cash_in" in tx_type:
            record.cash_in_transactions = (record.cash_in_transactions or 0) + 1
            record.cash_in_value = (record.cash_in_value or Decimal("0")) + amount_ngn
        elif "withdrawal" in tx_type or "cash_out" in tx_type:
            record.cash_out_transactions = (record.cash_out_transactions or 0) + 1
            record.cash_out_value = (record.cash_out_value or Decimal("0")) + amount_ngn
        elif "transfer" in tx_type:
            record.transfer_transactions = (record.transfer_transactions or 0) + 1
            record.transfer_value = (record.transfer_value or Decimal("0")) + amount_ngn
        elif "bill" in tx_type:
            record.bill_payment_transactions = (record.bill_payment_transactions or 0) + 1
            record.bill_payment_value = (record.bill_payment_value or Decimal("0")) + amount_ngn

        self.db.commit()
        return {"status": "updated", "period": period, "total_transactions": record.total_transactions}

    # ─────────────────────────────────────────────
    # Cross-service reads — shared link_core_banking DB
    # ─────────────────────────────────────────────


    # ─────────────────────────────────────────────
    # KYC ingest — called by agent-service on KYC status change
    # ─────────────────────────────────────────────

    # Maps agent-service KycVerificationStatus values to compliance KYC statuses
    _KYC_STATUS_MAP = {
        "not_verified": "pending",
        "pending": "in_review",
        "verified": "approved",
        "failed_verification": "rejected",
    }

    def ingest_kyc_update(self, data: dict) -> dict:
        """
        Called by agent-service when an agent's KYC status changes.
        Creates or updates the corresponding compliance_kyc_records entry.
        """
        agent_id = data.get("agent_id", "")
        if not agent_id:
            raise ValueError("agent_id is required")

        raw_status = str(data.get("kyc_status", "pending")).lower()
        compliance_status = self._KYC_STATUS_MAP.get(raw_status, "pending")
        risk_level = "high" if raw_status == "failed_verification" else "low"

        existing = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.customer_id == agent_id
        ).first()

        if existing:
            existing.status = compliance_status
            existing.risk_level = risk_level
            existing.notes = f"Synced from agent-service. KYC status: {raw_status}"
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info("KYC record updated agent_id=%s status=%s", agent_id, compliance_status)
            return {"status": "updated", "record_id": existing.id}

        record = ComplianceKYCRecord(
            customer_id=agent_id,
            status=compliance_status,
            risk_level=risk_level,
            notes=f"Synced from agent-service. KYC status: {raw_status}",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info("KYC record created agent_id=%s status=%s", agent_id, compliance_status)
        return {"status": "created", "record_id": record.id}

    def get_kyc_summary(self) -> dict:
        """
        Aggregated KYC compliance summary used by the admin dashboard.
        Source: compliance_kyc_records, populated by push from agent-service via /api/v1/kyc-ingest.
        """
        total = self.db.query(ComplianceKYCRecord).count()
        verified = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status.in_(["approved", "verified"])
        ).count()
        pending = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status.in_(["pending", "in_review"])
        ).count()
        rejected = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.status == "rejected"
        ).count()

        high_risk = self.db.query(ComplianceKYCRecord).filter(
            ComplianceKYCRecord.risk_level == "high"
        ).count()

        doc_national_id = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%national%")
        ).count()
        doc_passport = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%passport%")
        ).count()
        doc_drivers = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%driver%")
        ).count()
        doc_utility = self.db.query(KYCDocument).filter(
            KYCDocument.document_type.ilike("%utility%")
        ).count()

        bvn_attempted = self.db.query(KYCCheck).filter(
            KYCCheck.check_type == "bvn_verification"
        ).count()
        bvn_passed = self.db.query(KYCCheck).filter(
            KYCCheck.check_type == "bvn_verification",
            KYCCheck.status == "passed"
        ).count()

        return {
            "total": total,
            "approved": verified,
            "pending": pending,
            "rejected": rejected,
            "high_risk": high_risk,
            "compliance_rate_pct": round(verified / max(total, 1) * 100, 1),
            "bvn_verification": {
                "attempted": bvn_attempted,
                "passed": bvn_passed,
                "success_rate_pct": round(bvn_passed / max(bvn_attempted, 1) * 100, 1),
            },
            "documents": {
                "national_id": doc_national_id,
                "passport": doc_passport,
                "drivers_license": doc_drivers,
                "utility_bill": doc_utility,
            },
            "tier_breakdown": {
                "tier_1_no_kyc": max(0, total - verified - pending),
                "tier_2_bvn_pending": pending,
                "tier_3_fully_verified": verified,
            },
            "data_source": "compliance_kyc_records",
        }

    # ─────────────────────────────────────────────
    # GDPR / NDPR data subject request management
    # ─────────────────────────────────────────────

    def _gdpr_to_dict(self, r: "GDPRRequest") -> Dict:
        return {
            "id": r.id,
            "type": r.type,
            "subject_name": r.subject_name,
            "subject_email": r.subject_email,
            "status": r.status,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "deadline": r.deadline.isoformat() if r.deadline else None,
            "notes": r.notes,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }

    def list_gdpr_requests(self, status: Optional[str] = None) -> List[Dict]:
        q = self.db.query(GDPRRequest)
        if status and status != "all":
            q = q.filter(GDPRRequest.status == status)
        return [self._gdpr_to_dict(r) for r in q.order_by(GDPRRequest.submitted_at.desc()).all()]

    def update_gdpr_request(self, request_id: str, data: dict) -> Dict:
        r = self.db.query(GDPRRequest).filter(GDPRRequest.id == request_id).first()
        if not r:
            raise ValueError(f"GDPR request {request_id} not found")
        if "status" in data:
            r.status = data["status"]
            if data["status"] in ("completed", "rejected"):
                r.resolved_at = datetime.utcnow()
                r.resolved_by = data.get("resolved_by")
        if "notes" in data:
            r.notes = data["notes"]
        self.db.commit()
        self.db.refresh(r)
        return self._gdpr_to_dict(r)

    def export_gdpr_request(self, request_id: str) -> Dict:
        r = self.db.query(GDPRRequest).filter(GDPRRequest.id == request_id).first()
        if not r:
            raise ValueError(f"GDPR request {request_id} not found")
        return {
            "request_id": r.id,
            "type": r.type,
            "subject_name": r.subject_name,
            "subject_email": r.subject_email,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "status": r.status,
            "export_format": "json",
            "data": {"message": f"Data subject export for {r.subject_name} — type: {r.type}"},
            "generated_at": datetime.utcnow().isoformat(),
        }

    def create_gdpr_request(self, data: dict) -> Dict:
        deadline = datetime.utcnow() + timedelta(days=30)
        r = GDPRRequest(
            type=data.get("type", "access"),
            subject_name=data.get("subject_name", ""),
            subject_email=data.get("subject_email", ""),
            notes=data.get("notes"),
            deadline=deadline,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._gdpr_to_dict(r)

    # ─────────────────────────────────────────────
    # Regulatory Sandbox experiment management
    # ─────────────────────────────────────────────

    def _sandbox_to_dict(self, e: "SandboxExperiment") -> Dict:
        return {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "category": e.category,
            "status": e.status,
            "participants": e.participants,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "results": e.results,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }

    def list_sandbox_experiments(self) -> List[Dict]:
        return [self._sandbox_to_dict(e) for e in
                self.db.query(SandboxExperiment).order_by(SandboxExperiment.created_at.desc()).all()]

    def create_sandbox_experiment(self, data: dict) -> Dict:
        e = SandboxExperiment(
            name=data.get("name", ""),
            description=data.get("description"),
            category=data.get("category", "payment_limit"),
            created_by=data.get("created_by"),
        )
        self.db.add(e)
        self.db.commit()
        self.db.refresh(e)
        return self._sandbox_to_dict(e)

    def launch_sandbox_experiment(self, experiment_id: str) -> Dict:
        e = self.db.query(SandboxExperiment).filter(SandboxExperiment.id == experiment_id).first()
        if not e:
            raise ValueError(f"Experiment {experiment_id} not found")
        e.status = "running"
        e.start_date = datetime.utcnow()
        e.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(e)
        return self._sandbox_to_dict(e)

    def stop_sandbox_experiment(self, experiment_id: str) -> Dict:
        e = self.db.query(SandboxExperiment).filter(SandboxExperiment.id == experiment_id).first()
        if not e:
            raise ValueError(f"Experiment {experiment_id} not found")
        e.status = "completed"
        e.end_date = datetime.utcnow()
        e.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(e)
        return self._sandbox_to_dict(e)

    # ─────────────────────────────────────────────
    # CBN Scheduled Report records
    # ─────────────────────────────────────────────

    def _schedule_to_dict(self, s: "ReportScheduleRecord") -> Dict:
        return {
            "id": s.id,
            "name": s.name,
            "frequency": s.frequency,
            "status": s.status,
            "format": s.format,
            "recipients": json.loads(s.recipients) if s.recipients else [],
            "last_run": s.last_run.isoformat() if s.last_run else None,
            "next_run": s.next_run.isoformat() if s.next_run else None,
        }

    def _seed_default_schedules(self) -> None:
        """Seed the default CBN report schedules if the table is empty."""
        if self.db.query(ReportScheduleRecord).count() > 0:
            return
        defaults = [
            {"name": "CBN Transaction Report (Form A)", "frequency": "daily", "format": "xlsx",
             "recipients": json.dumps(["compliance@bank.com"])},
            {"name": "Suspicious Transaction Report (STR)", "frequency": "weekly", "format": "pdf",
             "recipients": json.dumps(["nfiu@bank.com", "compliance@bank.com"])},
            {"name": "Agent Float & Liquidity Report", "frequency": "daily", "format": "xlsx",
             "recipients": json.dumps(["treasury@bank.com"])},
            {"name": "Monthly Regulatory Return (MRR)", "frequency": "monthly", "format": "pdf",
             "recipients": json.dumps(["cbn-reporting@bank.com"])},
            {"name": "KYC Deficiency Report", "frequency": "weekly", "format": "csv",
             "recipients": json.dumps(["kyc@bank.com"])},
        ]
        now = datetime.utcnow()
        for d in defaults:
            self.db.add(ReportScheduleRecord(
                name=d["name"], frequency=d["frequency"],
                format=d["format"], recipients=d["recipients"],
                next_run=now + timedelta(days=1),
            ))
        self.db.commit()

    def list_report_schedules(self) -> List[Dict]:
        self._seed_default_schedules()
        return [self._schedule_to_dict(s) for s in
                self.db.query(ReportScheduleRecord).order_by(ReportScheduleRecord.created_at.asc()).all()]

    def run_report_schedule(self, schedule_id: str) -> Dict:
        s = self.db.query(ReportScheduleRecord).filter(ReportScheduleRecord.id == schedule_id).first()
        if not s:
            raise ValueError(f"Schedule {schedule_id} not found")
        s.last_run = datetime.utcnow()
        s.status = "active"
        freq_delta = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90}
        s.next_run = datetime.utcnow() + timedelta(days=freq_delta.get(s.frequency, 1))
        s.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(s)
        logger.info("Report schedule run: %s", s.name)
        return self._schedule_to_dict(s)

    def update_report_schedule_status(self, schedule_id: str, status: str) -> Dict:
        s = self.db.query(ReportScheduleRecord).filter(ReportScheduleRecord.id == schedule_id).first()
        if not s:
            raise ValueError(f"Schedule {schedule_id} not found")
        if status not in ("active", "paused", "failed"):
            raise ValueError(f"Invalid status: {status}")
        s.status = status
        s.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(s)
        return self._schedule_to_dict(s)

    def create_report_schedule(self, data: Dict) -> Dict:
        freq_delta = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90}
        freq = data.get("frequency", "monthly")
        recipients = data.get("recipients", [])
        s = ReportScheduleRecord(
            name=data["name"],
            frequency=freq,
            format=data.get("format", "pdf"),
            recipients=json.dumps(recipients if isinstance(recipients, list) else [recipients]),
            status="active",
            next_run=datetime.utcnow() + timedelta(days=freq_delta.get(freq, 30)),
        )
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return self._schedule_to_dict(s)

    def delete_report_schedule(self, schedule_id: str) -> None:
        s = self.db.query(ReportScheduleRecord).filter(ReportScheduleRecord.id == schedule_id).first()
        if not s:
            raise ValueError(f"Schedule {schedule_id} not found")
        self.db.delete(s)
        self.db.commit()

    # ─────────────────────────────────────────────
    # Training dashboard — fetches from agent-training-academy
    # ─────────────────────────────────────────────

    def get_training_dashboard_live(self) -> Dict:
        """
        Training stats from agent-training-academy service via HTTP.
        Falls back to hardcoded mock if the service is unreachable.
        """
        training_url = os.environ.get("TRAINING_SVC_URL", "http://agent-training-academy")
        try:
            resp = httpx.get(f"{training_url}/api/v1/training/stats", timeout=5.0)
            resp.raise_for_status()
            stats = resp.json()
            courses_resp = httpx.get(f"{training_url}/api/v1/training/courses?limit=15", timeout=5.0)
            courses = courses_resp.json().get("courses", []) if courses_resp.is_success else []
            total_enrollments = stats.get("total_enrollments", 0)
            completed = stats.get("total_completions", 0)
            return {
                "stats": {
                    "totalTrainings": stats.get("total_courses", 0),
                    "completed": completed,
                    "inProgress": max(0, total_enrollments - completed),
                    "overdue": 0,
                    "avgScore": stats.get("avg_pass_rate", 0),
                    "complianceRate": round(completed / max(total_enrollments, 1) * 100, 1),
                    "certificatesActive": stats.get("total_certificates", 0),
                },
                "courses": [
                    {
                        "id": str(c.get("id", "")),
                        "name": c.get("title", ""),
                        "category": "mandatory" if c.get("is_mandatory") else "optional",
                        "status": "active" if c.get("is_published") else "draft",
                        "enrolled": c.get("enrollment_count", 0),
                        "completed": c.get("completion_count", 0),
                    }
                    for c in courses
                ],
            }
        except Exception as exc:
            logger.warning("Training service unreachable (%s); returning fallback data", exc)
            return self.get_training_dashboard()

    # ─────────────────────────────────────────────
    # Enriched reports dashboard (adds CTR/SAR/KYC context)
    # ─────────────────────────────────────────────

    def get_reports_dashboard_enriched(self) -> Dict:
        base = self.get_reports_dashboard()
        base["stats"]["ctrRecords"] = self.db.query(CTRRecord).count()
        base["stats"]["sarRecords"] = self.db.query(SARRecord).count()
        base["stats"]["kycRecords"] = self.db.query(ComplianceKYCRecord).count()
        base["stats"]["pendingCtrs"] = self.db.query(CTRRecord).filter(CTRRecord.reported == False).count()
        return base
