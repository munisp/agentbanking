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
    