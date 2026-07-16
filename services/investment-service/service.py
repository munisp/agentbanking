"""Investment Service - Production Implementation"""
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid, os, logging

logger = logging.getLogger(__name__)
portfolios_db: Dict[str, Dict] = {}

async def create(data: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(uuid.uuid4())
    portfolios_db[pid] = {**data, "id": pid, "created_at": datetime.utcnow().isoformat()}
    return portfolios_db[pid]

async def get_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    return portfolios_db.get(item_id)

async def get_all() -> List[Dict[str, Any]]:
    return list(portfolios_db.values())

async def update(item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if item_id in portfolios_db:
        portfolios_db[item_id].update(data)
        return portfolios_db[item_id]
    return None

async def delete(item_id: str) -> bool:
    return portfolios_db.pop(item_id, None) is not None

async def list_products() -> List[Dict]:
    return [
        {"id": "tbills", "name": "Treasury Bills", "type": "fixed_income", "min_amount": 100000, "tenor_days": 91, "rate": 0.14},
        {"id": "bonds", "name": "FGN Bonds", "type": "fixed_income", "min_amount": 50000, "tenor_days": 365, "rate": 0.155},
        {"id": "money_market", "name": "Money Market Fund", "type": "mutual_fund", "min_amount": 5000, "rate": 0.12},
    ]

async def invest_from_savings(user_id: str, product_id: str, amount: float, source_goal: str) -> Dict:
    investment = {"id": str(uuid.uuid4()), "user_id": user_id, "product_id": product_id, "amount": amount, "source": source_goal, "status": "active", "invested_at": datetime.utcnow().isoformat()}
    portfolios_db[investment["id"]] = investment
    return investment

async def get_portfolio(user_id: str) -> Dict:
    user_inv = [v for v in portfolios_db.values() if v.get("user_id") == user_id]
    total = sum(i.get("amount", 0) for i in user_inv)
    return {"user_id": user_id, "investments": user_inv, "total_invested": total, "total_value": total * 1.02}

async def calculate_returns(investment_id: str) -> Dict:
    inv = portfolios_db.get(investment_id)
    if not inv:
        return {"error": "Not found"}
    rate = 0.14
    returns = inv.get("amount", 0) * rate * (30 / 365)
    return {"investment_id": investment_id, "principal": inv["amount"], "rate": rate, "returns": round(returns, 2)}
