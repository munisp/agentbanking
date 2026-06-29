"""
Agent Scorecard — Kafka Topics & Event Schemas
All events published/consumed by the Agent Scorecard service.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
import json
import uuid

# ── Topic Names ────────────────────────────────────────────────────────────────
class ScorecardTopics(str, Enum):
    # Published by this service
    SCORECARD_COMPUTED       = "agent.scorecard.computed"
    SCORECARD_TIER_CHANGED   = "agent.scorecard.tier_changed"
    RECOMMENDATION_GENERATED = "agent.scorecard.recommendation_generated"
    LEADERBOARD_UPDATED      = "agent.scorecard.leaderboard_updated"

    # Consumed by this service
    TRANSACTION_COMPLETED    = "transaction.completed"
    AGENT_KYC_UPDATED        = "agent.kyc.updated"
    AGENT_TRAINING_COMPLETED = "agent.training.completed"
    FRAUD_ALERT_RAISED       = "fraud.alert.raised"
    COMMISSION_SETTLED       = "agent.commission.settled"
    LOAN_DISBURSED           = "agent.finance.loan_disbursed"
    LOAN_REPAID              = "agent.finance.loan_repaid"


# ── Event Payloads ─────────────────────────────────────────────────────────────
@dataclass
class ScorecardComputedEvent:
    event_id: str
    event_type: str
    agent_id: str
    tenant_id: str
    composite_score: float
    tier: str
    previous_tier: Optional[str]
    trend: str
    score_change: float
    computed_at: str
    source_service: str = "agent-scorecard"

    @classmethod
    def create(cls, agent_id: str, tenant_id: str, composite_score: float,
               tier: str, previous_tier: Optional[str], trend: str, score_change: float) -> "ScorecardComputedEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=ScorecardTopics.SCORECARD_COMPUTED,
            agent_id=agent_id,
            tenant_id=tenant_id,
            composite_score=composite_score,
            tier=tier,
            previous_tier=previous_tier,
            trend=trend,
            score_change=score_change,
            computed_at=datetime.utcnow().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class TierChangedEvent:
    event_id: str
    event_type: str
    agent_id: str
    tenant_id: str
    old_tier: str
    new_tier: str
    composite_score: float
    changed_at: str
    source_service: str = "agent-scorecard"

    @classmethod
    def create(cls, agent_id: str, tenant_id: str, old_tier: str,
               new_tier: str, composite_score: float) -> "TierChangedEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=ScorecardTopics.SCORECARD_TIER_CHANGED,
            agent_id=agent_id,
            tenant_id=tenant_id,
            old_tier=old_tier,
            new_tier=new_tier,
            composite_score=composite_score,
            changed_at=datetime.utcnow().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
