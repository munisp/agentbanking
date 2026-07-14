import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Index, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase
from pydantic import BaseModel, Field

# --- SQLAlchemy Base and Models ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common utility methods.
    """
    pass

class RiskAssessment(Base):
    """
    SQLAlchemy model for a Risk Assessment record.
    """
    __tablename__ = "risk_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(String, nullable=False, index=True, comment="ID of the entity being assessed (e.g., user_id, transaction_id)")
    entity_type = Column(String, nullable=False, index=True, comment="Type of the entity (e.g., 'user', 'transaction', 'business')")
    
    score = Column(Float, nullable=False, comment="The calculated risk score (e.g., 0.0 to 1.0)")
    status = Column(Enum("PASS", "FLAGGED", "HIGH_RISK", name="risk_status"), nullable=False, default="FLAGGED", comment="The final risk status")
    reason = Column(Text, nullable=True, comment="Detailed reason for the score and status")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    logs = relationship("RiskAssessmentLog", back_populates="assessment", cascade="all, delete-orphan")

    # Indexes and Constraints
    __table_args__ = (
        Index("idx_entity_unique", entity_id, entity_type, unique=True),
    )

class RiskAssessmentLog(Base):
    """
    SQLAlchemy model for an activity log related to a Risk Assessment.
    """
    __tablename__ = "risk_assessment_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("risk_assessments.id"), nullable=False, index=True)
    
    action = Column(String, nullable=False, comment="The action performed (e.g., 'SCORE_UPDATED', 'MANUAL_REVIEW', 'STATUS_CHANGE')")
    details = Column(Text, nullable=True, comment="JSON string or text details about the action")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    assessment = relationship("RiskAssessment", back_populates="logs")

# --- Pydantic Schemas ---

class RiskAssessmentBase(BaseModel):
    """Base schema for Risk Assessment data."""
    entity_id: str = Field(..., description="ID of the entity being assessed.")
    entity_type: str = Field(..., description="Type of the entity (e.g., 'user', 'transaction').")
    score: float = Field(..., ge=0.0, le=1.0, description="The calculated risk score (0.0 to 1.0).")
    status: str = Field(..., description="The final risk status ('PASS', 'FLAGGED', 'HIGH_RISK').")
    reason: Optional[str] = Field(None, description="Detailed reason for the score and status.")

class RiskAssessmentCreate(RiskAssessmentBase):
    """Schema for creating a new Risk Assessment."""
    pass

class RiskAssessmentUpdate(BaseModel):
    """Schema for updating an existing Risk Assessment."""
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="The calculated risk score (0.0 to 1.0).")
    status: Optional[str] = Field(None, description="The final risk status ('PASS', 'FLAGGED', 'HIGH_RISK').")
    reason: Optional[str] = Field(None, description="Detailed reason for the score and status.")

class RiskAssessmentLogResponse(BaseModel):
    """Schema for reading a Risk Assessment Log."""
    id: uuid.UUID
    assessment_id: uuid.UUID
    action: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class RiskAssessmentResponse(RiskAssessmentBase):
    """Schema for reading a Risk Assessment record."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    logs: List[RiskAssessmentLogResponse] = Field(default_factory=list, description="Activity logs for this assessment.")

    class Config:
        from_attributes = True
