from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pydantic import BaseModel, Field

from config import Base

# --- Enums ---

class CommissionType(str, Enum):
    """Defines the type of commission calculation."""
    PERCENTAGE = "percentage"
    FLAT_RATE = "flat_rate"

class CommissionStatus(str, Enum):
    """Defines the status of a calculated commission."""
    CALCULATED = "calculated"
    PAID = "paid"
    VOID = "void"

# --- SQLAlchemy Models ---

class CommissionTier(Base):
    """Represents a performance tier that influences commission rates."""
    __tablename__ = "commission_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rate_multiplier: Mapped[float] = mapped_column(Float, default=1.0, doc="Multiplier applied to base commission rates for this tier.")

    rules: Mapped[List["CommissionRule"]] = relationship("CommissionRule", back_populates="tier")

class CommissionRule(Base):
    """Defines a specific rule for calculating commission."""
    __tablename__ = "commission_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    product_category: Mapped[str] = mapped_column(String, index=True, doc="Category of product this rule applies to.")
    min_sale_amount: Mapped[float] = mapped_column(Float, default=0.0, doc="Minimum sale amount for this rule to apply.")
    commission_type: Mapped[CommissionType] = mapped_column(String, nullable=False, doc="Type of commission (percentage or flat_rate).")
    commission_value: Mapped[float] = mapped_column(Float, nullable=False, doc="The value (rate or amount) for the commission.")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship to Tier (Optional: a rule can be general or tier-specific)
    tier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("commission_tiers.id"), nullable=True)
    tier: Mapped[Optional["CommissionTier"]] = relationship("CommissionTier", back_populates="rules")

class Sale(Base):
    """Represents a sale transaction that may generate a commission."""
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    salesperson_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    product_category: Mapped[str] = mapped_column(String, index=True, nullable=False)
    sale_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    commissions: Mapped[List["CommissionPayment"]] = relationship("CommissionPayment", back_populates="sale")

class CommissionPayment(Base):
    """Represents a calculated commission payment."""
    __tablename__ = "commission_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales.id"), nullable=False)
    salesperson_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False, doc="ID of the rule that triggered this commission.")
    calculated_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[CommissionStatus] = mapped_column(String, default=CommissionStatus.CALCULATED)
    calculation_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="commissions")


# --- Pydantic Schemas ---

# Base Schemas for common fields
class CommissionTierBase(BaseModel):
    name: str = Field(..., example="Gold Tier")
    description: Optional[str] = Field(None, example="Top performers with a 1.5x rate multiplier.")
    rate_multiplier: float = Field(1.0, ge=0.0, example=1.5)

class CommissionRuleBase(BaseModel):
    name: str = Field(..., example="High-Value Software Commission")
    product_category: str = Field(..., example="Software")
    min_sale_amount: float = Field(0.0, ge=0.0, example=1000.0)
    commission_type: CommissionType = Field(..., example=CommissionType.PERCENTAGE)
    commission_value: float = Field(..., ge=0.0, example=0.15) # 15% or $15
    is_active: bool = Field(True, example=True)
    tier_id: Optional[int] = Field(None, example=1, description="Optional ID of the tier this rule belongs to.")

class SaleBase(BaseModel):
    salesperson_id: int = Field(..., ge=1, example=101)
    amount: float = Field(..., gt=0.0, example=5000.0)
    product_category: str = Field(..., example="Software")

class CommissionPaymentBase(BaseModel):
    sale_id: int = Field(..., ge=1, example=50)
    salesperson_id: int = Field(..., ge=1, example=101)
    rule_id: int = Field(..., ge=1, example=3)
    calculated_amount: float = Field(..., ge=0.0, example=750.0)
    status: CommissionStatus = Field(CommissionStatus.CALCULATED, example=CommissionStatus.CALCULATED)
    payment_date: Optional[datetime] = Field(None, example=None)


# Create Schemas (for POST requests)
class CommissionTierCreate(CommissionTierBase):
    pass

class CommissionRuleCreate(CommissionRuleBase):
    pass

class SaleCreate(SaleBase):
    pass

class CommissionPaymentCreate(CommissionPaymentBase):
    pass


# Update Schemas (for PUT/PATCH requests)
class CommissionTierUpdate(CommissionTierBase):
    name: Optional[str] = None
    rate_multiplier: Optional[float] = None

class CommissionRuleUpdate(CommissionRuleBase):
    name: Optional[str] = None
    product_category: Optional[str] = None
    commission_type: Optional[CommissionType] = None
    commission_value: Optional[float] = None
    is_active: Optional[bool] = None
    tier_id: Optional[int] = None

class CommissionPaymentUpdate(BaseModel):
    status: Optional[CommissionStatus] = None
    payment_date: Optional[datetime] = None


# Read Schemas (for GET responses)
class CommissionTierRead(CommissionTierBase):
    id: int
    class Config:
        orm_mode = True

class CommissionRuleRead(CommissionRuleBase):
    id: int
    class Config:
        orm_mode = True

class SaleRead(SaleBase):
    id: int
    sale_date: datetime
    class Config:
        orm_mode = True

class CommissionPaymentRead(CommissionPaymentBase):
    id: int
    calculation_date: datetime
    sale: SaleRead # Include the related sale data
    class Config:
        orm_mode = True

# Schema for the commission calculation request (not tied to a DB model)
class CommissionCalculateRequest(BaseModel):
    salesperson_id: int = Field(..., ge=1, example=101)
    amount: float = Field(..., gt=0.0, example=5000.0)
    product_category: str = Field(..., example="Software")
    # Optional: Allow specifying a tier for a specific calculation, though typically derived
    tier_name: Optional[str] = Field(None, example="Gold Tier")

class CommissionCalculationResult(BaseModel):
    """Schema for the result of a commission calculation."""
    commission_amount: float = Field(..., ge=0.0, example=750.0)
    rule_applied_id: int = Field(..., example=3)
    rule_name: str = Field(..., example="High-Value Software Commission")
    tier_multiplier: float = Field(..., example=1.5)
    is_new_sale_recorded: bool = Field(..., example=True)
    new_sale_id: Optional[int] = Field(None, example=51)
