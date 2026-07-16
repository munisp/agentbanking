from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class PaymentStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core Transaction Details
    papss_ref_id = Column(String, unique=True, index=True, nullable=False) # PAPSS unique transaction ID
    originator_bank_bic = Column(String, index=True, nullable=False) # Originator Bank BIC/SWIFT
    beneficiary_bank_bic = Column(String, index=True, nullable=False) # Beneficiary Bank BIC/SWIFT
    
    # Financial Details
    amount = Column(Float, nullable=False)
    currency_code = Column(String(3), nullable=False) # ISO 4217 currency code (e.g., "NGN", "ZAR")
    
    # Status and Timestamps
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Originator Details (Simplified)
    originator_account_number = Column(String, nullable=False)
    originator_name = Column(String, nullable=False)
    
    # Beneficiary Details (Simplified)
    beneficiary_account_number = Column(String, nullable=False)
    beneficiary_name = Column(String, nullable=False)
    
    # Error/Failure Details
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    def __repr__(self):
        return f"<PaymentTransaction(id={self.id}, papss_ref_id='{self.papss_ref_id}', status='{self.status.value}')>"
