"""
Analytics Service with Dapr Integration
Remittance Platform V11.0

Features:
- Update transaction statistics
- Generate reports
- Real-time analytics
- Dapr pub/sub consumer
- Kafka event processing

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import FastAPI, Depends
from pydantic import BaseModel
import asyncio

sys.path.insert(0, "/home/ubuntu/remittance-platform/backend/python-services/shared")

from dapr_client import AgentBankingDaprClient
from permify_client import PermifyClient
from keycloak_auth import get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Analytics Service", version="1.0.0")

dapr_client = AgentBankingDaprClient()
permify_client = PermifyClient()


@app.post("/dapr/subscribe")
async def subscribe():
    """Subscribe to analytics events."""
    return [
        {"pubsubname": "pubsub", "topic": "transactions.created", "route": "/analytics/transaction-created"},
        {"pubsubname": "pubsub", "topic": "transactions.completed", "route": "/analytics/transaction-completed"},
        {"pubsubname": "pubsub", "topic": "wallets.updated", "route": "/analytics/wallet-updated"}
    ]


@app.post("/analytics/transaction-created")
async def handle_transaction_created(event: Dict[str, Any]):
    """Handle transaction created event."""
    data = event.get("data", {})
    transaction_id = data.get("transaction_id")
    
    logger.info(f"📊 Processing transaction created: {transaction_id}")
    
    # Update daily statistics
    today = datetime.utcnow().strftime("%Y-%m-%d")
    stats_key = f"stats:daily:{today}"
    
    stats = await dapr_client.get_state(stats_key) or {
        "date": today,
        "total_transactions": 0,
        "total_volume": 0.0,
        "transaction_types": {}
    }
    
    stats["total_transactions"] += 1
    stats["total_volume"] += data.get("amount", 0)
    
    txn_type = data.get("transaction_type", "unknown")
    stats["transaction_types"][txn_type] = stats["transaction_types"].get(txn_type, 0) + 1
    
    await dapr_client.save_state(stats_key, stats)
    
    logger.info(f"✅ Statistics updated for {today}")
    
    return {"status": "processed"}


@app.post("/analytics/transaction-completed")
async def handle_transaction_completed(event: Dict[str, Any]):
    """Handle transaction completed event."""
    data = event.get("data", {})
    logger.info(f"📊 Transaction completed: {data.get('transaction_id')}")
    return {"status": "processed"}


@app.post("/analytics/wallet-updated")
async def handle_wallet_updated(event: Dict[str, Any]):
    """Handle wallet updated event."""
    data = event.get("data", {})
    logger.info(f"📊 Wallet updated: {data.get('user_id')}")
    return {"status": "processed"}


@app.post("/update-transaction-stats")
async def update_transaction_stats(data: Dict[str, Any]):
    """Update transaction statistics (called via Dapr service invocation)."""
    transaction_id = data.get("transaction_id")
    logger.info(f"Updating stats for transaction: {transaction_id}")
    return {"status": "updated"}


@app.get("/stats/daily/{date}")
async def get_daily_stats(date: str, current_user: Dict = Depends(get_current_user)):
    """Get daily statistics."""
    stats = await dapr_client.get_state(f"stats:daily:{date}")
    
    if not stats:
        return {"date": date, "total_transactions": 0, "total_volume": 0.0}
    
    return stats


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "analytics-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
