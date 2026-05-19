import datetime
import enum
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Index
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field
from pydantic.types import UUID4

# --- SQLAlchemy Base and Models ---

Base = declarative_base()

class ScoreStatus(enum.Enum):
    """
    Enum for the status of a credit score calculation.
    """
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECALCULATED = "RECALCULATED"

class CreditScore(Base):
    """
    Main model for storing credit scoring results for a user or entity.
    """
    __tablename__ = "credit_scores"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(UUID4, unique=True, index=True, nullable=False, doc="Unique identifier for the entity (e.g., user, company)")
    score_value = Column(Integer, nullable=False, doc="The calculated credit score (e.g., FICO-like score from 300 to 850)")
    score_model_version = Column(String(50), nullable=False, doc="Version of the scoring model used")
    status = Column(Enum(ScoreStatus), default=ScoreStatus.COMPLETED, nullable=False, doc="Current status of the score")
    risk_level = Column(String(50), nullable=False, doc="Categorical risk level (e.g., 'Low', 'Medium', 'High')")
    score_factors = Column(String, nullable=True, doc="JSON string or text of key factors influencing the score")
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to activity log
    activity_logs = relationship("CreditScoreActivityLog", back_populates="credit_score")

    __table_args__ = (
        Index("idx_credit_score_entity_status", "entity_id", "status"),
    )

class CreditScoreActivityLog(Base):
    """
    Activity log for all operations and changes related to a credit score.
    """
    __tablename__ = "credit_score_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    credit_score_id = Column(Integer, ForeignKey("credit_scores.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    activity_type = Column(String(100), nullable=False, doc="Type of activity (e.g., 'SCORE_CALCULATED', 'SCORE_UPDATED', 'DATA_REFRESHED')")
    details = Column(String, nullable=True, doc="Detailed description or JSON payload of the activity")
    performed_by = Column(String(100), nullable=True, doc="User or system component that performed the action")

    # Relationship back to the CreditScore
    credit_score = relationship("CreditScore", back_populates="activity_logs")

    __table_args__ = (
        Index("idx_activity_log_score_id_timestamp", "credit_score_id", "timestamp"),
    )

# --- Pydantic Schemas ---

# Base Schema for Activity Log
class CreditScoreActivityLogBase(BaseModel):
    """Base Pydantic schema for CreditScoreActivityLog."""
    activity_type: str = Field(..., description="Type of activity (e.g., 'SCORE_CALCULATED', 'SCORE_UPDATED')")
    details: Optional[str] = Field(None, description="Detailed description or JSON payload of the activity")
    performed_by: Optional[str] = Field(None, description="User or system component that performed the action")

# Response Schema for Activity Log
class CreditScoreActivityLogResponse(CreditScoreActivityLogBase):
    """Response Pydantic schema for CreditScoreActivityLog."""
    id: int
    credit_score_id: int
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

# Base Schema for Credit Score
class CreditScoreBase(BaseModel):
    """Base Pydantic schema for CreditScore."""
    entity_id: UUID4 = Field(..., description="Unique identifier for the entity (e.g., user, company)")
    score_value: int = Field(..., ge=300, le=850, description="The calculated credit score (300-850)")
    score_model_version: str = Field(..., description="Version of the scoring model used")
    status: ScoreStatus = Field(ScoreStatus.COMPLETED, description="Current status of the score")
    risk_level: str = Field(..., description="Categorical risk level (e.g., 'Low', 'Medium', 'High')")
    score_factors: Optional[str] = Field(None, description="JSON string or text of key factors influencing the score")

# Create Schema for Credit Score
class CreditScoreCreate(CreditScoreBase):
    """Pydantic schema for creating a new CreditScore record."""
    pass

# Update Schema for Credit Score
class CreditScoreUpdate(BaseModel):
    """Pydantic schema for updating an existing CreditScore record."""
    score_value: Optional[int] = Field(None, ge=300, le=850, description="The calculated credit score (300-850)")
    score_model_version: Optional[str] = Field(None, description="Version of the scoring model used")
    status: Optional[ScoreStatus] = Field(None, description="Current status of the score")
    risk_level: Optional[str] = Field(None, description="Categorical risk level (e.g., 'Low', 'Medium', 'High')")
    score_factors: Optional[str] = Field(None, description="JSON string or text of key factors influencing the score")

# Response Schema for Credit Score
class CreditScoreResponse(CreditScoreBase):
    """Response Pydantic schema for CreditScore, including read-only fields."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Include the activity logs in the response
    activity_logs: List[CreditScoreActivityLogResponse] = Field([], description="List of activities related to this credit score")

    class Config:
        from_attributes = True
        use_enum_values = True
