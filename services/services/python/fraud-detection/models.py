from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
import enum

# Assuming Base is imported from config.py in a real application, 
# Base definition for standalone model usage
# and rely on the config.py to have the real one.
# For the purpose of this task, we will assume the Base is available.
try:
    from config import Base
except ImportError:
    # Base for standalone model usage
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


# --- Enums ---
class DecisionStatus(str, enum.Enum):
    """Possible outcomes of a fraud check."""
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"

class CaseStatus(str, enum.Enum):
    """Possible statuses for a fraud case."""
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    CLOSED_FRAUD = "CLOSED_FRAUD"
    CLOSED_NOT_FRAUD = "CLOSED_NOT_FRAUD"


# --- SQLAlchemy Models ---

class Transaction(Base):
    """
    Represents a financial transaction to be checked for fraud.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    merchant_id = Column(Integer, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    country = Column(String(2), nullable=False)
    
    # Relationship to the fraud check result
    check_result = relationship("FraudCheckResult", back_populates="transaction", uselist=False)

class FraudCheckResult(Base):
    """
    Stores the result of the ML and Rules Engine fraud check for a transaction.
    """
    __tablename__ = "fraud_check_results"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), unique=True, nullable=False)
    
    ml_score = Column(Float, nullable=False, index=True)
    rules_triggered = Column(Text, nullable=True) # Stored as a comma-separated string or JSON string
    
    decision = Column(Enum(DecisionStatus), nullable=False, index=True)
    reason = Column(String, nullable=False)
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to the transaction
    transaction = relationship("Transaction", back_populates="check_result")
    
    # Relationship to the case (if one was created)
    case = relationship("Case", back_populates="check_result", uselist=False)

class Case(Base):
    """
    Represents a case created for a transaction flagged for manual review.
    """
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("fraud_check_results.id"), unique=True, nullable=False)
    
    status = Column(Enum(CaseStatus), default=CaseStatus.OPEN, nullable=False, index=True)
    analyst_id = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship back to the check result
    check_result = relationship("FraudCheckResult", back_populates="case")


# --- Pydantic Schemas ---

# Base Schemas
class TransactionBase(BaseModel):
    """Base schema for transaction data."""
    user_id: int = Field(..., description="ID of the user performing the transaction.")
    merchant_id: int = Field(..., description="ID of the merchant receiving the funds.")
    amount: float = Field(..., gt=0, description="Transaction amount.")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (e.g., USD).")
    country: str = Field(..., min_length=2, max_length=2, description="2-letter country code of the transaction origin.")
    # Optional field for simulation in router.py
    transaction_count_24h: Optional[int] = Field(0, description="24-hour transaction velocity count.")

class FraudCheckResultBase(BaseModel):
    """Base schema for fraud check results."""
    ml_score: float = Field(..., ge=0, le=1, description="Machine Learning fraud score (0.0 to 1.0).")
    rules_triggered: List[str] = Field(..., description="List of rules that were triggered.")
    decision: DecisionStatus = Field(..., description="Final decision: ALLOW, REVIEW, or BLOCK.")
    reason: str = Field(..., description="Reason for the final decision.")

class CaseBase(BaseModel):
    """Base schema for case data."""
    analyst_id: Optional[int] = Field(None, description="ID of the analyst assigned to the case.")
    notes: Optional[str] = Field(None, description="Analyst notes on the case.")


# Request Schemas
class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction and triggering a fraud check."""
    pass

class CaseUpdate(CaseBase):
    """Schema for updating an existing case."""
    status: CaseStatus = Field(..., description="New status of the case.")


# Response Schemas (with ORM mode for SQLAlchemy compatibility)
class TransactionRead(TransactionBase):
    """Schema for reading a transaction from the database."""
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class FraudCheckResultRead(FraudCheckResultBase):
    """Schema for reading a fraud check result from the database."""
    id: int
    transaction_id: int
    checked_at: datetime
    
    # Override rules_triggered to be a list of strings for Pydantic
    @classmethod
    def __get_validators__(cls):
        yield cls.validate_rules_triggered

    @classmethod
    def validate_rules_triggered(cls, v):
        if isinstance(v, str):
            return [r.strip() for r in v.split(',') if r.strip()]
        return v

    class Config:
        from_attributes = True

class CaseRead(CaseBase):
    """Schema for reading a case from the database."""
    id: int
    result_id: int
    status: CaseStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TransactionCheckResponse(BaseModel):
    """Combined response schema for a transaction and its fraud check result."""
    transaction: TransactionRead
    result: FraudCheckResultRead
    case_id: Optional[int] = Field(None, description="ID of the case created, if decision is REVIEW.")
    
    class Config:
        from_attributes = True
