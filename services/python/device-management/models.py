"""
Complete Database Models for Device Management Service
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

Base = declarative_base()

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=True, index=True)
    agent_id = Column(Integer, nullable=True, index=True)
    device_name = Column(String(255), nullable=True)
    device_type = Column(String(50), default="mobile", index=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    os_type = Column(String(50), nullable=True)
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(50), nullable=True)
    device_fingerprint = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(String(50), default="pending", index=True)
    verified = Column(Boolean, default=False)
    trusted = Column(Boolean, default=False)
    last_ip_address = Column(String(45), nullable=True)
    total_logins = Column(Integer, default=0)
    total_transactions = Column(Integer, default=0)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, default=dict)
    sessions = relationship("DeviceSession", backref="device", cascade="all, delete-orphan")

class DeviceSession(Base):
    __tablename__ = "device_sessions"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    session_token = Column(String(500), unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    active = Column(Boolean, default=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

class DeviceActivity(Base):
    __tablename__ = "device_activities"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    activity_type = Column(String(100), nullable=False, index=True)
    activity_name = Column(String(255), nullable=False)
    status = Column(String(50), default="success", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Pydantic Schemas
class DeviceRegister(BaseModel):
    device_id: str
    device_fingerprint: str
    device_type: str
    device_name: Optional[str] = None
    user_id: Optional[int] = None

class DeviceResponse(BaseModel):
    id: int
    device_id: str
    status: str
    verified: bool
    registered_at: datetime
    class Config:
        orm_mode = True

def create_db_tables():
    from .config import engine
    Base.metadata.create_all(bind=engine)
