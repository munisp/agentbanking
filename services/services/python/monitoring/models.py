import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from .database import Base

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    # Status can be 'Operational', 'Degraded', 'Offline'
    status = Column(String, default="Operational", nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    endpoints = relationship("Endpoint", back_populates="service", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_service_name", "name"),
    )

class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    url = Column(String, index=True, nullable=False)
    method = Column(String, default="GET", nullable=False) # e.g., GET, POST
    check_interval_seconds = Column(Integer, default=60, nullable=False)
    expected_status_code = Column(Integer, default=200, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="endpoints")
    records = relationship("MonitorRecord", back_populates="endpoint", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_endpoint_service_url", "service_id", "url", unique=True),
    )

class MonitorRecord(Base):
    __tablename__ = "monitor_records"

    id = Column(Integer, primary_key=True, index=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    is_success = Column(Boolean, nullable=False)
    error_message = Column(String, nullable=True)

    endpoint = relationship("Endpoint", back_populates="records")

    __table_args__ = (
        Index("ix_record_endpoint_timestamp", "endpoint_id", "timestamp"),
    )