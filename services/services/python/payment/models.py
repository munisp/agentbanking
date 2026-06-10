from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum

# Enums for clarity and type safety
class PaymentStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELED = "canceled"

class PaymentMethodType(enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    E_WALLET = "e_wallet"
    OTHER = "other"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    
    # Unique identifier for the payment, e.g., an order ID from an external system
    external_id = Column(String, unique=True, index=True, nullable=False) 
    
    # Amount and currency
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="USD") # ISO 4217 code

    # Status of the payment
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to transactions (one payment can have multiple transactions, e.g., initial charge, refund)
    transactions = relationship("Transaction", back_populates="payment")

    # Relationship to the payment method used
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=True)
    payment_method = relationship("PaymentMethod", back_populates="payments")

    # User/Customer ID (assuming an external user service)
    user_id = Column(Integer, index=True, nullable=False)

    # Description/Metadata
    description = Column(String, nullable=True)

    def __repr__(self):
        return f"<Payment(id={self.id}, external_id='{self.external_id}', amount={self.amount}, status='{self.status.value}')>"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Link to the parent payment
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    payment = relationship("Payment", back_populates="transactions")

    # Unique ID from the payment processor (e.g., Stripe charge ID)
    processor_transaction_id = Column(String, unique=True, index=True, nullable=False)

    # Type of transaction (e.g., 'charge', 'refund', 'capture', 'authorization')
    transaction_type = Column(String, nullable=False) 
    
    # Amount of this specific transaction (can be less than payment amount for partial refunds)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    # Status of the transaction (e.g., 'success', 'failed', 'pending')
    status = Column(String, nullable=False) 

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Error details if transaction failed
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    def __repr__(self):
        return f"<Transaction(id={self.id}, payment_id={self.payment_id}, type='{self.transaction_type}', status='{self.status}')>"

class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    
    # User/Customer ID
    user_id = Column(Integer, index=True, nullable=False)

    # Type of payment method
    method_type = Column(Enum(PaymentMethodType), nullable=False)

    # Tokenized representation of the payment method (e.g., Stripe token, last 4 digits)
    token = Column(String, index=True, nullable=False) 
    
    # Last 4 digits of the card/account number
    last_four = Column(String(4), nullable=True) 
    
    # Expiration date for cards
    expiry_month = Column(Integer, nullable=True)
    expiry_year = Column(Integer, nullable=True)

    # Whether this is the user's default payment method
    is_default = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to payments
    payments = relationship("Payment", back_populates="payment_method")

    def __repr__(self):
        return f"<PaymentMethod(id={self.id}, user_id={self.user_id}, type='{self.method_type.value}', last_four='{self.last_four}')>"