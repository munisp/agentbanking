from utils import (
    create_logger,
    get_config,
    PubsubTopics,
    CurrencyEnum,
    CurrencyLedgerId,
    TransactionStatus,
)
from utils.coa_client import CoAClient
from adapters import (
    TigerBeetleAdapter,
    AccountServiceAdapter,
    LoanServiceAdapter,
    LpoServiceAdapter,
    InsuranceServiceAdapter,
    SupplyChainServiceAdapter,
    AuditServiceAdapter,
    ExchangeRateServiceAdapter,
    FraudEngineAdapter,
    CommissionServiceAdapter,
    ComplianceServiceAdapter,
    LoyaltyServiceAdapter,
    NetworkOpsAdapter,
)
from schemas import (
    InitiatePaymentSchema,
    InitiateDepositSchema,
    InitiateDepositWithAccountNumberSchema,
    TransactionEventSchema,
    InitiateLoanPaymentSchema,
    InitiateLPOPaymentSchema,
    Context,
    InitiateSystemPayoutSchema,
    InitiateInsurancePremiumPaymentSchema,
    SupplyChainFinancingPaymentSchema,
    AuditEventSchema,
)
from events import publish_transaction_event
from datetime import datetime, timezone
from typing import Any, Optional
import json
import uuid
from fastapi import HTTPException
from dapr.clients import DaprClient
from adapters import payment_rails_connector_adapter
from schemas.payment import ExternalTransferSchema, ExternalDebitSchema

logger = create_logger(__name__)

_tigerbeetle_adapter = TigerBeetleAdapter()

_dapr_client = None


def _get_dapr_client() -> DaprClient:
    global _dapr_client
    if _dapr_client is None:
        _dapr_client = DaprClient()
    return _dapr_client
