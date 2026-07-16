from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    # Production implementation for user authentication. In a real app, this would be a FK to a users table.
    user_id = Column(Integer, index=True, nullable=False) 
    account_name = Column(String, index=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to CurrencyBalance
    balances = relationship("CurrencyBalance", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account(id={self.id}, user_id={self.user_id}, name='{self.account_name}')>"

class CurrencyBalance(Base):
    __tablename__ = "currency_balances"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    currency_code = Column(String(3), index=True, nullable=False) # e.g., 'USD', 'EUR', 'GBP'
    
    # Use Numeric for financial data to avoid floating point issues. Precision and scale can be adjusted.
    balance = Column(Numeric(precision=18, scale=4), default=0.0000, nullable=False) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to Account
    account = relationship("Account", back_populates="balances")

    # Constraint to ensure an account only has one balance entry per currency
    __table_args__ = (
        UniqueConstraint("account_id", "currency_code", name="uq_account_currency"),
    )

    def __repr__(self):
        return f"<CurrencyBalance(id={self.id}, account_id={self.account_id}, currency='{self.currency_code}', balance={self.balance})>"