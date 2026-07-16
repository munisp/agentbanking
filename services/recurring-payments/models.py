"""Recurring Payments Models"""
from datetime import datetime
from typing import Optional

class RecurringPayment:
    def __init__(self, id: str, user_id: str, amount: float, currency: str,
                 recipient: str, frequency: str, start_date: str, status: str = "active"):
        self.id = id
        self.user_id = user_id
        self.amount = amount
        self.currency = currency
        self.recipient = recipient
        self.frequency = frequency
        self.start_date = start_date
        self.status = status
        self.next_execution: Optional[str] = start_date
        self.execution_count: int = 0
        self.last_executed: Optional[str] = None
        self.created_at: str = datetime.utcnow().isoformat()
