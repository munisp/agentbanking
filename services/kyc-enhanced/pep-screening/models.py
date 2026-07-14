import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
    Boolean,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# --- Base and Mixins ---

Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False, doc="Timestamp of creation."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False, doc="Timestamp of last update."
    )

class SoftDeleteMixin:
    """Mixin for soft deletion support."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, doc="Timestamp of deletion (soft delete)."
    )

class AuditMixin:
    """Mixin for audit fields (created_by and updated_by)."""
    created_by: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, doc="User or system that created the record."
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, doc="User or system that last updated the record."
    )

# --- Enums ---

class TransactionStatus(enum.Enum):
    """Status of a monitored transaction."""
    PENDING = "PENDING"
    CLEARED = "CLEARED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"
    REVERSED = "REVERSED"

class AlertStatus(enum.Enum):
    """Status of an alert."""
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    CLOSED_FALSE_POSITIVE = "CLOSED_FALSE_POSITIVE"
    CLOSED_SAR_FILED = "CLOSED_SAR_FILED"
    CLOSED_OTHER = "CLOSED_OTHER"

class RiskLevel(enum.Enum):
    """Calculated risk level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RuleType(enum.Enum):
    """Type of monitoring rule."""
    THRESHOLD = "THRESHOLD"
    BEHAVIORAL = "BEHAVIORAL"
    NETWORK = "NETWORK"
    GEO_FENCE = "GEO_FENCE"

class SARStatus(enum.Enum):
    """Status of a Suspicious Activity Report (SAR)."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"

# --- Models ---

class MonitoredTransaction(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a financial transaction being monitored for suspicious activity.
    This is the core entity that links to all monitoring results.
    """
    __tablename__ = "monitored_transactions"
    __table_args__ = (
        # Ensure the external transaction ID is unique
        UniqueConstraint("external_transaction_id", name="uq_monitored_transaction_external_id"),
        # Index on status for quick filtering
        {"comment": "Stores all transactions subject to AML monitoring."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, doc="Primary key.")
    external_transaction_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, doc="ID from the external system (e.g., core banking)."
    )
    account_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, doc="Account ID involved in the transaction."
    )
    transaction_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="The actual time the transaction occurred."
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False, doc="Transaction amount.")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, doc="Transaction currency (e.g., USD, EUR).")
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False, doc="Type of transaction (e.g., DEPOSIT, WITHDRAWAL, TRANSFER)."
    )
    status: Mapped[TransactionStatus] = mapped_column(
        String(50), nullable=False, default=TransactionStatus.PENDING, doc="Current monitoring status."
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, doc="Additional transaction details as JSON (e.g., counterparty info, location)."
    )

    # Relationships
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="transaction", cascade="all, delete-orphan"
    )
    risk_scores: Mapped[List["RiskScore"]] = relationship(
        "RiskScore", back_populates="transaction", cascade="all, delete-orphan"
    )


class Rule(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Defines the rules used for transaction monitoring.
    """
    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint("name", name="uq_rule_name"),
        CheckConstraint("priority >= 1 AND priority <= 100", name="chk_rule_priority_range"),
        {"comment": "Defines the set of AML monitoring rules."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, doc="Primary key.")
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Unique name of the rule.")
    description: Mapped[str] = mapped_column(Text, nullable=False, doc="Detailed description of the rule logic.")
    rule_type: Mapped[RuleType] = mapped_column(
        String(50), nullable=False, doc="The category of the rule (e.g., THRESHOLD, BEHAVIORAL)."
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, doc="Whether the rule is currently active.")
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, index=True, doc="Execution priority (1=highest, 100=lowest)."
    )
    rule_definition_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, doc="The executable definition of the rule (e.g., a JSON expression or code snippet)."
    )

    # Relationships
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="triggering_rule", cascade="all, delete-orphan"
    )


class Alert(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents an alert generated when a transaction violates a monitoring rule.
    """
    __tablename__ = "alerts"
    __table_args__ = (
        # Index on status and risk_level for analyst filtering
        {"comment": "Stores alerts generated by monitoring rules."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, doc="Primary key.")
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_transactions.id", ondelete="CASCADE"), nullable=False, index=True, doc="Foreign key to the monitored transaction."
    )
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("rules.id", ondelete="RESTRICT"), nullable=False, index=True, doc="Foreign key to the rule that triggered the alert."
    )
    status: Mapped[AlertStatus] = mapped_column(
        String(50), nullable=False, default=AlertStatus.NEW, index=True, doc="Current status of the alert."
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        String(50), nullable=False, default=RiskLevel.MEDIUM, index=True, doc="Calculated risk level of the alert."
    )
    alert_details_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, doc="Detailed context and parameters that triggered the alert."
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, doc="User or team assigned to review the alert."
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Notes on how the alert was resolved."
    )

    # Relationships
    transaction: Mapped["MonitoredTransaction"] = relationship(
        "MonitoredTransaction", back_populates="alerts"
    )
    triggering_rule: Mapped["Rule"] = relationship(
        "Rule", back_populates="alerts"
    )
    sar: Mapped[Optional["SuspiciousActivityReport"]] = relationship(
        "SuspiciousActivityReport", back_populates="alert", uselist=False, cascade="all, delete-orphan"
    )


class RiskScore(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Stores the calculated risk score for a transaction, potentially from multiple models.
    """
    __tablename__ = "risk_scores"
    __table_args__ = (
        # Index on score and model_name for analysis
        {"comment": "Stores risk scores calculated by various models for a transaction."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, doc="Primary key.")
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_transactions.id", ondelete="CASCADE"), nullable=False, index=True, doc="Foreign key to the monitored transaction."
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, doc="Name of the model that generated the score (e.g., 'GNN_Model_v2', 'Tazama_Rules')."
    )
    score: Mapped[float] = mapped_column(
        Float, nullable=False, index=True, doc="The calculated risk score (e.g., 0.0 to 1.0)."
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        String(50), nullable=False, default=RiskLevel.LOW, doc="Categorized risk level based on the score."
    )
    score_details_json: Mapped[dict] = mapped_column(
        JSON, nullable=True, doc="Detailed features and explanations used to derive the score."
    )

    # Relationships
    transaction: Mapped["MonitoredTransaction"] = relationship(
        "MonitoredTransaction", back_populates="risk_scores"
    )


class SuspiciousActivityReport(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a Suspicious Activity Report (SAR) filed based on an alert.
    """
    __tablename__ = "suspicious_activity_reports"
    __table_args__ = (
        # Ensure only one SAR per alert
        UniqueConstraint("alert_id", name="uq_sar_alert_id"),
        {"comment": "Stores Suspicious Activity Reports (SARs) filed with regulators."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, doc="Primary key.")
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="RESTRICT"), nullable=False, index=True, doc="Foreign key to the alert that led to the SAR."
    )
    sar_reference_number: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True, doc="Unique reference number assigned to the SAR."
    )
    filing_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), doc="Date the SAR was officially filed."
    )
    status: Mapped[SARStatus] = mapped_column(
        String(50), nullable=False, default=SARStatus.DRAFT, index=True, doc="Current status of the SAR."
    )
    report_content_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, doc="The full content of the SAR, structured as JSON."
    )
    regulator_feedback: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Feedback received from the regulatory body."
    )

    # Relationships
    alert: Mapped["Alert"] = relationship(
        "Alert", back_populates="sar"
    )

# --- End of Models ---

# Example usage (not part of the schema, but useful for context)
# if __name__ == '__main__':
#     from sqlalchemy import create_engine
#     from sqlalchemy.orm import sessionmaker
#     import os
#
#     # Example setup for a PostgreSQL database
#     DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/transaction_monitoring_db")
#     engine = create_engine(DATABASE_URL)
#
#     # Create tables
#     Base.metadata.create_all(engine)
#
#     print("Database schema created successfully.")
