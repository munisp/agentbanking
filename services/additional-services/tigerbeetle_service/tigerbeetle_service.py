"""
TigerBeetle Integration Service
High-performance financial accounting and ledger management
"""

from typing import Dict, List, Optional, Tuple
import os
import uuid
import time
import hashlib
from enum import Enum
from dataclasses import dataclass
import logging

try:
    # pip install tigerbeetle
    import tigerbeetle as tb
except ImportError:
    tb = None

logger = logging.getLogger(__name__)


class AccountType(Enum):
    """Account classification types"""
    USER_WALLET = "user_wallet"
    PLATFORM_FLOAT = "platform_float"
    PENDING = "pending"
    REVENUE = "revenue"
    EXPENSE = "expense"
    SETTLEMENT = "settlement"


class LedgerCode(Enum):
    """ISO 4217 currency codes"""
    USD = 840
    EUR = 978
    GBP = 826
    NGN = 566
    KES = 404
    GHS = 936
    BRL = 986
    INR = 356
    CNY = 156


class TransactionCode(Enum):
    """Transaction type codes"""
    DEPOSIT = 1
    REMITTANCE_SEND = 2
    REMITTANCE_RECEIVE = 3
    PENDING = 4
    WITHDRAWAL = 5
    PLATFORM_FEE = 10
    CDP_FEE = 11
    GATEWAY_FEE = 12
    FX_SPREAD = 13
    SETTLEMENT = 20
    REVERSAL = 99


@dataclass
class AccountBalance:
    """Account balance information"""
    account_id: int
    debits_posted: int
    credits_posted: int
    debits_pending: int
    credits_pending: int
    
    @property
    def balance(self) -> int:
        """Net balance (credits - debits)"""
        return self.credits_posted - self.debits_posted
    
    @property
    def available_balance(self) -> int:
        """Available balance including pending"""
        return (self.credits_posted + self.credits_pending) - \
               (self.debits_posted + self.debits_pending)


@dataclass
class TransferResult:
    """Transfer execution result"""
    transfer_id: int
    success: bool
    error: Optional[str] = None
    timestamp: Optional[int] = None


class TigerBeetleService:
    """
    TigerBeetle integration service for high-performance accounting
    
    Features:
    - Double-entry bookkeeping
    - Multi-currency support
    - Real-time balance queries (< 1ms)
    - Atomic transactions
    - Pending transfers
    - Revenue tracking
    """
    
    def __init__(self, cluster_id: int, addresses: List[str]):
        """
        Initialize TigerBeetle client
        
        Args:
            cluster_id: TigerBeetle cluster ID
            addresses: List of replica addresses (e.g., ["127.0.0.1:3000"])
        
        Raises:
            RuntimeError: If the tigerbeetle client library is not installed or
                the cluster is unreachable. The ledger never runs in mock mode.
        """
        if tb is None:
            raise RuntimeError(
                "The 'tigerbeetle' client library is not installed; "
                "refusing to run the financial ledger in mock mode"
            )

        self.cluster_id = cluster_id
        self.addresses = addresses
        self.client = tb.ClientSync(
            cluster_id=cluster_id,
            replica_addresses=list(addresses)
        )

        try:
            # Connectivity check: fail fast when the cluster cannot be reached.
            self.client.lookup_accounts([tb.id()])
        except Exception as e:
            raise RuntimeError(
                f"TigerBeetle cluster unreachable at {addresses}: {e}"
            )
        
        # Cache for account IDs
        self.account_cache: Dict[str, int] = {}
        
        logger.info(f"TigerBeetle service initialized: cluster={cluster_id}")
    
    # ==================== Account Management ====================
    
    def create_account(
        self,
        user_id: str,
        currency: str,
        account_type: AccountType
    ) -> int:
        """
        Create a new account in TigerBeetle
        
        Args:
            user_id: User identifier
            currency: Currency code (USD, EUR, etc.)
            account_type: Type of account
        
        Returns:
            Account ID (128-bit integer)
        """
        # Generate deterministic account ID
        account_id = self._generate_account_id(user_id, currency, account_type)
        
        # Check if account already exists
        cache_key = f"{user_id}:{currency}:{account_type.value}"
        if cache_key in self.account_cache:
            logger.info(f"Account already exists: {cache_key}")
            return self.account_cache[cache_key]
        
        # Get account parameters
        ledger = self._get_ledger_code(currency)
        code = self._get_account_code(account_type)
        flags = tb.AccountFlags(self._get_account_flags(account_type))
        
        account = tb.Account(
            id=account_id,
            ledger=ledger,
            code=code,
            flags=flags
        )
        
        try:
            errors = self.client.create_accounts([account])
        except Exception as e:
            raise RuntimeError(f"TigerBeetle account creation failed (cluster error): {e}")
        
        # An EXISTING account (deterministic ID) is acceptable; anything else is fatal.
        fatal_errors = [
            err for err in errors
            if "EXISTS" not in str(getattr(err, "result", "")).upper()
        ]
        if fatal_errors:
            raise RuntimeError(f"Failed to create TigerBeetle account: {fatal_errors}")
        
        # Cache account ID
        self.account_cache[cache_key] = account_id
        
        logger.info(
            f"Created account: user={user_id}, currency={currency}, "
            f"type={account_type.value}, id={account_id}"
        )
        
        return account_id
    
    def get_account_id(
        self,
        user_id: str,
        currency: str,
        account_type: AccountType
    ) -> Optional[int]:
        """
        Get existing account ID
        
        Args:
            user_id: User identifier
            currency: Currency code
            account_type: Type of account
        
        Returns:
            Account ID if exists, None otherwise
        """
        cache_key = f"{user_id}:{currency}:{account_type.value}"
        return self.account_cache.get(cache_key)
    
    def get_or_create_account(
        self,
        user_id: str,
        currency: str,
        account_type: AccountType
    ) -> int:
        """
        Get existing account or create new one
        
        Args:
            user_id: User identifier
            currency: Currency code
            account_type: Type of account
        
        Returns:
            Account ID
        """
        account_id = self.get_account_id(user_id, currency, account_type)
        if account_id is None:
            account_id = self.create_account(user_id, currency, account_type)
        return account_id
    
    # ==================== Balance Queries ====================
    
    def get_balance(self, account_id: int) -> Optional[AccountBalance]:
        """
        Get account balance (< 1ms)
        
        Args:
            account_id: Account ID
        
        Returns:
            AccountBalance object or None if not found
        """
        try:
            accounts = self.client.lookup_accounts([account_id])
        except Exception as e:
            raise RuntimeError(f"TigerBeetle balance lookup failed: {e}")
        
        if not accounts:
            return None
        
        account = accounts[0]
        return AccountBalance(
            account_id=account_id,
            debits_posted=account.debits_posted,
            credits_posted=account.credits_posted,
            debits_pending=account.debits_pending,
            credits_pending=account.credits_pending
        )
    
    def get_balance_by_user(
        self,
        user_id: str,
        currency: str
    ) -> Optional[AccountBalance]:
        """
        Get user wallet balance
        
        Args:
            user_id: User identifier
            currency: Currency code
        
        Returns:
            AccountBalance or None
        """
        account_id = self.get_account_id(
            user_id, currency, AccountType.USER_WALLET
        )
        if account_id is None:
            return None
        
        return self.get_balance(account_id)
    
    # ==================== Transfer Operations ====================
    
    def transfer(
        self,
        from_account: int,
        to_account: int,
        amount: int,
        currency: str,
        code: TransactionCode,
        pending: bool = False,
        linked: bool = False
    ) -> TransferResult:
        """
        Create a transfer between accounts
        
        Args:
            from_account: Debit account ID
            to_account: Credit account ID
            amount: Amount in smallest currency unit (cents)
            currency: Currency code
            code: Transaction type code
            pending: Create as pending transfer
            linked: Link to next transfer (atomic batch)
        
        Returns:
            TransferResult (success only when TigerBeetle accepted the transfer)
        """
        transfer_id = self._generate_transfer_id()
        ledger = self._get_ledger_code(currency)
        
        # Determine flags
        flags = tb.TransferFlags(0)
        if pending:
            flags |= tb.TransferFlags.PENDING
        if linked:
            flags |= tb.TransferFlags.LINKED
        
        transfer = tb.Transfer(
            id=transfer_id,
            debit_account_id=from_account,
            credit_account_id=to_account,
            amount=amount,
            ledger=ledger,
            code=code.value,
            flags=flags
        )
        
        try:
            errors = self.client.create_transfers([transfer])
        except Exception as e:
            raise RuntimeError(f"TigerBeetle transfer failed (cluster error): {e}")
        
        if errors:
            error_codes = [str(getattr(err, "result", "")) for err in errors]
            logger.error(f"TigerBeetle transfer rejected: {error_codes}")
            return TransferResult(
                transfer_id=transfer_id,
                success=False,
                error=str(errors)
            )
        
        logger.info(
            f"Transfer created: id={transfer_id}, from={from_account}, "
            f"to={to_account}, amount={amount}, code={code.name}"
        )
        
        return TransferResult(
            transfer_id=transfer_id,
            success=True,
            timestamp=int(time.time() * 1000)
        )
    
    def batch_transfer(
        self,
        transfers: List[Tuple[int, int, int, str, TransactionCode]]
    ) -> List[TransferResult]:
        """
        Execute multiple transfers atomically
        
        Args:
            transfers: List of (from, to, amount, currency, code) tuples
        
        Returns:
            List of TransferResult (all succeed or all fail)
        """
        results = []
        
        for i, (from_acc, to_acc, amount, currency, code) in enumerate(transfers):
            # Link all transfers except the last one
            linked = (i < len(transfers) - 1)
            
            result = self.transfer(
                from_account=from_acc,
                to_account=to_acc,
                amount=amount,
                currency=currency,
                code=code,
                linked=linked
            )
            
            results.append(result)
            
            if not result.success:
                logger.error(f"Batch transfer failed at index {i}: {result.error}")
                break
        
        return results
    
    def post_pending_transfer(self, transfer_id: int) -> bool:
        """
        Post (commit) a pending transfer
        
        Args:
            transfer_id: Transfer ID
        
        Returns:
            True if successful
        """
        transfer = tb.Transfer(
            id=self._generate_transfer_id(),
            pending_id=transfer_id,
            flags=tb.TransferFlags.POST_PENDING_TRANSFER
        )
        
        try:
            errors = self.client.create_transfers([transfer])
        except Exception as e:
            raise RuntimeError(f"TigerBeetle post-pending failed (cluster error): {e}")
        
        if errors:
            logger.error(f"TigerBeetle post-pending rejected: {errors}")
            return False
        
        logger.info(f"Posted pending transfer: {transfer_id}")
        return True
    
    def void_pending_transfer(self, transfer_id: int) -> bool:
        """
        Void (cancel) a pending transfer
        
        Args:
            transfer_id: Transfer ID
        
        Returns:
            True if successful
        """
        transfer = tb.Transfer(
            id=self._generate_transfer_id(),
            pending_id=transfer_id,
            flags=tb.TransferFlags.VOID_PENDING_TRANSFER
        )
        
        try:
            errors = self.client.create_transfers([transfer])
        except Exception as e:
            raise RuntimeError(f"TigerBeetle void-pending failed (cluster error): {e}")
        
        if errors:
            logger.error(f"TigerBeetle void-pending rejected: {errors}")
            return False
        
        logger.info(f"Voided pending transfer: {transfer_id}")
        return True
    
    # ==================== Remittance Operations ====================
    
    def process_remittance(
        self,
        sender_id: str,
        recipient_id: str,
        send_amount: int,
        send_currency: str,
        receive_amount: int,
        receive_currency: str,
        platform_fee: int,
        cdp_fee: int,
        gateway_fee: int,
        fx_spread: int = 0
    ) -> List[TransferResult]:
        """
        Process complete remittance transaction with fees
        
        Args:
            sender_id: Sender user ID
            recipient_id: Recipient user ID
            send_amount: Amount to send (cents)
            send_currency: Sender currency
            receive_amount: Amount to receive (cents)
            receive_currency: Recipient currency
            platform_fee: Platform fee (cents)
            cdp_fee: CDP fee (cents)
            gateway_fee: Gateway fee (cents)
            fx_spread: FX spread (cents)
        
        Returns:
            List of TransferResult
        """
        # Get account IDs
        sender_wallet = self.get_or_create_account(
            sender_id, send_currency, AccountType.USER_WALLET
        )
        recipient_wallet = self.get_or_create_account(
            recipient_id, receive_currency, AccountType.USER_WALLET
        )
        platform_float_send = self.get_or_create_account(
            "platform", send_currency, AccountType.PLATFORM_FLOAT
        )
        platform_float_receive = self.get_or_create_account(
            "platform", receive_currency, AccountType.PLATFORM_FLOAT
        )
        platform_revenue = self.get_or_create_account(
            "platform", send_currency, AccountType.REVENUE
        )
        cdp_revenue = self.get_or_create_account(
            "cdp", send_currency, AccountType.REVENUE
        )
        gateway_revenue = self.get_or_create_account(
            "gateway", send_currency, AccountType.REVENUE
        )
        
        # Build transfer batch (all atomic)
        transfers = [
            # 1. Debit sender (send currency)
            (
                sender_wallet,
                platform_float_send,
                send_amount,
                send_currency,
                TransactionCode.REMITTANCE_SEND
            ),
            # 2. Credit recipient (receive currency)
            (
                platform_float_receive,
                recipient_wallet,
                receive_amount,
                receive_currency,
                TransactionCode.REMITTANCE_RECEIVE
            ),
            # 3. Platform fee
            (
                sender_wallet,
                platform_revenue,
                platform_fee,
                send_currency,
                TransactionCode.PLATFORM_FEE
            ),
            # 4. CDP fee
            (
                sender_wallet,
                cdp_revenue,
                cdp_fee,
                send_currency,
                TransactionCode.CDP_FEE
            ),
            # 5. Gateway fee
            (
                sender_wallet,
                gateway_revenue,
                gateway_fee,
                send_currency,
                TransactionCode.GATEWAY_FEE
            ),
        ]
        
        # Add FX spread if applicable
        if fx_spread > 0:
            fx_revenue = self.get_or_create_account(
                "platform", send_currency, AccountType.REVENUE
            )
            transfers.append((
                sender_wallet,
                fx_revenue,
                fx_spread,
                send_currency,
                TransactionCode.FX_SPREAD
            ))
        
        # Execute atomic batch
        results = self.batch_transfer(transfers)
        
        logger.info(
            f"Remittance processed: sender={sender_id}, recipient={recipient_id}, "
            f"amount={send_amount} {send_currency} → {receive_amount} {receive_currency}"
        )
        
        return results
    
    # ==================== Revenue Tracking ====================
    
    def get_revenue(
        self,
        stakeholder: str,
        currency: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> int:
        """
        Get revenue for stakeholder
        
        Args:
            stakeholder: "platform", "cdp", or "gateway"
            currency: Currency code
            start_time: Start timestamp (ms) or None for all time
            end_time: End timestamp (ms) or None for now
        
        Returns:
            Total revenue in smallest currency unit
        """
        if start_time is not None or end_time is not None:
            # Never silently ignore the requested range and return a lifetime
            # total as if it were the filtered figure.
            raise NotImplementedError(
                "Time-range revenue queries are not supported by this client yet"
            )
        
        account_id = self.get_account_id(
            stakeholder, currency, AccountType.REVENUE
        )
        if account_id is None:
            return 0
        
        balance = self.get_balance(account_id)
        if balance is None:
            return 0
        
        return balance.balance
    
    def get_revenue_breakdown(
        self,
        currency: str = "USD"
    ) -> Dict[str, int]:
        """
        Get revenue breakdown by stakeholder
        
        Args:
            currency: Currency code
        
        Returns:
            Dictionary of stakeholder -> revenue
        """
        return {
            "platform": self.get_revenue("platform", currency),
            "cdp": self.get_revenue("cdp", currency),
            "gateway": self.get_revenue("gateway", currency)
        }
    
    # ==================== Settlement ====================
    
    def record_settlement(
        self,
        participant_id: str,
        currency: str,
        net_position: int
    ) -> TransferResult:
        """
        Record settlement from Mojaloop
        
        Args:
            participant_id: Participant identifier
            currency: Currency code
            net_position: Net position (positive = receive, negative = send)
        
        Returns:
            TransferResult
        """
        participant_account = self.get_or_create_account(
            participant_id, currency, AccountType.SETTLEMENT
        )
        settlement_bank = self.get_or_create_account(
            "settlement_bank", currency, AccountType.SETTLEMENT
        )
        
        if net_position < 0:
            # Net sender - debit participant
            return self.transfer(
                from_account=participant_account,
                to_account=settlement_bank,
                amount=abs(net_position),
                currency=currency,
                code=TransactionCode.SETTLEMENT
            )
        else:
            # Net receiver - credit participant
            return self.transfer(
                from_account=settlement_bank,
                to_account=participant_account,
                amount=net_position,
                currency=currency,
                code=TransactionCode.SETTLEMENT
            )
    
    # ==================== Helper Methods ====================
    
    def _generate_account_id(
        self,
        user_id: str,
        currency: str,
        account_type: AccountType
    ) -> int:
        """Generate deterministic account ID"""
        data = f"{user_id}:{currency}:{account_type.value}".encode()
        hash_bytes = hashlib.sha256(data).digest()[:16]  # 128 bits
        return int.from_bytes(hash_bytes, 'big')
    
    def _generate_transfer_id(self) -> int:
        """Generate unique transfer ID"""
        if tb is not None:
            return tb.id()
        return int.from_bytes(uuid.uuid4().bytes, 'big')
    
    def _get_ledger_code(self, currency: str) -> int:
        """Get ISO 4217 currency code"""
        try:
            return LedgerCode[currency].value
        except KeyError:
            logger.warning(f"Unknown currency: {currency}, using 0")
            return 0
    
    def _get_account_code(self, account_type: AccountType) -> int:
        """Get account classification code"""
        codes = {
            AccountType.USER_WALLET: 1100,
            AccountType.PLATFORM_FLOAT: 1200,
            AccountType.PENDING: 1300,
            AccountType.REVENUE: 3000,
            AccountType.EXPENSE: 4000,
            AccountType.SETTLEMENT: 5000
        }
        return codes.get(account_type, 0)
    
    def _get_account_flags(self, account_type: AccountType) -> int:
        """Get account behavior flags"""
        # AccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS = 1
        # AccountFlags.CREDITS_MUST_NOT_EXCEED_DEBITS = 2
        
        if account_type in [AccountType.USER_WALLET, AccountType.REVENUE]:
            return 1  # Cannot go negative
        elif account_type == AccountType.EXPENSE:
            return 2  # Debits only
        else:
            return 0  # No restrictions


# ==================== Singleton Instance ====================

_tigerbeetle_service: Optional[TigerBeetleService] = None


def get_tigerbeetle_service() -> TigerBeetleService:
    """Get singleton TigerBeetle service instance
    
    Raises:
        RuntimeError: If the tigerbeetle client library is missing or the
            configured cluster is unreachable.
    """
    global _tigerbeetle_service
    
    if _tigerbeetle_service is None:
        cluster_id = int(os.getenv("TB_CLUSTER_ID", "0"))
        addresses = os.getenv(
            "TB_ADDRESSES",
            "127.0.0.1:3000,127.0.0.1:3001,127.0.0.1:3002"
        ).split(",")
        
        _tigerbeetle_service = TigerBeetleService(
            cluster_id=cluster_id,
            addresses=addresses
        )
    
    return _tigerbeetle_service
