"""
Wallet Service with Dapr Integration
Remittance Platform V11.0

Features:
- Get wallet balance
- Update wallet balance
- Transaction history
- Dapr state management
- Dapr pub/sub
- Permify authorization

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

sys.path.insert(0, "/home/ubuntu/remittance-platform/backend/python-services/shared")

from dapr_client import AgentBankingDaprClient
from permify_client import PermifyClient
from keycloak_auth import get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wallet Service", version="1.0.0")

dapr_client = AgentBankingDaprClient()
permify_client = PermifyClient()


class BalanceRequest(BaseModel):
    user_id: str


class UpdateBalanceRequest(BaseModel):
    user_id: str
    amount: float
    transaction_id: str


@app.get("/get-balance")
async def get_balance(user_id: str, current_user: Dict = Depends(get_current_user)):
    """Get wallet balance."""
    # Check permission
    allowed = await permify_client.check_permission(
        entity="wallet",
        entity_id=f"wallet-{user_id}",
        permission="view_balance",
        subject=f"user:{current_user['sub']}"
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Get balance from state
    wallet = await dapr_client.get_state(f"wallet:{user_id}")
    
    if not wallet:
        wallet = {"user_id": user_id, "balance": 0.0, "updated_at": datetime.utcnow().isoformat()}
        await dapr_client.save_state(f"wallet:{user_id}", wallet)
    
    return {"balance": wallet.get("balance", 0.0)}


@app.post("/update-balance")
async def update_balance(request: UpdateBalanceRequest):
    """Update wallet balance."""
    # Get current balance
    wallet = await dapr_client.get_state(f"wallet:{request.user_id}")
    
    if not wallet:
        wallet = {"user_id": request.user_id, "balance": 0.0}
    
    # Update balance
    new_balance = wallet["balance"] + request.amount
    
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    wallet["balance"] = new_balance
    wallet["updated_at"] = datetime.utcnow().isoformat()
    wallet["last_transaction_id"] = request.transaction_id
    
    # Save state
    await dapr_client.save_state(f"wallet:{request.user_id}", wallet, consistency="strong")
    
    # Publish event
    await dapr_client.publish_event(
        topic="wallets.updated",
        data={
            "user_id": request.user_id,
            "balance": new_balance,
            "amount": request.amount,
            "transaction_id": request.transaction_id
        }
    )
    
    logger.info(f"Wallet updated: {request.user_id}, new balance: {new_balance}")
    
    return {"balance": new_balance, "status": "updated"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "wallet-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
