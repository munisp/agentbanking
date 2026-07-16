import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Ready TigerBeetle Service - Maximizing All Features
Financial-grade distributed ledger with:
- Linked transfers for atomic multi-leg transactions
- Pending/Post/Void workflow for 2-phase commit
- Deterministic IDs for idempotency
- Multiple ledgers for currency isolation
- Fail-closed operation (NO fallback in production)
- Full account flags support
"""
import os
import logging
import hashlib
import struct
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from enum import IntFlag, IntEnum
from decimal import Decimal
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field, validator
import uvicorn

# TigerBeetle Python client - REQUIRED, no fallback
try:
    from tigerbeetle import Client, Account, Transfer, AccountFlags, TransferFlags
    TIGERBEETLE_AVAILABLE = True
except ImportError:
    TIGERBEETLE_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TigerBeetle Production Service",
    description="Production-ready Financial Ledger maximizing all TigerBeetle features",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

apply_middleware(app)
setup_logging("tigerbeetle-production-service")
app.include_router(metrics_router)

# ==================== Configuration ====================

class Config:
    TIGERBEETLE_CLUSTER_ID = int(os.getenv("TIGERBEETLE_CLUSTER_ID", "0"))
    TIGERBEETLE_ADDRESSES = os.getenv("TIGERBEETLE_ADDRESSES", "3000").split(",")
    
    # Ledger IDs for currency isolation
    LEDGER_NGN = 1  # Nigerian Naira
    LEDGER_USD = 2  # US Dollar
    LEDGER_KES = 3  # Kenyan Shilling
    LEDGER_GHS = 4  # Ghanaian Cedi
    LEDGER_ZAR = 5  # South African Rand
    
    # Fail-closed mode - NO fallback in production
    ALLOW_MOCK_FALLBACK = os.getenv("ALLOW_MOCK_FALLBACK", "false").lower() == "true"
    
    MODEL_VERSION = "3.0.0"

config = Config()

# Currency to Ledger mapping
CURRENCY_LEDGER_MAP = {
    "NGN": config.LEDGER_NGN,
    "USD": config.LEDGER_USD,
    "KES": config.LEDGER_KES,
    "GHS": config.LEDGER_GHS,
    "ZAR": config.LEDGER_ZAR,
}

# Currency smallest unit multipliers
CURRENCY_MULTIPLIERS = {
    "NGN": 100,    # Kobo
    "USD": 100,    # Cents
    "KES": 100,    # Cents
    "GHS": 100,    # Pesewas
    "ZAR": 100,    # Cents
}

# ==================== TigerBeetle Account Flags ====================

class TBAccountFlags(IntFlag):
    """TigerBeetle Account Flags - using all available options"""
    NONE = 0
    LINKED = 1 << 0                           # Link with next account in batch
    DEBITS_MUST_NOT_EXCEED_CREDITS = 1 << 1   # Prevent overdraft
    CREDITS_MUST_NOT_EXCEED_DEBITS = 1 << 2   # For liability accounts
    HISTORY = 1 << 3                          # Enable historical balance queries

class TBTransferFlags(IntFlag):
    """TigerBeetle Transfer Flags - using all available options"""
    NONE = 0
    LINKED = 1 << 0           # Link with next transfer (atomic batch)
    PENDING = 1 << 1          # Create pending transfer (2PC phase 1)
    POST_PENDING = 1 << 2     # Post a pending transfer (2PC phase 2 commit)
    VOID_PENDING = 1 << 3     # Void a pending transfer (2PC phase 2 abort)
    BALANCING_DEBIT = 1 << 4  # Debit the full balance
    BALANCING_CREDIT = 1 << 5 # Credit the full balance

# ==================== Account Types ====================

class AccountType(IntEnum):
    """Chart of accounts codes"""
    ASSET = 1
    LIABILITY = 2
    EQUITY = 3
    REVENUE = 4
    EXPENSE = 5
    
    # Specific account types
    AGENT_FLOAT = 10
    AGENT_COMMISSION = 11
    CUSTOMER_WALLET = 20
    MERCHANT_SETTLEMENT = 30
    PLATFORM_FEE = 40
    PLATFORM_REVENUE = 41
    ESCROW = 50
    SUSPENSE = 60

class TransferCode(IntEnum):
    """Transfer type codes for categorization"""
    DEPOSIT = 1
    WITHDRAWAL = 2
    TRANSFER = 3
    FEE = 4
    COMMISSION = 5
    REFUND = 6
    PURCHASE = 7
    SALE = 8
    SETTLEMENT = 9
    REVERSAL = 10
    INTEREST = 11
    CHARGE = 12

# ==================== Request/Response Models ====================

class CreateAccountRequest(BaseModel):
    """Request to create a TigerBeetle account"""
    user_id: str = Field(..., description="External user/entity ID")
    account_type: AccountType
    currency: str = Field(default="NGN", description="Currency code")
    initial_balance: Decimal = Field(default=Decimal("0"), ge=0)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0)
    enable_history: bool = Field(default=True, description="Enable historical balance queries")
    metadata: Optional[Dict[str, Any]] = {}
    
    @validator('currency')
    def validate_currency(cls, v):
        if v not in CURRENCY_LEDGER_MAP:
            raise ValueError(f"Unsupported currency: {v}")
        return v

class LinkedAccountsRequest(BaseModel):
    """Request to create linked accounts atomically"""
    accounts: List[CreateAccountRequest]

class TransferRequest(BaseModel):
    """Request for a single transfer"""
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="NGN")
    transfer_code: TransferCode
    description: str
    idempotency_key: str = Field(..., description="Deterministic key for idempotency")
    timeout_seconds: int = Field(default=0, description="Timeout for pending transfers (0=no timeout)")
    metadata: Optional[Dict[str, Any]] = {}

class LinkedTransferRequest(BaseModel):
    """Request for atomic linked transfers (e.g., principal + fee + commission)"""
    transfers: List[TransferRequest]
    description: str = Field(..., description="Description for the linked batch")

class PendingTransferRequest(BaseModel):
    """Request to create a pending transfer (2PC phase 1)"""
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="NGN")
    transfer_code: TransferCode
    description: str
    idempotency_key: str
    timeout_seconds: int = Field(default=300, description="Timeout in seconds")
    metadata: Optional[Dict[str, Any]] = {}

class PostPendingRequest(BaseModel):
    """Request to post (commit) a pending transfer (2PC phase 2)"""
    pending_transfer_id: str
    idempotency_key: str
    amount: Optional[Decimal] = Field(default=None, description="Optional: post partial amount")

class VoidPendingRequest(BaseModel):
    """Request to void (abort) a pending transfer (2PC phase 2)"""
    pending_transfer_id: str
    idempotency_key: str

class AccountResponse(BaseModel):
    account_id: str
    user_id: str
    account_type: AccountType
    currency: str
    balance: Decimal
    credits_posted: Decimal
    debits_posted: Decimal
    credits_pending: Decimal
    debits_pending: Decimal
    flags: int
    created_at: datetime

class TransferResponse(BaseModel):
    transfer_id: str
    from_account_id: str
    to_account_id: str
    amount: Decimal
    currency: str
    transfer_code: TransferCode
    status: str
    is_pending: bool
    timestamp: datetime

class LinkedTransferResponse(BaseModel):
    batch_id: str
    transfers: List[TransferResponse]
    total_amount: Decimal
    status: str
    timestamp: datetime

# ==================== Deterministic ID Generation ====================

class DeterministicIDGenerator:
    """
    Generate deterministic 128-bit IDs for TigerBeetle idempotency.
    Same input always produces same ID, enabling safe retries.
    """
    
    @staticmethod
    def generate_account_id(user_id: str, account_type: AccountType, currency: str) -> int:
        """Generate deterministic account ID from user_id + type + currency"""
        data = f"account:{user_id}:{account_type.value}:{currency}"
        hash_bytes = hashlib.sha256(data.encode()).digest()[:16]
        return int.from_bytes(hash_bytes, byteorder='big')
    
    @staticmethod
    def generate_transfer_id(idempotency_key: str) -> int:
        """Generate deterministic transfer ID from idempotency key"""
        data = f"transfer:{idempotency_key}"
        hash_bytes = hashlib.sha256(data.encode()).digest()[:16]
        return int.from_bytes(hash_bytes, byteorder='big')
    
    @staticmethod
    def generate_linked_batch_id(idempotency_keys: List[str]) -> str:
        """Generate batch ID for linked transfers"""
        data = f"batch:{':'.join(sorted(idempotency_keys))}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

id_generator = DeterministicIDGenerator()

# ==================== TigerBeetle Production Manager ====================

class TigerBeetleProductionManager:
    """
    Production TigerBeetle manager with fail-closed operation.
    NO fallback - if TigerBeetle is unavailable, operations fail.
    """
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.stats = {
            "total_accounts": 0,
            "total_transfers": 0,
            "total_pending": 0,
            "total_posted": 0,
            "total_voided": 0,
            "total_linked_batches": 0,
            "total_volume": {},  # Per currency
            "failed_operations": 0,
            "start_time": datetime.now()
        }
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize TigerBeetle client - FAIL if not available"""
        if not TIGERBEETLE_AVAILABLE:
            if config.ALLOW_MOCK_FALLBACK:
                logger.warning("TigerBeetle client not installed. Fallback ENABLED (dev mode only)")
                self.connected = False
            else:
                logger.error("TigerBeetle client not installed. FAIL-CLOSED mode - no fallback")
                raise RuntimeError("TigerBeetle client required but not installed")
        else:
            try:
                self.client = Client(
                    cluster_id=config.TIGERBEETLE_CLUSTER_ID,
                    replica_addresses=config.TIGERBEETLE_ADDRESSES
                )
                self.connected = True
                logger.info(f"Connected to TigerBeetle cluster: {config.TIGERBEETLE_ADDRESSES}")
            except Exception as e:
                if config.ALLOW_MOCK_FALLBACK:
                    logger.warning(f"TigerBeetle connection failed: {e}. Fallback ENABLED")
                    self.connected = False
                else:
                    logger.error(f"TigerBeetle connection failed: {e}. FAIL-CLOSED - no fallback")
                    raise RuntimeError(f"TigerBeetle connection required: {e}")
    
    def _ensure_connected(self):
        """Ensure TigerBeetle is connected - fail if not"""
        if not self.connected and not config.ALLOW_MOCK_FALLBACK:
            raise HTTPException(
                status_code=503,
                detail="TigerBeetle ledger unavailable. Financial operations suspended."
            )
    
    def _to_smallest_unit(self, amount: Decimal, currency: str) -> int:
        """Convert amount to smallest currency unit"""
        multiplier = CURRENCY_MULTIPLIERS.get(currency, 100)
        return int(amount * multiplier)
    
    def _from_smallest_unit(self, amount: int, currency: str) -> Decimal:
        """Convert from smallest currency unit to decimal"""
        multiplier = CURRENCY_MULTIPLIERS.get(currency, 100)
        return Decimal(amount) / Decimal(multiplier)
    
    def _get_ledger_id(self, currency: str) -> int:
        """Get ledger ID for currency"""
        return CURRENCY_LEDGER_MAP.get(currency, config.LEDGER_NGN)
    
    # ==================== Account Operations ====================
    
    async def create_account(self, request: CreateAccountRequest) -> AccountResponse:
        """Create a single account with full flag support"""
        self._ensure_connected()
        
        account_id = id_generator.generate_account_id(
            request.user_id, request.account_type, request.currency
        )
        
        # Build flags based on account type and options
        flags = TBAccountFlags.NONE
        
        # Asset accounts should not go negative
        if request.account_type in [AccountType.ASSET, AccountType.AGENT_FLOAT, 
                                     AccountType.CUSTOMER_WALLET, AccountType.MERCHANT_SETTLEMENT]:
            flags |= TBAccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS
        
        # Liability accounts should not have positive balance
        if request.account_type == AccountType.LIABILITY:
            flags |= TBAccountFlags.CREDITS_MUST_NOT_EXCEED_DEBITS
        
        # Enable history if requested
        if request.enable_history:
            flags |= TBAccountFlags.HISTORY
        
        ledger_id = self._get_ledger_id(request.currency)
        initial_credits = self._to_smallest_unit(request.initial_balance, request.currency)
        
        account = Account(
            id=account_id,
            user_data_128=int(uuid.uuid4().int & ((1 << 128) - 1)),
            user_data_64=request.account_type.value,
            user_data_32=0,
            ledger=ledger_id,
            code=request.account_type.value,
            flags=flags,
            debits_pending=0,
            debits_posted=0,
            credits_pending=0,
            credits_posted=initial_credits,
            timestamp=0
        )
        
        try:
            result = self.client.create_accounts([account])
            if result:
                # Check for specific error
                error = result[0] if result else None
                if error:
                    logger.error(f"Account creation failed: {error}")
                    raise HTTPException(status_code=400, detail=f"Account creation failed: {error}")
            
            self.stats["total_accounts"] += 1
            
            return AccountResponse(
                account_id=str(account_id),
                user_id=request.user_id,
                account_type=request.account_type,
                currency=request.currency,
                balance=request.initial_balance,
                credits_posted=request.initial_balance,
                debits_posted=Decimal("0"),
                credits_pending=Decimal("0"),
                debits_pending=Decimal("0"),
                flags=flags,
                created_at=datetime.now()
            )
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Account creation error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    async def create_linked_accounts(self, request: LinkedAccountsRequest) -> List[AccountResponse]:
        """Create multiple accounts atomically using LINKED flag"""
        self._ensure_connected()
        
        if len(request.accounts) < 2:
            raise HTTPException(status_code=400, detail="Linked accounts require at least 2 accounts")
        
        accounts = []
        responses = []
        
        for i, acc_req in enumerate(request.accounts):
            account_id = id_generator.generate_account_id(
                acc_req.user_id, acc_req.account_type, acc_req.currency
            )
            
            flags = TBAccountFlags.NONE
            
            # Link all accounts except the last one
            if i < len(request.accounts) - 1:
                flags |= TBAccountFlags.LINKED
            
            if acc_req.account_type in [AccountType.ASSET, AccountType.AGENT_FLOAT,
                                        AccountType.CUSTOMER_WALLET]:
                flags |= TBAccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS
            
            if acc_req.enable_history:
                flags |= TBAccountFlags.HISTORY
            
            ledger_id = self._get_ledger_id(acc_req.currency)
            initial_credits = self._to_smallest_unit(acc_req.initial_balance, acc_req.currency)
            
            account = Account(
                id=account_id,
                user_data_128=int(uuid.uuid4().int & ((1 << 128) - 1)),
                user_data_64=acc_req.account_type.value,
                user_data_32=0,
                ledger=ledger_id,
                code=acc_req.account_type.value,
                flags=flags,
                debits_pending=0,
                debits_posted=0,
                credits_pending=0,
                credits_posted=initial_credits,
                timestamp=0
            )
            accounts.append(account)
            
            responses.append(AccountResponse(
                account_id=str(account_id),
                user_id=acc_req.user_id,
                account_type=acc_req.account_type,
                currency=acc_req.currency,
                balance=acc_req.initial_balance,
                credits_posted=acc_req.initial_balance,
                debits_posted=Decimal("0"),
                credits_pending=Decimal("0"),
                debits_pending=Decimal("0"),
                flags=flags,
                created_at=datetime.now()
            ))
        
        try:
            result = self.client.create_accounts(accounts)
            if result:
                logger.error(f"Linked account creation failed: {result}")
                raise HTTPException(status_code=400, detail=f"Linked account creation failed")
            
            self.stats["total_accounts"] += len(accounts)
            return responses
            
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Linked account creation error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    # ==================== Transfer Operations ====================
    
    async def create_transfer(self, request: TransferRequest) -> TransferResponse:
        """Create a single immediate transfer"""
        self._ensure_connected()
        
        transfer_id = id_generator.generate_transfer_id(request.idempotency_key)
        ledger_id = self._get_ledger_id(request.currency)
        amount = self._to_smallest_unit(request.amount, request.currency)
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=int(request.from_account_id),
            credit_account_id=int(request.to_account_id),
            user_data_128=0,
            user_data_64=0,
            user_data_32=0,
            pending_id=0,
            timeout=0,
            ledger=ledger_id,
            code=request.transfer_code.value,
            flags=TBTransferFlags.NONE,
            amount=amount,
            timestamp=0
        )
        
        try:
            result = self.client.create_transfers([transfer])
            if result:
                logger.error(f"Transfer failed: {result}")
                self.stats["failed_operations"] += 1
                raise HTTPException(status_code=400, detail=f"Transfer failed: {result}")
            
            self.stats["total_transfers"] += 1
            self._update_volume_stats(request.currency, request.amount)
            
            return TransferResponse(
                transfer_id=str(transfer_id),
                from_account_id=request.from_account_id,
                to_account_id=request.to_account_id,
                amount=request.amount,
                currency=request.currency,
                transfer_code=request.transfer_code,
                status="completed",
                is_pending=False,
                timestamp=datetime.now()
            )
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Transfer error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    async def create_linked_transfers(self, request: LinkedTransferRequest) -> LinkedTransferResponse:
        """
        Create atomic linked transfers (e.g., principal + fee + commission).
        All transfers succeed or all fail together.
        """
        self._ensure_connected()
        
        if len(request.transfers) < 2:
            raise HTTPException(status_code=400, detail="Linked transfers require at least 2 transfers")
        
        transfers = []
        responses = []
        idempotency_keys = []
        total_amount = Decimal("0")
        
        for i, tx_req in enumerate(request.transfers):
            transfer_id = id_generator.generate_transfer_id(tx_req.idempotency_key)
            idempotency_keys.append(tx_req.idempotency_key)
            ledger_id = self._get_ledger_id(tx_req.currency)
            amount = self._to_smallest_unit(tx_req.amount, tx_req.currency)
            
            # Link all transfers except the last one
            flags = TBTransferFlags.NONE
            if i < len(request.transfers) - 1:
                flags |= TBTransferFlags.LINKED
            
            transfer = Transfer(
                id=transfer_id,
                debit_account_id=int(tx_req.from_account_id),
                credit_account_id=int(tx_req.to_account_id),
                user_data_128=0,
                user_data_64=0,
                user_data_32=0,
                pending_id=0,
                timeout=0,
                ledger=ledger_id,
                code=tx_req.transfer_code.value,
                flags=flags,
                amount=amount,
                timestamp=0
            )
            transfers.append(transfer)
            total_amount += tx_req.amount
            
            responses.append(TransferResponse(
                transfer_id=str(transfer_id),
                from_account_id=tx_req.from_account_id,
                to_account_id=tx_req.to_account_id,
                amount=tx_req.amount,
                currency=tx_req.currency,
                transfer_code=tx_req.transfer_code,
                status="completed",
                is_pending=False,
                timestamp=datetime.now()
            ))
        
        try:
            result = self.client.create_transfers(transfers)
            if result:
                logger.error(f"Linked transfers failed: {result}")
                self.stats["failed_operations"] += 1
                raise HTTPException(status_code=400, detail=f"Linked transfers failed atomically")
            
            batch_id = id_generator.generate_linked_batch_id(idempotency_keys)
            self.stats["total_transfers"] += len(transfers)
            self.stats["total_linked_batches"] += 1
            
            return LinkedTransferResponse(
                batch_id=batch_id,
                transfers=responses,
                total_amount=total_amount,
                status="completed",
                timestamp=datetime.now()
            )
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Linked transfers error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    # ==================== 2-Phase Commit Operations ====================
    
    async def create_pending_transfer(self, request: PendingTransferRequest) -> TransferResponse:
        """Create a pending transfer (2PC phase 1 - reserve funds)"""
        self._ensure_connected()
        
        transfer_id = id_generator.generate_transfer_id(request.idempotency_key)
        ledger_id = self._get_ledger_id(request.currency)
        amount = self._to_smallest_unit(request.amount, request.currency)
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=int(request.from_account_id),
            credit_account_id=int(request.to_account_id),
            user_data_128=0,
            user_data_64=0,
            user_data_32=0,
            pending_id=0,
            timeout=request.timeout_seconds,
            ledger=ledger_id,
            code=request.transfer_code.value,
            flags=TBTransferFlags.PENDING,
            amount=amount,
            timestamp=0
        )
        
        try:
            result = self.client.create_transfers([transfer])
            if result:
                logger.error(f"Pending transfer failed: {result}")
                self.stats["failed_operations"] += 1
                raise HTTPException(status_code=400, detail=f"Pending transfer failed: {result}")
            
            self.stats["total_pending"] += 1
            
            return TransferResponse(
                transfer_id=str(transfer_id),
                from_account_id=request.from_account_id,
                to_account_id=request.to_account_id,
                amount=request.amount,
                currency=request.currency,
                transfer_code=request.transfer_code,
                status="pending",
                is_pending=True,
                timestamp=datetime.now()
            )
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Pending transfer error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    async def post_pending_transfer(self, request: PostPendingRequest) -> TransferResponse:
        """Post (commit) a pending transfer (2PC phase 2 - commit)"""
        self._ensure_connected()
        
        transfer_id = id_generator.generate_transfer_id(request.idempotency_key)
        pending_id = int(request.pending_transfer_id)
        
        # If partial amount specified, use it; otherwise post full amount
        amount = 0
        if request.amount:
            amount = self._to_smallest_unit(request.amount, "NGN")  # Will be overridden by pending
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=0,
            credit_account_id=0,
            user_data_128=0,
            user_data_64=0,
            user_data_32=0,
            pending_id=pending_id,
            timeout=0,
            ledger=0,
            code=0,
            flags=TBTransferFlags.POST_PENDING,
            amount=amount,
            timestamp=0
        )
        
        try:
            result = self.client.create_transfers([transfer])
            if result:
                logger.error(f"Post pending failed: {result}")
                self.stats["failed_operations"] += 1
                raise HTTPException(status_code=400, detail=f"Post pending failed: {result}")
            
            self.stats["total_posted"] += 1
            
            return TransferResponse(
                transfer_id=str(transfer_id),
                from_account_id="",
                to_account_id="",
                amount=request.amount or Decimal("0"),
                currency="NGN",
                transfer_code=TransferCode.TRANSFER,
                status="posted",
                is_pending=False,
                timestamp=datetime.now()
            )
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Post pending error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    async def void_pending_transfer(self, request: VoidPendingRequest) -> TransferResponse:
        """Void (abort) a pending transfer (2PC phase 2 - abort)"""
        self._ensure_connected()
        
        transfer_id = id_generator.generate_transfer_id(request.idempotency_key)
        pending_id = int(request.pending_transfer_id)
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=0,
            credit_account_id=0,
            user_data_128=0,
            user_data_64=0,
            user_data_32=0,
            pending_id=pending_id,
            timeout=0,
            ledger=0,
            code=0,
            flags=TBTransferFlags.VOID_PENDING,
            amount=0,
            timestamp=0
        )
        
        try:
            result = self.client.create_transfers([transfer])
            if result:
                logger.error(f"Void pending failed: {result}")
                self.stats["failed_operations"] += 1
                raise HTTPException(status_code=400, detail=f"Void pending failed: {result}")
            
            self.stats["total_voided"] += 1
            
            return TransferResponse(
                transfer_id=str(transfer_id),
                from_account_id="",
                to_account_id="",
                amount=Decimal("0"),
                currency="NGN",
                transfer_code=TransferCode.REVERSAL,
                status="voided",
                is_pending=False,
                timestamp=datetime.now()
            )
        except HTTPException:
            raise
        except Exception as e:
            self.stats["failed_operations"] += 1
            logger.error(f"Void pending error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    # ==================== Query Operations ====================
    
    async def get_account_balance(self, account_id: str, currency: str = "NGN") -> Dict[str, Any]:
        """Get account balance and details"""
        self._ensure_connected()
        
        try:
            account_id_int = int(account_id)
            accounts = self.client.lookup_accounts([account_id_int])
            
            if not accounts:
                raise HTTPException(status_code=404, detail="Account not found")
            
            account = accounts[0]
            
            return {
                "account_id": account_id,
                "balance": self._from_smallest_unit(
                    account.credits_posted - account.debits_posted, currency
                ),
                "available_balance": self._from_smallest_unit(
                    account.credits_posted - account.debits_posted - account.debits_pending, currency
                ),
                "credits_posted": self._from_smallest_unit(account.credits_posted, currency),
                "debits_posted": self._from_smallest_unit(account.debits_posted, currency),
                "credits_pending": self._from_smallest_unit(account.credits_pending, currency),
                "debits_pending": self._from_smallest_unit(account.debits_pending, currency),
                "ledger": account.ledger,
                "code": account.code,
                "flags": account.flags
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Balance lookup error: {e}")
            raise HTTPException(status_code=500, detail=f"Ledger error: {str(e)}")
    
    def _update_volume_stats(self, currency: str, amount: Decimal):
        """Update volume statistics per currency"""
        if currency not in self.stats["total_volume"]:
            self.stats["total_volume"][currency] = Decimal("0")
        self.stats["total_volume"][currency] += amount

# ==================== Initialize Manager ====================

tb_manager = TigerBeetleProductionManager()

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    return {
        "service": "tigerbeetle-production",
        "version": config.MODEL_VERSION,
        "cluster_id": config.TIGERBEETLE_CLUSTER_ID,
        "connected": tb_manager.connected,
        "fail_closed_mode": not config.ALLOW_MOCK_FALLBACK,
        "features": [
            "linked_transfers",
            "pending_post_void",
            "deterministic_ids",
            "multi_currency_ledgers",
            "full_account_flags"
        ],
        "status": "ready" if tb_manager.connected else "degraded"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - tb_manager.stats["start_time"]).total_seconds()
    return {
        "status": "healthy" if tb_manager.connected else "unhealthy",
        "uptime_seconds": int(uptime),
        "connected": tb_manager.connected,
        "fail_closed_mode": not config.ALLOW_MOCK_FALLBACK,
        "stats": {
            "total_accounts": tb_manager.stats["total_accounts"],
            "total_transfers": tb_manager.stats["total_transfers"],
            "total_pending": tb_manager.stats["total_pending"],
            "total_posted": tb_manager.stats["total_posted"],
            "total_voided": tb_manager.stats["total_voided"],
            "total_linked_batches": tb_manager.stats["total_linked_batches"],
            "failed_operations": tb_manager.stats["failed_operations"]
        }
    }

# Account endpoints
@app.post("/accounts", response_model=AccountResponse)
async def create_account(request: CreateAccountRequest):
    """Create a single account"""
    return await tb_manager.create_account(request)

@app.post("/accounts/linked", response_model=List[AccountResponse])
async def create_linked_accounts(request: LinkedAccountsRequest):
    """Create multiple accounts atomically"""
    return await tb_manager.create_linked_accounts(request)

@app.get("/accounts/{account_id}/balance")
async def get_balance(account_id: str, currency: str = "NGN"):
    """Get account balance"""
    return await tb_manager.get_account_balance(account_id, currency)

# Transfer endpoints
@app.post("/transfers", response_model=TransferResponse)
async def create_transfer(request: TransferRequest):
    """Create a single immediate transfer"""
    return await tb_manager.create_transfer(request)

@app.post("/transfers/linked", response_model=LinkedTransferResponse)
async def create_linked_transfers(request: LinkedTransferRequest):
    """Create atomic linked transfers (principal + fee + commission)"""
    return await tb_manager.create_linked_transfers(request)

# 2-Phase Commit endpoints
@app.post("/transfers/pending", response_model=TransferResponse)
async def create_pending_transfer(request: PendingTransferRequest):
    """Create a pending transfer (2PC phase 1 - reserve)"""
    return await tb_manager.create_pending_transfer(request)

@app.post("/transfers/pending/post", response_model=TransferResponse)
async def post_pending_transfer(request: PostPendingRequest):
    """Post a pending transfer (2PC phase 2 - commit)"""
    return await tb_manager.post_pending_transfer(request)

@app.post("/transfers/pending/void", response_model=TransferResponse)
async def void_pending_transfer(request: VoidPendingRequest):
    """Void a pending transfer (2PC phase 2 - abort)"""
    return await tb_manager.void_pending_transfer(request)

@app.get("/stats")
async def get_statistics():
    """Get service statistics"""
    uptime = (datetime.now() - tb_manager.stats["start_time"]).total_seconds()
    return {
        "uptime_seconds": int(uptime),
        "connected": tb_manager.connected,
        "accounts": tb_manager.stats["total_accounts"],
        "transfers": {
            "total": tb_manager.stats["total_transfers"],
            "pending": tb_manager.stats["total_pending"],
            "posted": tb_manager.stats["total_posted"],
            "voided": tb_manager.stats["total_voided"],
            "linked_batches": tb_manager.stats["total_linked_batches"]
        },
        "volume_by_currency": {
            k: str(v) for k, v in tb_manager.stats["total_volume"].items()
        },
        "failed_operations": tb_manager.stats["failed_operations"],
        "success_rate": (
            (tb_manager.stats["total_transfers"] - tb_manager.stats["failed_operations"]) /
            max(tb_manager.stats["total_transfers"], 1)
        )
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8160)
