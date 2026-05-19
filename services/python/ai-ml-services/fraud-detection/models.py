from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column

# --- Base Class ---
class Base(DeclarativeBase):
    pass

# --- Enums ---
import enum
class TransactionStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"

class FraudDecision(enum.Enum):
    SAFE = "SAFE"
    REVIEW = "REVIEW"
    FRAUD = "FRAUD"

class RuleStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

# --- Models ---

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="tenant")
    rules: Mapped[List["FraudRule"]] = relationship("FraudRule", back_populates="tenant")

    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}')>"

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    merchant_id: Mapped[str] = mapped_column(String(50), index=True)
    ip_address: Mapped[str] = mapped_column(String(45)) # IPv4 or IPv6
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="transactions")
    reports: Mapped[List["FraudReport"]] = relationship("FraudReport", back_populates="transaction")

    def __repr__(self):
        return f"<Transaction(id={self.id}, tenant_id={self.tenant_id}, amount={self.amount})>"

class FraudRule(Base):
    __tablename__ = "fraud_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    rule_expression: Mapped[str] = mapped_column(Text) # e.g., "amount > 1000 AND ip_country == 'NG'"
    severity_score: Mapped[int] = mapped_column(Integer) # 1 to 100
    status: Mapped[RuleStatus] = mapped_column(Enum(RuleStatus), default=RuleStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="rules")
    reports: Mapped[List["FraudReport"]] = relationship("FraudReport", back_populates="rule")

    def __repr__(self):
        return f"<FraudRule(id={self.id}, name='{self.name}', score={self.severity_score})>"

class FraudReport(Base):
    __tablename__ = "fraud_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"), index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("fraud_rules.id"), nullable=True, index=True) # Nullable if decision is from ML model
    decision: Mapped[FraudDecision] = mapped_column(Enum(FraudDecision))
    score: Mapped[float] = mapped_column(Float) # Total fraud score (e.g., 0.0 to 1.0 or 0 to 100)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # Version of the ML model used
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="reports")
    rule: Mapped[Optional["FraudRule"]] = relationship("FraudRule", back_populates="reports")

    def __repr__(self):
        return f"<FraudReport(id={self.id}, transaction_id={self.transaction_id}, decision='{self.decision.name}')>"