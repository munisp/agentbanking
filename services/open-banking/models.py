import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Enum, Boolean, Index
from sqlalchemy.orm import relationship
from database import Base
import enum

# --- Enums for Open Banking Data Types ---

class AccountStatus(enum.Enum):
    """Status of the account."""
    Enabled = "Enabled"
    Disabled = "Disabled"
    Deleted = "Deleted"

class BalanceType(enum.Enum):
    """Type of balance."""
    ClosingAvailable = "ClosingAvailable"
    OpeningBooked = "OpeningBooked"
    InterimAvailable = "InterimAvailable"
    InterimBooked = "InterimBooked"

class CreditDebitIndicator(enum.Enum):
    """Indicates whether the amount is a credit or a debit."""
    Credit = "Credit"
    Debit = "Debit"

class TransactionStatus(enum.Enum):
    """Status of the transaction."""
    Booked = "Booked"
    Pending = "Pending"
    Rejected = "Rejected"

# --- Core Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="owner")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    currency = Column(String(3), nullable=False) # e.g., "GBP", "USD"
    nickname = Column(String, nullable=False)
    status = Column(Enum(AccountStatus), default=AccountStatus.Enabled, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="accounts")
    balances = relationship("Balance", back_populates="account", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_account_owner_currency", "owner_id", "currency"),
    )

class Balance(Base):
    __tablename__ = "balances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    amount = Column(Numeric(precision=19, scale=4), nullable=False)
    currency = Column(String(3), nullable=False)
    type = Column(Enum(BalanceType), nullable=False)
    credit_debit_indicator = Column(Enum(CreditDebitIndicator), nullable=False)
    datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="balances")

    __table_args__ = (
        Index("idx_balance_account_type", "account_id", "type"),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    transaction_reference = Column(String, index=True, nullable=True)
    amount = Column(Numeric(precision=19, scale=4), nullable=False)
    currency = Column(String(3), nullable=False)
    credit_debit_indicator = Column(Enum(CreditDebitIndicator), nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.Booked, nullable=False)
    booking_date_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    transaction_information = Column(String, nullable=True)

    account = relationship("Account", back_populates="transactions")

    __table_args__ = (
        Index("idx_transaction_account_date", "account_id", "booking_date_time"),
    )