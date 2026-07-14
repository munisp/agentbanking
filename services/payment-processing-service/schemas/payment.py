import datetime
from pydantic import BaseModel
from utils import TransactionStatus, CurrencyEnum
from typing import Optional


class TransactionEventSchema(BaseModel):
    transaction_id: str
    payer: str
    payee: str
    amount: str
    status: TransactionStatus
    currency: CurrencyEnum
    completed_at: Optional[datetime.datetime]
    note: Optional[str]
    tag: Optional[str]
    tenant_id: str
    ledger_id: str


class InitiatePaymentSchema(BaseModel):
    payer: int | str
    payee: int | str
    payee_tenant_id: Optional[str] = None
    payee_bank_code: Optional[int] = None
    amount: float
    note: str
    pin: str


class InitiateSystemPayoutSchema(BaseModel):
    recipient: str
    amount: float
    note: str


class InitiateDepositSchema(BaseModel):
    recipient: int
    amount: float
    note: str


class InitiateDepositWithAccountNumberSchema(BaseModel):
    recipient_account_number: str
    amount: float
    note: str


class InitiateLoanPaymentSchema(BaseModel):
    loan_id: str
    payer: int
    amount: float
    pin: str


class InitiateLPOPaymentSchema(BaseModel):
    lpo_id: str
    payer: int
    pin: str


class InitiateInsurancePremiumPaymentSchema(BaseModel):
    insurance_policy_id: str
    payer: int
    pin: str


class SupplyChainFinancingPaymentSchema(BaseModel):
    financing_id: str
    payer: int
    pin: str


class ExternalParty(BaseModel):
    idType: str
    idValue: str


class ExternalAmount(BaseModel):
    currency: str
    amount: float


class ExternalTransferSchema(BaseModel):
    transactionId: str
    party: ExternalParty
    amount: ExternalAmount
    metadata: Optional[dict] = None


class ExternalDebitSchema(BaseModel):
    transactionId: str
    payer: str
    amount: ExternalAmount
    metadata: Optional[dict] = None
