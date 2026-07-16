import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.schema import UniqueConstraint, Index

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    """Mixin for common timestamp fields."""
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

class Party(Base, TimestampMixin):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True, index=True)
    party_type = Column(String, nullable=False) # 'Individual', 'Organization'
    name = Column(String, nullable=False)
    contact_email = Column(String, unique=True, index=True)
    contact_phone = Column(String)
    address = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    owned_assets = relationship("LandAsset", back_populates="owner", foreign_keys="[LandAsset.owner_id]")
    agreements = relationship("Agreement", back_populates="party", foreign_keys="[Agreement.party_id]")

    __table_args__ = (
        Index("ix_parties_name", "name"),
    )

class LandAsset(Base, TimestampMixin):
    __tablename__ = "land_assets"

    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(String, unique=True, index=True, nullable=False) # e.g., cadastral ID
    name = Column(String, nullable=False)
    description = Column(Text)
    area_sqm = Column(Float, nullable=False)
    owner_id = Column(Integer, ForeignKey("parties.id"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    zoning_code = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    owner = relationship("Party", back_populates="owned_assets", foreign_keys=[owner_id])
    agreements = relationship("Agreement", back_populates="land_asset")

    __table_args__ = (
        Index("ix_land_assets_coords", "latitude", "longitude"),
    )

class Agreement(Base, TimestampMixin):
    __tablename__ = "agreements"

    id = Column(Integer, primary_key=True, index=True)
    agreement_type = Column(String, nullable=False) # 'Lease', 'Permit', 'ROW'
    name = Column(String, nullable=False)
    land_asset_id = Column(Integer, ForeignKey("land_assets.id"), nullable=False)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False) # Lessee/Permittee
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    term_months = Column(Integer)
    status = Column(String, nullable=False) # 'Active', 'Expired', 'Pending'
    payment_amount = Column(Float)
    payment_frequency = Column(String) # 'Monthly', 'Annually'

    # Relationships
    land_asset = relationship("LandAsset", back_populates="agreements")
    party = relationship("Party", back_populates="agreements", foreign_keys=[party_id])

    __table_args__ = (
        UniqueConstraint("land_asset_id", "name", name="uq_agreement_asset_name"),
        Index("ix_agreements_status", "status"),
    )
