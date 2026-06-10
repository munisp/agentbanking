import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base

# Base class for declarative class definitions
Base = declarative_base()

class Stablecoin(Base):
    """
    Represents a supported stablecoin.
    """
    __tablename__ = "stablecoins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    contract_address: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="stablecoin")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="stablecoin")

    def __repr__(self):
        return f"<Stablecoin(symbol='{self.symbol}', name='{self.name}')>"

class Account(Base):
    """
    Represents a user's stablecoin account.
    """
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False) # Represents the user in the main system
    stablecoin_id: Mapped[int] = mapped_column(Integer, ForeignKey("stablecoins.id"), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    stablecoin: Mapped["Stablecoin"] = relationship("Stablecoin", back_populates="accounts")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="account")

    def __repr__(self):
        return f"<Account(user_id={self.user_id}, stablecoin_id={self.stablecoin_id}, balance={self.balance})>"

class Transaction(Base):
    """
    Represents a stablecoin transaction (deposit, withdrawal, transfer).
    """
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    stablecoin_id: Mapped[int] = mapped_column(Integer, ForeignKey("stablecoins.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(Enum("DEPOSIT", "WITHDRAWAL", "TRANSFER", name="transaction_type_enum"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Enum("PENDING", "COMPLETED", "FAILED", name="transaction_status_enum"), default="PENDING", nullable=False)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True) # Blockchain transaction hash
    destination_address: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")
    stablecoin: Mapped["Stablecoin"] = relationship("Stablecoin", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(type='{self.transaction_type}', amount={self.amount}, status='{self.status}')>"