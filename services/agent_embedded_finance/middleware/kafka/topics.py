"""
Agent Embedded Finance — Kafka Topics & Event Schemas
All events published/consumed by the Agent Embedded Finance service.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
import json
import uuid


class FinanceTopics(str, Enum):
    # Published by this service
    LOAN_APPLICATION_SUBMITTED = "agent.finance.loan_application_submitted"
    LOAN_APPROVED              = "agent.finance.loan_approved"
    LOAN_REJECTED              = "agent.finance.loan_rejected"
    LOAN_DISBURSED             = "agent.finance.loan_disbursed"
    LOAN_REPAID                = "agent.finance.loan_repaid"
    LOAN_OVERDUE               = "agent.finance.loan_overdue"
    LOAN_SETTLED               = "agent.finance.loan_settled"
    BNPL_ORDER_CREATED         = "agent.finance.bnpl_order_created"
    BNPL_INSTALLMENT_PAID      = "agent.finance.bnpl_installment_paid"
    BNPL_ORDER_COMPLETED       = "agent.finance.bnpl_order_completed"
    CREDIT_LIMIT_UPDATED       = "agent.finance.credit_limit_updated"

    # Consumed by this service
    SCORECARD_COMPUTED         = "agent.scorecard.computed"
    SCORECARD_TIER_CHANGED     = "agent.scorecard.tier_changed"
    AGENT_KYC_UPDATED          = "agent.kyc.updated"
    TRANSACTION_COMPLETED      = "transaction.completed"


@dataclass
class LoanDisbursedEvent:
    event_id: str
    event_type: str
    agent_id: str
    tenant_id: str
    loan_id: str
    application_id: str
    product_type: str
    principal_amount: float
    interest_rate: float
    tenure_days: int
    disbursed_at: str
    source_service: str = "agent-embedded-finance"

    @classmethod
    def create(cls, agent_id: str, tenant_id: str, loan_id: str,
               application_id: str, product_type: str, principal_amount: float,
               interest_rate: float, tenure_days: int) -> "LoanDisbursedEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=FinanceTopics.LOAN_DISBURSED,
            agent_id=agent_id,
            tenant_id=tenant_id,
            loan_id=loan_id,
            application_id=application_id,
            product_type=product_type,
            principal_amount=principal_amount,
            interest_rate=interest_rate,
            tenure_days=tenure_days,
            disbursed_at=datetime.utcnow().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class LoanRepaidEvent:
    event_id: str
    event_type: str
    agent_id: str
    tenant_id: str
    loan_id: str
    amount_paid: float
    outstanding_balance: float
    is_settled: bool
    repaid_at: str
    source_service: str = "agent-embedded-finance"

    @classmethod
    def create(cls, agent_id: str, tenant_id: str, loan_id: str,
               amount_paid: float, outstanding_balance: float,
               is_settled: bool) -> "LoanRepaidEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=FinanceTopics.LOAN_SETTLED if is_settled else FinanceTopics.LOAN_REPAID,
            agent_id=agent_id,
            tenant_id=tenant_id,
            loan_id=loan_id,
            amount_paid=amount_paid,
            outstanding_balance=outstanding_balance,
            is_settled=is_settled,
            repaid_at=datetime.utcnow().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class CreditLimitUpdatedEvent:
    event_id: str
    event_type: str
    agent_id: str
    tenant_id: str
    old_limit: float
    new_limit: float
    reason: str
    updated_at: str
    source_service: str = "agent-embedded-finance"

    @classmethod
    def create(cls, agent_id: str, tenant_id: str, old_limit: float,
               new_limit: float, reason: str) -> "CreditLimitUpdatedEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=FinanceTopics.CREDIT_LIMIT_UPDATED,
            agent_id=agent_id,
            tenant_id=tenant_id,
            old_limit=old_limit,
            new_limit=new_limit,
            reason=reason,
            updated_at=datetime.utcnow().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
