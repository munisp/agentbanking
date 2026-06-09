import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive TigerBeetle Integration Service
Handles all financial ledger operations across the platform
Port: 8028
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("tigerbeetle-integration-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import asyncpg
import redis.asyncio as redis
import uuid
import json

app = FastAPI(title="TigerBeetle Integration Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database and cache
db_pool = None
redis_client = None

# TigerBeetle account types (using 128-bit IDs)
class AccountType(str, Enum):
    AGENT_ASSET = "agent_asset"  # Agent's main account
    AGENT_LIABILITY = "agent_liability"  # Agent's credit facility
    MERCHANT_ASSET = "merchant_asset"  # Merchant/Store account
    MANUFACTURER_ASSET = "manufacturer_asset"  # Manufacturer account
    PLATFORM_REVENUE = "platform_revenue"  # Platform revenue
    PLATFORM_FEES = "platform_fees"  # Platform fees
    INVENTORY_ASSET = "inventory_asset"  # Inventory valuation
    ESCROW = "escrow"  # Escrow for transactions

class TransactionType(str, Enum):
    AGENT_ONBOARDING = "agent_onboarding"
    CREDIT_DISBURSEMENT = "credit_disbursement"
    CREDIT_PAYMENT = "credit_payment"
    PURCHASE_ORDER = "purchase_order"
    PAYMENT_PROCESSING = "payment_processing"
    INVENTORY_PURCHASE = "inventory_purchase"
    MERCHANT_SALE = "merchant_sale"
    PLATFORM_FEE = "platform_fee"
    REFUND = "refund"

# ==================== MODELS ====================

class TigerBeetleAccount(BaseModel):
    id: str  # UUID mapped to 128-bit TigerBeetle ID
    user_id: str  # Agent/Merchant/Manufacturer ID
    account_type: AccountType
    ledger_id: int = 1  # Nigerian Naira ledger
    code: int  # Account code (asset=1, liability=2, equity=3, revenue=4, expense=5)
    balance: int = 0  # Balance in smallest currency unit (kobo for NGN)
    created_at: Optional[datetime] = None

class TigerBeetleTransfer(BaseModel):
    id: str  # Transfer ID
    debit_account_id: str
    credit_account_id: str
    amount: int  # Amount in smallest currency unit
    ledger_id: int = 1
    code: int  # Transfer code for categorization
    user_data: Optional[Dict[str, Any]] = {}
    timestamp: Optional[datetime] = None

class AccountCreationRequest(BaseModel):
    user_id: str
    user_type: str  # "agent", "merchant", "manufacturer"
    initial_balance: float = 0.0
    credit_limit: Optional[float] = None

class TransferRequest(BaseModel):
    from_user_id: str
    to_user_id: str
    amount: float
    transaction_type: TransactionType
    description: str
    metadata: Optional[Dict[str, Any]] = {}

class BalanceQuery(BaseModel):
    user_id: str
    account_type: Optional[AccountType] = None

# ==================== HELPER FUNCTIONS ====================

def naira_to_kobo(amount: float) -> int:
    """Convert Naira to Kobo (smallest unit)"""
    return int(amount * 100)

def kobo_to_naira(amount: int) -> float:
    """Convert Kobo to Naira"""
    return amount / 100.0

def generate_account_code(account_type: AccountType) -> int:
    """Generate account code based on type"""
    code_map = {
        AccountType.AGENT_ASSET: 1001,
        AccountType.AGENT_LIABILITY: 2001,
        AccountType.MERCHANT_ASSET: 1002,
        AccountType.MANUFACTURER_ASSET: 1003,
        AccountType.PLATFORM_REVENUE: 4001,
        AccountType.PLATFORM_FEES: 4002,
        AccountType.INVENTORY_ASSET: 1004,
        AccountType.ESCROW: 1005,
    }
    return code_map.get(account_type, 1000)

def generate_transfer_code(transaction_type: TransactionType) -> int:
    """Generate transfer code based on transaction type"""
    code_map = {
        TransactionType.AGENT_ONBOARDING: 1,
        TransactionType.CREDIT_DISBURSEMENT: 2,
        TransactionType.CREDIT_PAYMENT: 3,
        TransactionType.PURCHASE_ORDER: 4,
        TransactionType.PAYMENT_PROCESSING: 5,
        TransactionType.INVENTORY_PURCHASE: 6,
        TransactionType.MERCHANT_SALE: 7,
        TransactionType.PLATFORM_FEE: 8,
        TransactionType.REFUND: 9,
    }
    return code_map.get(transaction_type, 0)

# ==================== DATABASE INITIALIZATION ====================

async def init_db():
    """Initialize database tables"""
    global db_pool, redis_client
    
    import os
    
    # Get configuration from environment variables - NO hardcoded defaults
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME", "remittance")
    redis_url = os.getenv("REDIS_URL")
    
    # Validate required configuration
    if not all([db_host, db_user, db_password]):
        raise ValueError(
            "Database configuration missing. Set DB_HOST, DB_USER, DB_PASSWORD environment variables"
        )
    if not redis_url:
        raise ValueError("REDIS_URL environment variable is required")
    
    try:
        db_pool = await asyncpg.create_pool(
            host=db_host,
            port=int(db_port),
            user=db_user,
            password=db_password,
            database=db_name,
            min_size=10,
            max_size=20
        )
        
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        
        async with db_pool.acquire() as conn:
            # TigerBeetle accounts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tigerbeetle_accounts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    account_type VARCHAR(50) NOT NULL,
                    ledger_id INTEGER DEFAULT 1,
                    code INTEGER NOT NULL,
                    balance BIGINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, account_type)
                )
            """)
            
            # TigerBeetle transfers table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tigerbeetle_transfers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    debit_account_id UUID REFERENCES tigerbeetle_accounts(id),
                    credit_account_id UUID REFERENCES tigerbeetle_accounts(id),
                    amount BIGINT NOT NULL,
                    ledger_id INTEGER DEFAULT 1,
                    code INTEGER NOT NULL,
                    transaction_type VARCHAR(50),
                    description TEXT,
                    user_data JSONB,
                    status VARCHAR(20) DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Account balance history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS account_balance_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id UUID REFERENCES tigerbeetle_accounts(id),
                    balance_before BIGINT,
                    balance_after BIGINT,
                    change_amount BIGINT,
                    transfer_id UUID REFERENCES tigerbeetle_transfers(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create platform accounts if they don't exist
            platform_accounts = [
                (str(uuid.uuid4()), 'platform', AccountType.PLATFORM_REVENUE, generate_account_code(AccountType.PLATFORM_REVENUE)),
                (str(uuid.uuid4()), 'platform', AccountType.PLATFORM_FEES, generate_account_code(AccountType.PLATFORM_FEES)),
            ]
            
            for acc_id, user_id, acc_type, code in platform_accounts:
                await conn.execute("""
                    INSERT INTO tigerbeetle_accounts (id, user_id, account_type, code)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, account_type) DO NOTHING
                """, acc_id, user_id, acc_type.value, code)
            
            print("✅ TigerBeetle integration tables initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()

# ==================== API ENDPOINTS ====================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "TigerBeetle Integration", "port": 8028}

@app.post("/api/tigerbeetle/accounts/create")
async def create_account(request: AccountCreationRequest):
    """Create TigerBeetle account(s) for a user"""
    try:
        async with db_pool.acquire() as conn:
            accounts_created = []
            
            # Determine which accounts to create based on user type
            if request.user_type == "agent":
                account_types = [
                    (AccountType.AGENT_ASSET, naira_to_kobo(request.initial_balance)),
                ]
                if request.credit_limit and request.credit_limit > 0:
                    account_types.append((AccountType.AGENT_LIABILITY, 0))
            
            elif request.user_type == "merchant":
                account_types = [(AccountType.MERCHANT_ASSET, naira_to_kobo(request.initial_balance))]
            
            elif request.user_type == "manufacturer":
                account_types = [(AccountType.MANUFACTURER_ASSET, naira_to_kobo(request.initial_balance))]
            
            else:
                raise HTTPException(status_code=400, detail="Invalid user type")
            
            # Create accounts
            for account_type, initial_balance in account_types:
                account_id = str(uuid.uuid4())
                code = generate_account_code(account_type)
                
                await conn.execute("""
                    INSERT INTO tigerbeetle_accounts (id, user_id, account_type, code, balance)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, account_type) DO NOTHING
                """, account_id, request.user_id, account_type.value, code, initial_balance)
                
                accounts_created.append({
                    "id": account_id,
                    "user_id": request.user_id,
                    "account_type": account_type.value,
                    "code": code,
                    "balance": kobo_to_naira(initial_balance)
                })
                
                # Cache account
                cache_key = f"tb_account:{request.user_id}:{account_type.value}"
                await redis_client.setex(
                    cache_key,
                    3600,
                    json.dumps({"id": account_id, "balance": initial_balance})
                )
            
            return {
                "success": True,
                "user_id": request.user_id,
                "accounts": accounts_created,
                "message": f"Created {len(accounts_created)} TigerBeetle account(s)"
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tigerbeetle/transfer")
async def create_transfer(request: TransferRequest):
    """Create a transfer between accounts (double-entry bookkeeping)"""
    try:
        async with db_pool.acquire() as conn:
            # Get source account
            from_account = await conn.fetchrow("""
                SELECT id, balance FROM tigerbeetle_accounts
                WHERE user_id = $1 AND account_type = $2
            """, request.from_user_id, AccountType.AGENT_ASSET.value)
            
            if not from_account:
                raise HTTPException(status_code=404, detail="Source account not found")
            
            # Get destination account
            to_account = await conn.fetchrow("""
                SELECT id, balance FROM tigerbeetle_accounts
                WHERE user_id = $1 AND account_type = $2
            """, request.to_user_id, AccountType.MERCHANT_ASSET.value)
            
            if not to_account:
                raise HTTPException(status_code=404, detail="Destination account not found")
            
            amount_kobo = naira_to_kobo(request.amount)
            
            # Check sufficient balance
            if from_account['balance'] < amount_kobo:
                raise HTTPException(status_code=400, detail="Insufficient balance")
            
            # Create transfer record
            transfer_id = str(uuid.uuid4())
            transfer_code = generate_transfer_code(request.transaction_type)
            
            await conn.execute("""
                INSERT INTO tigerbeetle_transfers 
                (id, debit_account_id, credit_account_id, amount, code, transaction_type, description, user_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, transfer_id, from_account['id'], to_account['id'], amount_kobo, 
                transfer_code, request.transaction_type.value, request.description, 
                json.dumps(request.metadata))
            
            # Update balances (debit from source, credit to destination)
            new_from_balance = from_account['balance'] - amount_kobo
            new_to_balance = to_account['balance'] + amount_kobo
            
            await conn.execute("""
                UPDATE tigerbeetle_accounts SET balance = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, new_from_balance, from_account['id'])
            
            await conn.execute("""
                UPDATE tigerbeetle_accounts SET balance = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, new_to_balance, to_account['id'])
            
            # Record balance history
            await conn.execute("""
                INSERT INTO account_balance_history 
                (account_id, balance_before, balance_after, change_amount, transfer_id)
                VALUES ($1, $2, $3, $4, $5), ($6, $7, $8, $9, $10)
            """, from_account['id'], from_account['balance'], new_from_balance, -amount_kobo, transfer_id,
                to_account['id'], to_account['balance'], new_to_balance, amount_kobo, transfer_id)
            
            # Invalidate cache
            await redis_client.delete(f"tb_account:{request.from_user_id}:*")
            await redis_client.delete(f"tb_account:{request.to_user_id}:*")
            
            return {
                "success": True,
                "transfer_id": transfer_id,
                "from_user": request.from_user_id,
                "to_user": request.to_user_id,
                "amount": request.amount,
                "from_balance": kobo_to_naira(new_from_balance),
                "to_balance": kobo_to_naira(new_to_balance),
                "transaction_type": request.transaction_type.value
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tigerbeetle/balance")
async def get_balance(query: BalanceQuery):
    """Get account balance(s) for a user"""
    try:
        async with db_pool.acquire() as conn:
            if query.account_type:
                # Get specific account balance
                account = await conn.fetchrow("""
                    SELECT id, account_type, balance, code, created_at
                    FROM tigerbeetle_accounts
                    WHERE user_id = $1 AND account_type = $2
                """, query.user_id, query.account_type.value)
                
                if not account:
                    raise HTTPException(status_code=404, detail="Account not found")
                
                return {
                    "user_id": query.user_id,
                    "account_type": account['account_type'],
                    "balance": kobo_to_naira(account['balance']),
                    "balance_kobo": account['balance'],
                    "code": account['code']
                }
            else:
                # Get all accounts for user
                accounts = await conn.fetch("""
                    SELECT id, account_type, balance, code, created_at
                    FROM tigerbeetle_accounts
                    WHERE user_id = $1
                """, query.user_id)
                
                return {
                    "user_id": query.user_id,
                    "accounts": [
                        {
                            "account_type": acc['account_type'],
                            "balance": kobo_to_naira(acc['balance']),
                            "balance_kobo": acc['balance'],
                            "code": acc['code']
                        }
                        for acc in accounts
                    ]
                }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tigerbeetle/transactions/{user_id}")
async def get_transactions(user_id: str, limit: int = 50):
    """Get transaction history for a user"""
    try:
        async with db_pool.acquire() as conn:
            transactions = await conn.fetch("""
                SELECT 
                    t.id, t.amount, t.transaction_type, t.description, t.created_at,
                    da.user_id as from_user, da.account_type as from_account_type,
                    ca.user_id as to_user, ca.account_type as to_account_type
                FROM tigerbeetle_transfers t
                JOIN tigerbeetle_accounts da ON t.debit_account_id = da.id
                JOIN tigerbeetle_accounts ca ON t.credit_account_id = ca.id
                WHERE da.user_id = $1 OR ca.user_id = $1
                ORDER BY t.created_at DESC
                LIMIT $2
            """, user_id, limit)
            
            return {
                "user_id": user_id,
                "transactions": [
                    {
                        "id": str(tx['id']),
                        "amount": kobo_to_naira(tx['amount']),
                        "type": tx['transaction_type'],
                        "description": tx['description'],
                        "from_user": str(tx['from_user']),
                        "to_user": str(tx['to_user']),
                        "direction": "debit" if tx['from_user'] == user_id else "credit",
                        "timestamp": tx['created_at'].isoformat()
                    }
                    for tx in transactions
                ]
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tigerbeetle/analytics/platform")
async def get_platform_analytics():
    """Get platform-wide financial analytics"""
    try:
        async with db_pool.acquire() as conn:
            # Total balances by account type
            balances = await conn.fetch("""
                SELECT account_type, SUM(balance) as total_balance, COUNT(*) as account_count
                FROM tigerbeetle_accounts
                GROUP BY account_type
            """)
            
            # Total transfers
            transfer_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_transfers,
                    SUM(amount) as total_volume,
                    AVG(amount) as avg_transfer
                FROM tigerbeetle_transfers
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            """)
            
            # Transfers by type
            by_type = await conn.fetch("""
                SELECT transaction_type, COUNT(*) as count, SUM(amount) as volume
                FROM tigerbeetle_transfers
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY transaction_type
            """)
            
            return {
                "balances_by_type": [
                    {
                        "account_type": b['account_type'],
                        "total_balance": kobo_to_naira(b['total_balance']),
                        "account_count": b['account_count']
                    }
                    for b in balances
                ],
                "last_30_days": {
                    "total_transfers": transfer_stats['total_transfers'],
                    "total_volume": kobo_to_naira(transfer_stats['total_volume']),
                    "avg_transfer": kobo_to_naira(transfer_stats['avg_transfer']) if transfer_stats['avg_transfer'] else 0
                },
                "by_transaction_type": [
                    {
                        "type": bt['transaction_type'],
                        "count": bt['count'],
                        "volume": kobo_to_naira(bt['volume'])
                    }
                    for bt in by_type
                ]
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8028)
