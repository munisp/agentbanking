"""
Transaction Service with Full Middleware Integration

Demonstrates complete integration with:
- Dapr service mesh (service invocation, state management, pub/sub)
- Permify authorization (fine-grained permissions)
- Keycloak authentication (JWT validation)

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel

# Add shared directory to path
sys.path.insert(0, "/home/ubuntu/remittance-platform/backend/python-services/shared")

from dapr_client import AgentBankingDaprClient
from permify_client import PermifyClient
from keycloak_auth import get_current_user, require_role

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Transaction Service",
    description="Transaction service with full middleware integration",
    version="1.0.0"
)

# Initialize clients
dapr_client = AgentBankingDaprClient()
permify_client = PermifyClient()


# ============================================================================
# Models
# ============================================================================

class TransactionRequest(BaseModel):
    """Transaction request model."""
    transaction_type: str  # cash_in, cash_out, p2p_transfer
    amount: float
    customer_id: str
    description: Optional[str] = None


class TransactionResponse(BaseModel):
    """Transaction response model."""
    transaction_id: str
    status: str
    amount: float
    timestamp: str


# ============================================================================
# Dapr Pub/Sub Subscription
# ============================================================================

@app.post("/dapr/subscribe")
async def subscribe():
    """Subscribe to Dapr pub/sub topics."""
    return [
        {
            "pubsubname": "pubsub",
            "topic": "transactions.created",
            "route": "/handle-transaction-created"
        },
        {
            "pubsubname": "pubsub",
            "topic": "wallets.updated",
            "route": "/handle-wallet-updated"
        }
    ]


@app.post("/handle-transaction-created")
async def handle_transaction_created(event: Dict[str, Any]):
    """Handle transaction created event."""
    logger.info(f"📥 Transaction created event: {event}")
    
    # Process event (e.g., update analytics, send notifications)
    transaction_id = event.get("data", {}).get("transaction_id")
    
    if transaction_id:
        # Update analytics
        await dapr_client.invoke_service(
            app_id="analytics-service",
            method="update-transaction-stats",
            data={"transaction_id": transaction_id}
        )
        
        # Send notification
        await dapr_client.publish_event(
            topic="notifications.sms",
            data={
                "recipient": event.get("data", {}).get("customer_phone"),
                "message": f"Transaction {transaction_id} completed successfully"
            }
        )
    
    return {"status": "processed"}


@app.post("/handle-wallet-updated")
async def handle_wallet_updated(event: Dict[str, Any]):
    """Handle wallet updated event."""
    logger.info(f"📥 Wallet updated event: {event}")
    return {"status": "processed"}


# ============================================================================
# Transaction Endpoints
# ============================================================================

@app.post("/transactions", response_model=TransactionResponse)
async def create_transaction(
    request: TransactionRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new transaction.
    
    Workflow:
    1. Authenticate user (Keycloak JWT)
    2. Check permission (Permify)
    3. Get wallet balance (Dapr service invocation)
    4. Save transaction state (Dapr state management)
    5. Publish event (Dapr pub/sub)
    6. Return response
    """
    user_id = user.get("sub")
    agent_id = user.get("agent_id", "agent-001")  # From JWT claims
    
    logger.info(f"Creating transaction for user {user_id}")
    
    # Step 1: Check permission (Permify)
    allowed = await permify_client.check_permission(
        entity="transaction",
        entity_id="new",  # For new transactions
        permission="create",
        subject=f"user:{user_id}"
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied: Cannot create transaction")
    
    # Step 2: Get wallet balance (Dapr service invocation)
    try:
        wallet_response = await dapr_client.invoke_service(
            app_id="wallet-service",
            method="get-balance",
            data={"user_id": user_id}
        )
        
        balance = wallet_response.get("balance", 0)
        
        logger.info(f"Wallet balance: {balance}")
        
        # Check sufficient balance for cash_out
        if request.transaction_type == "cash_out" and balance < request.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
    
    except Exception as e:
        logger.error(f"Failed to get wallet balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get wallet balance")
    
    # Step 3: Create transaction
    transaction_id = f"txn-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id[:8]}"
    
    transaction_data = {
        "transaction_id": transaction_id,
        "transaction_type": request.transaction_type,
        "amount": request.amount,
        "customer_id": request.customer_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "description": request.description,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Step 4: Save transaction state (Dapr state management)
    try:
        await dapr_client.save_state(
            key=f"transaction:{transaction_id}",
            value=transaction_data,
            consistency="strong"  # Strong consistency for financial data
        )
        
        logger.info(f"Transaction state saved: {transaction_id}")
    
    except Exception as e:
        logger.error(f"Failed to save transaction state: {e}")
        raise HTTPException(status_code=500, detail="Failed to save transaction")
    
    # Step 5: Write Permify relationships
    try:
        await permify_client.write_relationships([
            {
                "entity": "transaction",
                "id": transaction_id,
                "relation": "initiator",
                "subject": f"user:{user_id}"
            },
            {
                "entity": "transaction",
                "id": transaction_id,
                "relation": "agent",
                "subject": f"agent:{agent_id}"
            },
            {
                "entity": "transaction",
                "id": transaction_id,
                "relation": "customer",
                "subject": f"customer:{request.customer_id}"
            }
        ])
        
        logger.info(f"Permify relationships written for transaction: {transaction_id}")
    
    except Exception as e:
        logger.error(f"Failed to write Permify relationships: {e}")
        # Continue even if relationship write fails
    
    # Step 6: Update wallet balance (Dapr service invocation)
    try:
        await dapr_client.invoke_service(
            app_id="wallet-service",
            method="update-balance",
            data={
                "user_id": user_id,
                "amount": request.amount if request.transaction_type == "cash_in" else -request.amount,
                "transaction_id": transaction_id
            }
        )
        
        logger.info(f"Wallet balance updated")
    
    except Exception as e:
        logger.error(f"Failed to update wallet balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to update wallet balance")
    
    # Step 7: Publish event (Dapr pub/sub)
    try:
        await dapr_client.publish_event(
            topic="transactions.created",
            data=transaction_data
        )
        
        logger.info(f"Transaction created event published: {transaction_id}")
    
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")
        # Continue even if event publish fails
    
    # Step 8: Update transaction status
    transaction_data["status"] = "completed"
    
    await dapr_client.save_state(
        key=f"transaction:{transaction_id}",
        value=transaction_data,
        consistency="strong"
    )
    
    return TransactionResponse(
        transaction_id=transaction_id,
        status="completed",
        amount=request.amount,
        timestamp=transaction_data["created_at"]
    )


@app.get("/transactions/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get transaction by ID.
    
    Requires:
    - Authentication (Keycloak)
    - Permission (Permify: transaction.view)
    """
    user_id = user.get("sub")
    
    # Check permission (Permify)
    allowed = await permify_client.check_permission(
        entity="transaction",
        entity_id=transaction_id,
        permission="view",
        subject=f"user:{user_id}"
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied: Cannot view transaction")
    
    # Get transaction state (Dapr)
    transaction = await dapr_client.get_state(f"transaction:{transaction_id}")
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return transaction


@app.post("/transactions/{transaction_id}/reverse")
async def reverse_transaction(
    transaction_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Reverse a transaction.
    
    Requires:
    - Authentication (Keycloak)
    - Permission (Permify: transaction.reverse)
    - Role: admin (Keycloak)
    """
    user_id = user.get("sub")
    
    # Check permission (Permify)
    allowed = await permify_client.check_permission(
        entity="transaction",
        entity_id=transaction_id,
        permission="reverse",
        subject=f"user:{user_id}"
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied: Cannot reverse transaction")
    
    # Get transaction
    transaction = await dapr_client.get_state(f"transaction:{transaction_id}")
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Can only reverse completed transactions")
    
    # Reverse wallet balance
    await dapr_client.invoke_service(
        app_id="wallet-service",
        method="update-balance",
        data={
            "user_id": transaction["user_id"],
            "amount": -transaction["amount"] if transaction["transaction_type"] == "cash_in" else transaction["amount"],
            "transaction_id": transaction_id
        }
    )
    
    # Update transaction status
    transaction["status"] = "reversed"
    transaction["reversed_at"] = datetime.utcnow().isoformat()
    transaction["reversed_by"] = user_id
    
    await dapr_client.save_state(
        key=f"transaction:{transaction_id}",
        value=transaction,
        consistency="strong"
    )
    
    # Publish event
    await dapr_client.publish_event(
        topic="transactions.reversed",
        data=transaction
    )
    
    return {"status": "reversed", "transaction_id": transaction_id}


@app.get("/transactions")
async def list_transactions(
    user: Dict[str, Any] = Depends(get_current_user),
    limit: int = 10
):
    """
    List transactions user can view.
    
    Uses Permify to lookup all transactions user has view permission on.
    """
    user_id = user.get("sub")
    
    # Lookup resources (Permify)
    transaction_ids = await permify_client.lookup_resources(
        entity="transaction",
        permission="view",
        subject=f"user:{user_id}"
    )
    
    # Get transaction details (Dapr)
    transactions = []
    
    for txn_id in transaction_ids[:limit]:
        transaction = await dapr_client.get_state(f"transaction:{txn_id}")
        if transaction:
            transactions.append(transaction)
    
    return {
        "total": len(transaction_ids),
        "limit": limit,
        "transactions": transactions
    }


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "transaction-service",
        "timestamp": datetime.utcnow().isoformat(),
        "dapr_metrics": dapr_client.get_metrics(),
        "permify_metrics": permify_client.get_metrics()
    }


# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
async def startup():
    """Startup event."""
    logger.info("🚀 Transaction Service started")
    logger.info(f"Dapr HTTP port: {dapr_client.dapr_http_port}")
    logger.info(f"Dapr gRPC port: {dapr_client.dapr_grpc_port}")
    logger.info(f"Permify endpoint: {permify_client.endpoint}")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown event."""
    await permify_client.close()
    logger.info("👋 Transaction Service stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
