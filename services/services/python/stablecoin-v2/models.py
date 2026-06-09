from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

# Enums
class TransactionType(enum.Enum):
    MINT = "MINT"
    BURN = "BURN"
    TRANSFER = "TRANSFER"
    COLLATERAL_DEPOSIT = "COLLATERAL_DEPOSIT"
    COLLATERAL_WITHDRAWAL = "COLLATERAL_WITHDRAWAL"

class VaultStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"

class CollateralAsset(enum.Enum):
    ETH = "ETH"
    BTC = "BTC"
    USDC = "USDC"
    T_BILLS = "T_BILLS"

# Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    public_address = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    vaults = relationship("Vault", back_populates="owner")
    transactions = relationship("Transaction", back_populates="user")

class Vault(Base):
    __tablename__ = "vaults"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    collateral_asset = Column(Enum(CollateralAsset), nullable=False)
    collateral_amount = Column(Numeric(precision=30, scale=18), nullable=False)
    stablecoin_debt = Column(Numeric(precision=30, scale=18), nullable=False)
    collateralization_ratio = Column(Float, nullable=False) # Calculated ratio
    status = Column(Enum(VaultStatus), default=VaultStatus.OPEN, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="vaults")
    transactions = relationship("Transaction", back_populates="vault")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vault_id = Column(Integer, ForeignKey("vaults.id"), nullable=True) # Nullable for non-vault transactions (e.g., simple transfer)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    stablecoin_amount = Column(Numeric(precision=30, scale=18), nullable=False)
    collateral_change = Column(Numeric(precision=30, scale=18), nullable=True) # Change in collateral for vault transactions
    tx_hash = Column(String, unique=True, index=True, nullable=True) # Blockchain transaction hash
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")
    vault = relationship("Vault", back_populates="transactions")

# Global Stablecoin State (Simplified for a single row)
class GlobalState(Base):
    __tablename__ = "global_state"

    id = Column(Integer, primary_key=True, default=1)
    total_stablecoin_supply = Column(Numeric(precision=30, scale=18), default=0, nullable=False)
    total_collateral_value = Column(Numeric(precision=30, scale=18), default=0, nullable=False)
    last_updated = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())