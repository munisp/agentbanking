"""Investment Service Models"""
from datetime import datetime
from typing import Optional

class Investment:
    def __init__(self, id: str, user_id: str, product_id: str, amount: float,
                 currency: str = "NGN", status: str = "active"):
        self.id = id
        self.user_id = user_id
        self.product_id = product_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.invested_at: str = datetime.utcnow().isoformat()
        self.returns: float = 0.0
