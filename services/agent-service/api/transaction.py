"""
Agent Transaction API - Cash In/Out Operations
Similar to teller service but for agent banking operations
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid
import httpx
import os
from adapters import AuditServiceAdapter
from schemas import Context, AuditEventSchema

router = APIRouter()

# ==================== Models ====================


class CashInRequest(BaseModel):
    agent_id: str = Field(..., description="Agent keycloak ID")
    customer_account: str = Field(..., description="Customer account number")
    amount: float = Field(..., gt=0, description="Amount in NGN")
    currency: str = Field(default="NGN")
    reference: Optional[str] = Field(None, description="Transaction reference")
    description: Optional[str] = Field(None, description="Transaction description")
    payment_method: str = Field(
        default="cash", description="Payment method: cash, card, transfer"
    )


class CashOutRequest(BaseModel):
    agent_id: str = Field(..., description="Agent keycloak ID")
    customer_account: str = Field(..., description="Customer account number")
    amount: float = Field(..., gt=0, description="Amount in NGN")
    currency: str = Field(default="NGN")
    reference: Optional[str] = Field(None, description="Transaction reference")
    description: Optional[str] = Field(None, description="Transaction description")
    payment_method: str = Field(
        default="cash", description="Payment method: cash, card, transfer"
    )
    card_number: Optional[str] = Field(
        None, description="Card number (last 4 digits) if payment_method is card"
    )
    card_id: Optional[str] = Field(
        None, description="Card ID if payment_method is card"
    )


class TransactionResponse(BaseModel):
    transaction_id: str
    transaction_type: str
    agent_id: str
    customer_account: str
    amount: float
    currency: str
    status: str
    reference: str
    description: str
    payment_method: str
    card_last4: Optional[str] = None
    created_at: datetime
    gl_posting_id: Optional[str] = None


# ==================== Helper Functions ====================


async def call_account_service(
    endpoint: str, method: str = "GET", data: dict = None, headers: dict = None
):
    """Call account service API"""
    base_url = os.getenv("ACCOUNT_SERVICE_URL", "http://localhost:8001")
    url = f"{base_url}{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, headers=headers)
        elif method == "POST":
            response = await client.post(url, json=data, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Account service error: {response.text}",
            )

        return response.json()


async def call_chart_of_accounts(
    endpoint: str, method: str = "POST", data: dict = None
):
    """Call chart of accounts service for GL postings"""
    base_url = os.getenv("CHART_OF_ACCOUNTS_URL", "http://localhost:8007")
    url = f"{base_url}{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "POST":
            response = await client.post(url, json=data)
        else:
            response = await client.get(url)

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Chart of accounts error: {response.text}",
            )

        return response.json()


async def get_agent_account(agent_keycloak_id: str, tenant_id: str, keycloak_id: str):
    """Get agent's account details"""
    headers = {"x-tenant-id": tenant_id, "x-keycloak-id": keycloak_id}
    return await call_account_service(
        f"/account/account/keycloak/{agent_keycloak_id}", headers=headers
    )


async def get_customer_account(account_number: str, tenant_id: str, keycloak_id: str):
    """Get customer's account details"""
    headers = {"x-tenant-id": tenant_id, "x-keycloak-id": keycloak_id}
    return await call_account_service(
        f"/account/account/account-number/{account_number}", headers=headers
    )


async def validate_card_transaction(
    card_id: str, amount: float, tenant_id: str, keycloak_id: str
):
    """Validate card for transaction (check limits, status)"""
    card_service_url = os.getenv("CARD_SERVICE_URL", "http://localhost:8003")
    url = f"{card_service_url}/api/v1/cards/{card_id}"

    headers = {"x-tenant-id": tenant_id, "x-keycloak-id": keycloak_id}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Card validation error: {response.text}",
            )

        card_data = response.json()
        card = card_data.get("card")

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        # Check card status
        if card.get("status") != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Card is {card.get('status')}. Cannot process transaction.",
            )

        # Check daily limit
        daily_spent = float(card.get("daily_spent", 0))
        daily_limit = float(card.get("daily_limit", 500000))

        if (daily_spent + amount) > daily_limit:
            raise HTTPException(
                status_code=400,
                detail=f"Transaction exceeds daily limit. Available: ₦{(daily_limit - daily_spent):,.2f}",
            )

        return card


# ==================== Endpoints ====================


@router.post("/transactions/cash-in", response_model=TransactionResponse)
async def create_cash_in(
    request: CashInRequest,
    x_tenant_id: str = Header(...),
    x_keycloak_id: str = Header(...),
):
    """
    Process a cash in (customer deposit) transaction

    Flow:
    1. Agent receives physical cash from customer
    2. System credits customer's account (virtual balance)
    3. Creates GL posting:
       - DR: Cash In Hand (1001) - Agent has the cash
       - CR: Customer Deposits Payable (2001) - Platform owes customer
    """
    try:
        transaction_id = f"CASHIN-{uuid.uuid4().hex[:12].upper()}"
        reference = request.reference or transaction_id
        description = (
            request.description or f"{request.payment_method.capitalize()} deposit"
        )
        card_last4 = None

        # Validate payment method
        valid_methods = ["cash", "card", "transfer"]
        if request.payment_method not in valid_methods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment method. Must be one of: {', '.join(valid_methods)}",
            )

        # Verify agent exists and get their account
        try:
            await get_agent_account(request.agent_id, x_tenant_id, x_keycloak_id)
        except Exception as e:
            raise HTTPException(
                status_code=404, detail=f"Agent account not found: {str(e)}"
            )

        # Verify customer account exists
        try:
            await get_customer_account(
                request.customer_account, x_tenant_id, x_keycloak_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=404, detail=f"Customer account not found: {str(e)}"
            )

        # Credit customer's account via account service
        await call_account_service(
            f"/account/account/account-number/{request.customer_account}/credit",
            method="POST",
            data={"amount": int(request.amount * 100), "reference": reference, "description": description},
            headers={"x-tenant-id": x_tenant_id, "x-keycloak-id": x_keycloak_id},
        )

        # Create GL posting for double-entry accounting
        gl_response = await call_chart_of_accounts(
            "/chart-of-accounts/auto-post",
            method="POST",
            data={
                "transaction_ref": reference,
                "transaction_type": "cash_in",
                "amount": request.amount,
                "currency": request.currency,
                "agent_id": request.agent_id,
                "payment_method": request.payment_method,
            },
        )

        AuditServiceAdapter().create_audit(
            payload=AuditEventSchema(
                actor_id=x_keycloak_id,
                tenant_id=x_tenant_id,
                event_type="DEPOSIT",
                event_data={
                    "type": "cash_in",
                    "transaction_id": transaction_id,
                    "amount": str(request.amount),
                    "agent_id": request.agent_id,
                    "customer_account": request.customer_account,
                    "reference": reference,
                },
                timestamp=datetime.utcnow().isoformat(),
            ),
            context=Context(tenant_id=x_tenant_id, keycloak_id=x_keycloak_id),
        )

        return TransactionResponse(
            transaction_id=transaction_id,
            transaction_type="cash_in",
            agent_id=request.agent_id,
            customer_account=request.customer_account,
            amount=request.amount,
            currency=request.currency,
            status="completed",
            reference=reference,
            description=description,
            payment_method=request.payment_method,
            card_last4=card_last4,
            created_at=datetime.utcnow(),
            gl_posting_id=gl_response.get("posting_id"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process cash in: {str(e)}"
        )


@router.post("/transactions/cash-out", response_model=TransactionResponse)
async def create_cash_out(
    request: CashOutRequest,
    x_tenant_id: str = Header(...),
    x_keycloak_id: str = Header(...),
):
    """
    Process a cash out (customer withdrawal) transaction

    Flow:
    1. Agent disburses physical cash to customer
    2. System debits customer's account (virtual balance)
    3. Creates GL posting:
       - DR: Customer Deposits Payable (2001) - Reduce platform liability
       - CR: Cash Out Disbursements (1002) - Agent gave away cash
    """
    try:
        transaction_id = f"CASHOUT-{uuid.uuid4().hex[:12].upper()}"
        reference = request.reference or transaction_id
        description = (
            request.description or f"{request.payment_method.capitalize()} withdrawal"
        )
        card_last4 = None

        # Validate payment method
        valid_methods = ["cash", "card", "transfer"]
        if request.payment_method not in valid_methods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment method. Must be one of: {', '.join(valid_methods)}",
            )

        # Validate card if payment method is card
        if request.payment_method == "card":
            if not request.card_id:
                raise HTTPException(
                    status_code=400,
                    detail="card_id is required when payment_method is 'card'",
                )

            # Validate card and check limits
            try:
                card = await validate_card_transaction(
                    request.card_id, request.amount, x_tenant_id, x_keycloak_id
                )
                card_last4 = request.card_number or card.get("card_number", "")[-4:]
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Card validation failed: {str(e)}"
                )

        # Verify agent exists and has sufficient balance (for cash/card withdrawals)
        if request.payment_method in ["cash", "card"]:
            try:
                agent_account = await get_agent_account(
                    request.agent_id, x_tenant_id, x_keycloak_id
                )
                agent_balance = agent_account.get("account", {}).get("balance", 0)

                # Convert from kobo to naira for comparison
                if agent_balance < request.amount * 100:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient agent balance. Available: ₦{agent_balance/100:,.2f}, Required: ₦{request.amount:,.2f}",
                    )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=404, detail=f"Agent account not found: {str(e)}"
                )

        # Verify customer account exists and has sufficient balance
        try:
            customer_account = await get_customer_account(
                request.customer_account, x_tenant_id, x_keycloak_id
            )
            customer_balance = customer_account.get("account", {}).get("balance", 0)

            if customer_balance < request.amount * 100:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient customer balance. Available: ₦{customer_balance/100:,.2f}, Required: ₦{request.amount:,.2f}",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=404, detail=f"Customer account not found: {str(e)}"
            )

        # Debit customer's account via account service
        await call_account_service(
            f"/account/account/account-number/{request.customer_account}/debit",
            method="POST",
            data={"amount": int(request.amount * 100), "reference": reference, "description": description},
            headers={"x-tenant-id": x_tenant_id, "x-keycloak-id": x_keycloak_id},
        )

        # Create GL posting for double-entry accounting
        gl_response = await call_chart_of_accounts(
            "/chart-of-accounts/auto-post",
            method="POST",
            data={
                "transaction_ref": reference,
                "transaction_type": "cash_out",
                "amount": request.amount,
                "currency": request.currency,
                "agent_id": request.agent_id,
                "payment_method": request.payment_method,
                "card_id": (
                    request.card_id if request.payment_method == "card" else None
                ),
            },
        )

        AuditServiceAdapter().create_audit(
            payload=AuditEventSchema(
                actor_id=x_keycloak_id,
                tenant_id=x_tenant_id,
                event_type="WITHDRAWAL",
                event_data={
                    "type": "cash_out",
                    "transaction_id": transaction_id,
                    "amount": str(request.amount),
                    "agent_id": request.agent_id,
                    "customer_account": request.customer_account,
                    "reference": reference,
                },
                timestamp=datetime.utcnow().isoformat(),
            ),
            context=Context(tenant_id=x_tenant_id, keycloak_id=x_keycloak_id),
        )

        return TransactionResponse(
            transaction_id=transaction_id,
            transaction_type="cash_out",
            agent_id=request.agent_id,
            customer_account=request.customer_account,
            amount=request.amount,
            currency=request.currency,
            status="completed",
            reference=reference,
            description=description,
            payment_method=request.payment_method,
            card_last4=card_last4,
            created_at=datetime.utcnow(),
            gl_posting_id=gl_response.get("posting_id"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process cash out: {str(e)}"
        )


@router.get("/transactions/cash-book")
async def get_cash_book(
    agent_id: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = 100,
):
    """
    Get cash book transactions (cash in/out history)

    Note: This currently returns transactions from GL postings
    In production, this should query a proper transaction history table
    """
    try:
        # Get GL postings for this agent
        gl_postings = await call_chart_of_accounts(
            (
                f"/chart-of-accounts/postings?agent_id={agent_id}&limit={limit}"
                if agent_id
                else f"/chart-of-accounts/postings?limit={limit}"
            ),
            method="GET",
        )

        # Filter by transaction type if specified
        transactions = gl_postings.get("postings", [])
        if transaction_type:
            transactions = [
                t for t in transactions if t.get("transaction_type") == transaction_type
            ]

        return {
            "transactions": transactions,
            "total": len(transactions),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve transactions: {str(e)}"
        )
