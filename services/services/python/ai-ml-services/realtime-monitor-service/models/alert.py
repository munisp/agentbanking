"""
Alert Database Models
Nigerian Remittance Platform
"""

from sqlalchemy import Column, String, DateTime, Enum, Boolean, JSON, Index
from sqlalchemy.sql import func
import enum
from db.base import Base


class AlertType(str, enum.Enum):
    """Alert type enumeration"""
    FRAUD = "fraud"
    HIGH_VOLUME = "high_volume"
    SYSTEM_ERROR = "system_error"
    RATE_LIMIT = "rate_limit"
    UNUSUAL_ACTIVITY = "unusual_activity"
    COMPLIANCE = "compliance"


class AlertSeverity(str, enum.Enum):
    """Alert severity enumeration"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Alert(Base):
    """Alert model"""
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, index=True)
    type = Column(Enum(AlertType), nullable=False, index=True)
    severity = Column(Enum(AlertSeverity), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    
    # Acknowledgment
    acknowledged = Column(Boolean, default=False, nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(36), nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_acknowledged_timestamp', 'acknowledged', 'timestamp'),
        Index('idx_severity_timestamp', 'severity', 'timestamp'),
    )

    def __repr__(self):
        return f"<Alert {self.id} {self.severity} {self.type}>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }
