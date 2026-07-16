"""
Agent Scorecard - SQLAlchemy ORM Models and Pydantic Schemas
"""
import enum
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum as SAEnum,
    ForeignKey, Index, Numeric, String, Text, Integer, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class ScoreTier(str, enum.Enum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    UNRATED = "unrated"


class TrendDirection(str, enum.Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class RecommendationPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── ORM Models ───────────────────────────────────────────────────────────────

class AgentScorecard(Base):
    __tablename__ = "agent_scorecards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    computation_date = Column(Date, nullable=False, default=date.today)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Composite
    composite_score = Column(Numeric(7, 2), nullable=False, default=0)
    previous_composite_score = Column(Numeric(7, 2), nullable=True)
    tier = Column(SAEnum(ScoreTier), nullable=False, default=ScoreTier.UNRATED)
    trend = Column(SAEnum(TrendDirection), nullable=False, default=TrendDirection.STABLE)
    percentile_rank = Column(Numeric(5, 2), nullable=True)

    # Dimension 1: Transaction Performance (30%)
    txn_volume_score = Column(Numeric(5, 2), nullable=False, default=0)
    txn_value_score = Column(Numeric(5, 2), nullable=False, default=0)
    txn_success_rate_score = Column(Numeric(5, 2), nullable=False, default=0)
    txn_growth_rate_score = Column(Numeric(5, 2), nullable=False, default=0)
    txn_dimension_score = Column(Numeric(5, 2), nullable=False, default=0)

    # Dimension 2: Customer Experience (20%)
    customer_satisfaction_score = Column(Numeric(5, 2), nullable=False, default=0)
    complaint_resolution_score = Column(Numeric(5, 2), nullable=False, default=0)
    customer_retention_score = Column(Numeric(5, 2), nullable=False, default=0)
    new_customer_acquisition_score = Column(Numeric(5, 2), nullable=False, default=0)
    cx_dimension_score = Column(Numeric(5, 2), nullable=False, default=0)

    # Dimension 3: Compliance & Risk (25%)
    kyc_compliance_score = Column(Numeric(5, 2), nullable=False, default=0)
    aml_compliance_score = Column(Numeric(5, 2), nullable=False, default=0)
    fraud_incident_score = Column(Numeric(5, 2), nullable=False, default=0)
    geo_compliance_score = Column(Numeric(5, 2), nullable=False, default=0)
    transaction_limit_score = Column(Numeric(5, 2), nullable=False, default=0)
    compliance_dimension_score = Column(Numeric(5, 2), nullable=False, default=0)

    # Dimension 4: Training & Certification (15%)
    training_completion_score = Column(Numeric(5, 2), nullable=False, default=0)
    certification_score = Column(Numeric(5, 2), nullable=False, default=0)
    assessment_score = Column(Numeric(5, 2), nullable=False, default=0)
    training_dimension_score = Column(Numeric(5, 2), nullable=False, default=0)

    # Dimension 5: Network Growth (10%)
    sub_agent_count_score = Column(Numeric(5, 2), nullable=False, default=0)
    network_activation_score = Column(Numeric(5, 2), nullable=False, default=0)
    referral_score = Column(Numeric(5, 2), nullable=False, default=0)
    network_dimension_score = Column(Numeric(5, 2), nullable=False, default=0)

    # Raw metrics for auditability
    raw_metrics = Column(JSONB, nullable=False, default=dict)

    # Metadata
    computed_by = Column(String(100), nullable=False, default="scorecard-service")
    model_version = Column(String(20), nullable=False, default="1.0.0")
    is_published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    recommendations = relationship("ScorecardRecommendation", back_populates="scorecard", cascade="all, delete-orphan")


class ScorecardRecommendation(Base):
    __tablename__ = "scorecard_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scorecard_id = Column(UUID(as_uuid=True), ForeignKey("agent_scorecards.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    dimension = Column(String(50), nullable=False)
    priority = Column(SAEnum(RecommendationPriority), nullable=False, default=RecommendationPriority.MEDIUM)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)
    impact_score = Column(Numeric(5, 2), nullable=True)
    is_dismissed = Column(Boolean, nullable=False, default=False)
    dismissed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    scorecard = relationship("AgentScorecard", back_populates="recommendations")


class ScorecardHistory(Base):
    __tablename__ = "scorecard_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    score_date = Column(Date, nullable=False)
    composite_score = Column(Numeric(7, 2), nullable=False)
    tier = Column(SAEnum(ScoreTier), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ScorecardBenchmark(Base):
    __tablename__ = "scorecard_benchmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    benchmark_date = Column(Date, nullable=False, default=date.today)
    avg_score = Column(Numeric(7, 2), nullable=False)
    median_score = Column(Numeric(7, 2), nullable=False)
    p75_score = Column(Numeric(7, 2), nullable=False)
    p90_score = Column(Numeric(7, 2), nullable=False)
    platinum_count = Column(Integer, nullable=False, default=0)
    gold_count = Column(Integer, nullable=False, default=0)
    silver_count = Column(Integer, nullable=False, default=0)
    bronze_count = Column(Integer, nullable=False, default=0)
    unrated_count = Column(Integer, nullable=False, default=0)
    total_agents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class RawMetricsInput(BaseModel):
    """Raw input metrics used to compute the scorecard."""
    # Transaction metrics
    total_transactions: int = 0
    successful_transactions: int = 0
    total_transaction_value: float = 0.0
    prev_period_transactions: int = 0
    prev_period_value: float = 0.0

    # Customer metrics
    avg_customer_rating: float = 0.0        # 1-5 scale
    total_complaints: int = 0
    resolved_complaints: int = 0
    active_customers: int = 0
    new_customers: int = 0
    returning_customers: int = 0

    # Compliance metrics
    kyc_checks_passed: int = 0
    kyc_checks_total: int = 0
    aml_flags_raised: int = 0
    fraud_incidents: int = 0
    geo_violations: int = 0
    limit_breaches: int = 0

    # Training metrics
    training_modules_completed: int = 0
    training_modules_total: int = 0
    certifications_active: int = 0
    certifications_required: int = 0
    last_assessment_score: float = 0.0     # 0-100

    # Network metrics
    active_sub_agents: int = 0
    total_sub_agents: int = 0
    referrals_made: int = 0
    referrals_converted: int = 0


class ScorecardComputeRequest(BaseModel):
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    metrics: RawMetricsInput


class RecommendationOut(BaseModel):
    id: uuid.UUID
    dimension: str
    priority: RecommendationPriority
    title: str
    description: str
    action_url: Optional[str] = None
    impact_score: Optional[float] = None
    is_dismissed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ScorecardOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    computation_date: date
    period_start: datetime
    period_end: datetime

    composite_score: float
    previous_composite_score: Optional[float] = None
    score_change: Optional[float] = None
    tier: ScoreTier
    trend: TrendDirection
    percentile_rank: Optional[float] = None

    # Dimension scores
    txn_dimension_score: float
    cx_dimension_score: float
    compliance_dimension_score: float
    training_dimension_score: float
    network_dimension_score: float

    # Sub-scores
    txn_volume_score: float
    txn_value_score: float
    txn_success_rate_score: float
    txn_growth_rate_score: float

    customer_satisfaction_score: float
    complaint_resolution_score: float
    customer_retention_score: float
    new_customer_acquisition_score: float

    kyc_compliance_score: float
    aml_compliance_score: float
    fraud_incident_score: float
    geo_compliance_score: float
    transaction_limit_score: float

    training_completion_score: float
    certification_score: float
    assessment_score: float

    sub_agent_count_score: float
    network_activation_score: float
    referral_score: float

    raw_metrics: Dict[str, Any]
    model_version: str
    is_published: bool
    recommendations: List[RecommendationOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ScorecardSummary(BaseModel):
    """Lightweight summary for list views."""
    id: uuid.UUID
    agent_id: uuid.UUID
    computation_date: date
    composite_score: float
    tier: ScoreTier
    trend: TrendDirection
    percentile_rank: Optional[float] = None
    txn_dimension_score: float
    cx_dimension_score: float
    compliance_dimension_score: float
    training_dimension_score: float
    network_dimension_score: float

    class Config:
        from_attributes = True


class HistoryPoint(BaseModel):
    score_date: date
    composite_score: float
    tier: ScoreTier

    class Config:
        from_attributes = True


class BenchmarkOut(BaseModel):
    benchmark_date: date
    avg_score: float
    median_score: float
    p75_score: float
    p90_score: float
    tier_distribution: Dict[str, int]
    total_agents: int

    class Config:
        from_attributes = True


class DismissRecommendationRequest(BaseModel):
    recommendation_id: uuid.UUID


class NetworkLeaderboardEntry(BaseModel):
    agent_id: uuid.UUID
    composite_score: float
    tier: ScoreTier
    rank: int
    percentile_rank: float
