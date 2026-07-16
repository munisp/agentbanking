import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship, sessionmaker, DeclarativeBase
from pydantic import BaseModel, Field

# --- Database Setup (DeclarativeBase) ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and primary key column.
    """
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __abstract__ = True

# --- SQLAlchemy Models ---

class HybridEngineResult(Base):
    """
    Represents the result of a single run of the hybrid fraud detection engine.

    This model stores the combined score, the decision made, and details
    from both the rule-based and machine learning components.
    """
    __tablename__ = "hybrid_engine_results"

    # Core fields
    transaction_id = Column(String, index=True, nullable=False, unique=True)
    overall_score = Column(Float, index=True, nullable=False, doc="The final combined fraud score (0.0 to 1.0)")
    decision = Column(String, index=True, nullable=False, doc="The final decision: 'ALLOW', 'REVIEW', or 'DENY'")
    is_fraud = Column(Boolean, default=False, nullable=False, doc="Final determination after manual review, if applicable")

    # Component scores
    rule_score = Column(Float, nullable=False, doc="Score from the rule-based engine")
    ml_score = Column(Float, nullable=False, doc="Score from the machine learning model")
    gnn_score = Column(Float, nullable=True, doc="Score from the Graph Neural Network model, if used")

    # Details
    rule_hits = Column(Text, nullable=True, doc="JSON string or text detailing which rules were triggered")
    model_version = Column(String, nullable=False, doc="Version of the ML/GNN model used")
    
    # Relationships
    log_entries = relationship("HybridEngineLog", back_populates="result", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_result_transaction_decision", transaction_id, decision),
    )

class HybridEngineLog(Base):
    """
    Activity log for the hybrid engine result, tracking state changes or review actions.
    """
    __tablename__ = "hybrid_engine_logs"

    result_id = Column(Integer, ForeignKey("hybrid_engine_results.id"), nullable=False, index=True)
    action = Column(String, nullable=False, doc="Type of action: 'CREATED', 'UPDATED', 'REVIEWED', 'MARKED_FRAUD'")
    details = Column(Text, nullable=True, doc="Detailed description of the action or change")
    
    # Relationships
    result = relationship("HybridEngineResult", back_populates="log_entries")

    __table_args__ = (
        Index("ix_log_result_action", result_id, action),
    )

# --- Pydantic Schemas ---

# Base Schemas
class HybridEngineResultBase(BaseModel):
    transaction_id: str = Field(..., example="txn_1A2B3C4D5E", description="Unique identifier for the transaction.")
    overall_score: float = Field(..., ge=0.0, le=1.0, example=0.85, description="The final combined fraud score (0.0 to 1.0).")
    decision: str = Field(..., example="REVIEW", description="The final decision: 'ALLOW', 'REVIEW', or 'DENY'.")
    rule_score: float = Field(..., ge=0.0, le=1.0, example=0.7, description="Score from the rule-based engine.")
    ml_score: float = Field(..., ge=0.0, le=1.0, example=0.9, description="Score from the machine learning model.")
    gnn_score: Optional[float] = Field(None, ge=0.0, le=1.0, example=0.95, description="Score from the Graph Neural Network model, if used.")
    rule_hits: Optional[str] = Field(None, example='["Rule_Velocity_Check", "Rule_Geo_Mismatch"]', description="Details on which rules were triggered.")
    model_version: str = Field(..., example="v2.1.0", description="Version of the ML/GNN model used.")

class HybridEngineLogBase(BaseModel):
    action: str = Field(..., example="REVIEWED", description="Type of action: 'CREATED', 'UPDATED', 'REVIEWED', 'MARKED_FRAUD'.")
    details: Optional[str] = Field(None, example="Manual review completed by Analyst X. Decision changed to DENY.", description="Detailed description of the action or change.")

# Create Schemas (for POST requests)
class HybridEngineResultCreate(HybridEngineResultBase):
    """Schema for creating a new HybridEngineResult."""
    pass

class HybridEngineLogCreate(HybridEngineLogBase):
    """Schema for creating a new log entry."""
    pass

# Update Schemas (for PUT/PATCH requests)
class HybridEngineResultUpdate(BaseModel):
    """Schema for updating an existing HybridEngineResult."""
    overall_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="The final combined fraud score (0.0 to 1.0).")
    decision: Optional[str] = Field(None, description="The final decision: 'ALLOW', 'REVIEW', or 'DENY'.")
    is_fraud: Optional[bool] = Field(None, description="Final determination after manual review, if applicable.")
    rule_hits: Optional[str] = Field(None, description="Details on which rules were triggered.")
    
# Response Schemas (for GET requests)
class HybridEngineLogResponse(HybridEngineLogBase):
    id: int
    created_at: datetime.datetime
    result_id: int

    class Config:
        from_attributes = True

class HybridEngineResultResponse(HybridEngineResultBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_fraud: bool
    log_entries: List[HybridEngineLogResponse] = []

    class Config:
        from_attributes = True
