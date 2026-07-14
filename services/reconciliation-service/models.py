import enum
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Enum, Text, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class ReconciliationStatus(str, enum.Enum):
    BALANCED = "balanced"
    DISCREPANCY = "discrepancy"
    ERROR = "error"

class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"
    id = Column(Integer, primary_key=True, index=True)
    run_type = Column(String(50), nullable=False, index=True)  # float_vs_ledger | settlement_vs_commission | commission_vs_settlement
    status = Column(Enum(ReconciliationStatus), nullable=False, default=ReconciliationStatus.BALANCED)
    total_checked = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    discrepancy_count = Column(Integer, default=0)
    discrepancy_amount = Column(Numeric(18, 2), default=0)
    details = Column(Text, nullable=True)  # JSON string of specific discrepancies
    run_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True)
