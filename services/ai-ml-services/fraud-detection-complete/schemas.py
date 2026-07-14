from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, conint, constr
from enum import Enum as PyEnum

# --- Enums Schemas ---

class TransactionStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"

class FraudDecision(str, PyEnum):
    SAFE = "SAFE"
    REVIEW = "REVIEW"
    FRAUD = "FRAUD"

class RuleStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

# --- Base Schemas ---

class TenantBase(BaseModel):
    name: constr(min_length=1, max_length=100) = Field(..., example="AcmeCorp")
    is_active: Optional[bool] = Field(True, example=True)

class TenantCreate(TenantBase):
    pass

class TenantUpdate(TenantBase):
    name: Optional[constr(min_length=1, max_length=100)] = Field(None, example="AcmeCorp")
    is_active: Optional[bool] = Field(None, example=True)

class Tenant(TenantBase):
    id: int = Field(..., example=1)
    created_at: datetime = Field(..., example="2025-10-27T10:00:00")

    class Config:
        from_attributes = True

# --- Transaction Schemas ---

class TransactionBase(BaseModel):
    tenant_id: conint(ge=1) = Field(..., example=1, description="The ID of the tenant performing the transaction.")
    amount: float = Field(..., gt=0, example=150.75, description="Transaction amount.")
    currency: constr(min_length=3, max_length=3) = Field(..., example="USD", description="Currency code (e.g., USD, EUR).")
    user_id: constr(min_length=1, max_length=50) = Field(..., example="user_456", description="Unique identifier for the user.")
    merchant_id: constr(min_length=1, max_length=50) = Field(..., example="merch_123", description="Unique identifier for the merchant.")
    ip_address: constr(min_length=7, max_length=45) = Field(..., example="192.168.1.1", description="IP address of the transaction origin.")

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    status: Optional[TransactionStatus] = Field(None, example=TransactionStatus.APPROVED)

class Transaction(TransactionBase):
    id: int = Field(..., example=101)
    status: TransactionStatus = Field(TransactionStatus.PENDING, example=TransactionStatus.PENDING)
    created_at: datetime = Field(..., example="2025-10-27T10:00:00")

    class Config:
        from_attributes = True

# --- FraudRule Schemas ---

class FraudRuleBase(BaseModel):
    tenant_id: conint(ge=1) = Field(..., example=1)
    name: constr(min_length=1, max_length=100) = Field(..., example="HighValueTransaction")
    description: Optional[str] = Field(None, example="Flag transactions over $1000.")
    rule_expression: str = Field(..., example="amount > 1000 AND currency == 'USD'")
    severity_score: conint(ge=1, le=100) = Field(..., example=80, description="Score from 1 (low) to 100 (high).")
    status: Optional[RuleStatus] = Field(RuleStatus.ACTIVE, example=RuleStatus.ACTIVE)

class FraudRuleCreate(FraudRuleBase):
    pass

class FraudRuleUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = Field(None, example="HighValueTransactionV2")
    description: Optional[str] = Field(None, example="Flag transactions over $1000 from new users.")
    rule_expression: Optional[str] = Field(None, example="amount > 1000 AND currency == 'USD' AND user_age_days < 30")
    severity_score: Optional[conint(ge=1, le=100)] = Field(None, example=90)
    status: Optional[RuleStatus] = Field(None, example=RuleStatus.INACTIVE)

class FraudRule(FraudRuleBase):
    id: int = Field(..., example=5)
    created_at: datetime = Field(..., example="2025-10-27T10:00:00")
    updated_at: datetime = Field(..., example="2025-10-27T11:00:00")

    class Config:
        from_attributes = True

# --- FraudReport Schemas ---

class FraudReportBase(BaseModel):
    transaction_id: conint(ge=1) = Field(..., example=101)
    rule_id: Optional[conint(ge=1)] = Field(None, example=5, description="ID of the rule that triggered the report, if applicable.")
    decision: FraudDecision = Field(..., example=FraudDecision.FRAUD)
    score: float = Field(..., ge=0.0, le=100.0, example=95.5, description="Final fraud score.")
    reason: Optional[str] = Field(None, example="High value transaction triggered rule 5.")
    model_version: Optional[constr(max_length=50)] = Field(None, example="v1.2.3", description="Version of the ML model used for scoring.")

class FraudReportCreate(FraudReportBase):
    pass

class FraudReport(FraudReportBase):
    id: int = Field(..., example=201)
    created_at: datetime = Field(..., example="2025-10-27T10:00:00")

    class Config:
        from_attributes = True

# --- Response Schemas ---

class TransactionWithReports(Transaction):
    reports: List[FraudReport] = Field([], description="List of fraud reports associated with this transaction.")

class TenantWithRules(Tenant):
    rules: List[FraudRule] = Field([], description="List of fraud rules associated with this tenant.")

class HTTPError(BaseModel):
    detail: str = Field(..., example="Item not found")