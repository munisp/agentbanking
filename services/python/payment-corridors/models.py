from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class CorridorStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"

class FeeType(enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    TIERED = "TIERED"

class LimitType(enum.Enum):
    TRANSACTION = "TRANSACTION"
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"

class PaymentCorridor(Base):
    __tablename__ = "payment_corridors"

    id = Column(Integer, primary_key=True, index=True)
    source_country_iso = Column(String(3), index=True, nullable=False)
    source_currency_iso = Column(String(3), nullable=False)
    destination_country_iso = Column(String(3), index=True, nullable=False)
    destination_currency_iso = Column(String(3), nullable=False)
    
    # Corridor details
    status = Column(Enum(CorridorStatus), default=CorridorStatus.INACTIVE, nullable=False)
    exchange_rate = Column(Float, nullable=False)
    processing_time_hours = Column(Integer, default=24, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    fees = relationship("CorridorFee", back_populates="corridor", cascade="all, delete-orphan")
    limits = relationship("CorridorLimit", back_populates="corridor", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('source_country_iso', 'source_currency_iso', 
                         'destination_country_iso', 'destination_currency_iso', 
                         name='uq_corridor_route'),
    )

class CorridorFee(Base):
    __tablename__ = "corridor_fees"

    id = Column(Integer, primary_key=True, index=True)
    corridor_id = Column(Integer, ForeignKey("payment_corridors.id"), nullable=False)
    
    fee_type = Column(Enum(FeeType), nullable=False)
    value = Column(Float, nullable=False) # Can be fixed amount or percentage
    min_amount = Column(Float, default=0.0) # Minimum transaction amount for this fee to apply
    max_amount = Column(Float, default=999999999.99) # Maximum transaction amount for this fee to apply

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    corridor = relationship("PaymentCorridor", back_populates="fees")

class CorridorLimit(Base):
    __tablename__ = "corridor_limits"

    id = Column(Integer, primary_key=True, index=True)
    corridor_id = Column(Integer, ForeignKey("payment_corridors.id"), nullable=False)
    
    limit_type = Column(Enum(LimitType), nullable=False)
    max_value = Column(Float, nullable=False) # The maximum allowed value
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship
    corridor = relationship("PaymentCorridor", back_populates="limits")

    # Constraints
    __table_args__ = (
        UniqueConstraint('corridor_id', 'limit_type', name='uq_corridor_limit_type'),
    )
