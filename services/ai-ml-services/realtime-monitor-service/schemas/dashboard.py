"""
Dashboard Pydantic Schemas
Nigerian Remittance Platform
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from models.transaction import TransactionStatus, TransactionType
from models.alert import AlertType, AlertSeverity


# User Schemas
class UserSchema(BaseModel):
    """User schema"""
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


# Transaction Schemas
class TransactionSchema(BaseModel):
    """Transaction schema"""
    id: str
    amount: float
    currency: str
    status: TransactionStatus
    type: TransactionType
    sender: UserSchema
    recipient: UserSchema
    payment_method: str
    reference: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class PaginatedTransactionResponse(BaseModel):
    """Paginated transaction response"""
    data: List[TransactionSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


# Alert Schemas
class AlertSchema(BaseModel):
    """Alert schema"""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    acknowledged: bool
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class PaginatedAlertResponse(BaseModel):
    """Paginated alert response"""
    data: List[AlertSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


# Metrics Schemas
class CurrencyBreakdown(BaseModel):
    """Currency breakdown schema"""
    currency: str
    volume: float
    count: int
    percentage: float


class HourlyVolume(BaseModel):
    """Hourly volume schema"""
    hour: str
    volume: float
    count: int


class TopCorridor(BaseModel):
    """Top corridor schema"""
    from_country: str
    to_country: str
    volume: float
    count: int


class DashboardMetrics(BaseModel):
    """Dashboard metrics schema"""
    active_transactions: int
    total_volume: float
    success_rate: float
    average_processing_time: float
    failed_transactions: int
    pending_transactions: int
    transactions_per_minute: float
    active_users: int
    total_fees_collected: float
    currency_breakdown: List[CurrencyBreakdown]
    hourly_volume: List[HourlyVolume]
    top_corridors: List[TopCorridor]


# WebSocket Message Schemas
class WebSocketMessage(BaseModel):
    """WebSocket message schema"""
    type: str
    data: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# API Response Schemas
class ApiResponse(BaseModel):
    """Generic API response"""
    data: Any
    message: Optional[str] = None
    status: str = "success"


# Filter Schemas
class DashboardFilters(BaseModel):
    """Dashboard filters schema"""
    status: Optional[List[TransactionStatus]] = None
    type: Optional[List[TransactionType]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    currency: Optional[List[str]] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


# System Health Schema
class SystemHealth(BaseModel):
    """System health schema"""
    status: str
    database: str
    redis: str
    websocket_connections: int
    uptime_seconds: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
