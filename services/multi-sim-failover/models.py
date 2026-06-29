"""Models for Multi-SIM Failover Service."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, SmallInteger, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TerminalConnectivityProfile(Base):
    __tablename__ = "terminal_connectivity_profiles"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    terminal_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    sim_slot_1_carrier = Column(String(50))
    sim_slot_2_carrier = Column(String(50))
    sim_slot_3_carrier = Column(String(50))
    wifi_enabled = Column(Boolean, default=False)
    active_sim_slot = Column(SmallInteger, default=1)
    failover_order = Column(String(100), default="sim1,sim2,sim3,wifi")
    signal_strength_1 = Column(SmallInteger, default=0)
    signal_strength_2 = Column(SmallInteger, default=0)
    signal_strength_3 = Column(SmallInteger, default=0)
    wifi_signal = Column(SmallInteger, default=0)
    last_heartbeat = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConnectivityFailoverEvent(Base):
    __tablename__ = "connectivity_failover_events"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    terminal_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    from_sim_slot = Column(SmallInteger)
    to_sim_slot = Column(SmallInteger)
    from_carrier = Column(String(50))
    to_carrier = Column(String(50))
    reason = Column(String(200))
    transaction_id = Column(PGUUID(as_uuid=True))
    failover_latency_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Pydantic schemas
class SignalUpdateRequest(BaseModel):
    terminal_id: UUID
    sim1_signal: Optional[int] = Field(None, ge=0, le=100)
    sim2_signal: Optional[int] = Field(None, ge=0, le=100)
    sim3_signal: Optional[int] = Field(None, ge=0, le=100)
    wifi_signal: Optional[int] = Field(None, ge=0, le=100)
    sim1_carrier: Optional[str] = None
    sim2_carrier: Optional[str] = None
    sim3_carrier: Optional[str] = None


class ManualFailoverRequest(BaseModel):
    terminal_id: UUID
    target_slot: int = Field(..., ge=1, le=4)
    reason: str = "manual"
    transaction_id: Optional[UUID] = None


class SlotInfo(BaseModel):
    slot: int
    carrier: Optional[str]
    signal: int
    score: float
    is_active: bool


class ConnectivityStatus(BaseModel):
    terminal_id: UUID
    active_slot: int
    active_carrier: Optional[str]
    active_signal: int
    quality: str  # excellent | good | fair | poor | offline
    available_slots: List[SlotInfo]
    failovers_last_24h: int
    last_heartbeat: Optional[datetime]
    is_online: bool


class FailoverEventResponse(BaseModel):
    id: UUID
    terminal_id: UUID
    from_sim_slot: Optional[int]
    to_sim_slot: Optional[int]
    from_carrier: Optional[str]
    to_carrier: Optional[str]
    reason: Optional[str]
    failover_latency_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# Enums used in service
class SimSlot:
    SIM1 = 1
    SIM2 = 2
    SIM3 = 3
    WIFI = 4


class FailoverReason:
    SIGNAL_LOSS = "signal_loss"
    TIMEOUT = "timeout"
    ERROR_RATE = "error_rate"
    MANUAL = "manual"
    SIGNAL_QUALITY = "signal_quality"
