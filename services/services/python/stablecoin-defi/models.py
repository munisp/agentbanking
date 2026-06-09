import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="user")

class Stablecoin(Base):
    __tablename__ = "stablecoins"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False) # e.g., "USDC", "DAI"
    name = Column(String, nullable=False)
    peg_asset = Column(String, default="USD")
    collateral_ratio = Column(Float, default=1.0) # For collateralized stablecoins
    is_active = Column(Integer, default=1)

    accounts = relationship("Account", back_populates="stablecoin")
    transactions = relationship("Transaction", back_populates="stablecoin")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stablecoin_id = Column(Integer, ForeignKey("stablecoins.id"), nullable=False)
    balance = Column(Float, default=0.0)
    deposit_rate = Column(Float, default=0.0) # Annual Percentage Yield (APY) for deposits
    borrow_rate = Column(Float, default=0.0) # Annual Percentage Rate (APR) for borrowing
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    stablecoin = relationship("Stablecoin", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")

    __table_args__ = (
        UniqueConstraint('user_id', 'stablecoin_id', name='_user_stablecoin_uc'),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    stablecoin_id = Column(Integer, ForeignKey("stablecoins.id"), nullable=False)
    type = Column(Enum("DEPOSIT", "WITHDRAW", "BORROW", "REPAY", name="transaction_type"), nullable=False)
    amount = Column(Float, nullable=False)
    rate_at_time = Column(Float, nullable=False) # Deposit or borrow rate at the time of transaction
    timestamp = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="transactions")
    stablecoin = relationship("Stablecoin", back_populates="transactions")
