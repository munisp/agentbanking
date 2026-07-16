from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class LocationModel(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    components: Mapped[List["ComponentModel"]] = relationship("ComponentModel", back_populates="location")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Location(name='{self.name}')>"

class StatusModel(Base):
    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False) # e.g., Operational, Maintenance, Degraded, Offline
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    components: Mapped[List["ComponentModel"]] = relationship("ComponentModel", back_populates="status")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Status(name='{self.name}')>"

class ComponentModel(Base):
    __tablename__ = "components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., Server, Router, Database, Application
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), index=True) # IPv4 or IPv6
    description: Mapped[Optional[str]] = mapped_column(Text)

    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("statuses.id"), nullable=False)

    location: Mapped["LocationModel"] = relationship("LocationModel", back_populates="components")
    status: Mapped["StatusModel"] = relationship("StatusModel", back_populates="components")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("name", "location_id", name="uq_component_name_location"),
    )

    def __repr__(self):
        return f"<Component(name='{self.name}', type='{self.type}')>"