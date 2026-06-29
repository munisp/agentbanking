from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()

class TransactionStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    EXPIRED = "EXPIRED"

class TransactionType(enum.Enum):
    PAY = "PAY"
    COLLECT = "COLLECT"

class UPITransaction(Base):
    __tablename__ = "upi_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # External UPI/PSP Transaction ID
    transaction_id = Column(String, unique=True, index=True, nullable=False)
    
    # Internal Reference ID (e.g., Merchant Order ID)
    reference_id = Column(String, index=True, nullable=False)
    
    # Virtual Payment Address (VPA) of the counterparty
    vpa = Column(String, index=True, nullable=False)
    
    # Transaction details
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR", nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    
    # Status and timestamps
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    status_message = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Additional metadata (e.g., bank reference number, merchant code)
    bank_ref_no = Column(String, nullable=True)
    merchant_code = Column(String, nullable=True)

    def __repr__(self):
        return f"<UPITransaction(id={self.id}, transaction_id='{self.transaction_id}', status='{self.status.value}')>"