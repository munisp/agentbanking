"""
Production-Ready TigerBeetle Client
Provides proper integration with TigerBeetle for financial ledger operations
Implements double-entry accounting with ACID guarantees
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import struct
import uuid

logger = logging.getLogger(__name__)


class AccountFlags(Enum):
    LINKED = 1 << 0
    DEBITS_MUST_NOT_EXCEED_CREDITS = 1 << 1
    CREDITS_MUST_NOT_EXCEED_DEBITS = 1 << 2
    HISTORY = 1 << 3


class TransferFlags(Enum):
    LINKED = 1 << 0
    PENDING = 1 << 1
    POST_PENDING_TRANSFER = 1 << 2
    VOID_PENDING_TRANSFER = 1 << 3
    BALANCING_DEBIT = 1 << 4
    BALANCING_CREDIT = 1 << 5


@dataclass
class Account:
    id: int
    debits_pending: int = 0
    debits_posted: int = 0
    credits_pending: int = 0
    credits_posted: int = 0
    user_data_128: int = 0
    user_data_64: int = 0
    user_data_32: int = 0
    reserved: int = 0
    ledger: int = 1
    code: int = 0
    flags: int = 0
    timestamp: int = 0


@dataclass
class Transfer:
    id: int
    debit_account_id: int
    credit_account_id: int
    amount: int
    pending_id: int = 0
    user_data_128: int = 0
    user_data_64: int = 0
    user_data_32: int = 0
    timeout: int = 0
    ledger: int = 1
    code: int = 0
    flags: int = 0
    timestamp: int = 0


class TigerBeetleError(Exception):
    """TigerBeetle operation error"""
    pass


class TigerBeetleClient:
    """Production TigerBeetle client with proper error handling"""
    
    ACCOUNT_SIZE = 128
    TRANSFER_SIZE = 128
    
    def __init__(
        self,
        cluster_id: int = 0,
        addresses: Optional[List[str]] = None
    ):
        self.cluster_id = cluster_id
        self.addresses = addresses or [os.getenv("TIGERBEETLE_ADDRESS", "127.0.0.1:3000")]
        self._client = None
        self._connected = False
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to TigerBeetle cluster"""
        async with self._lock:
            if self._connected:
                return True
            
            try:
                try:
                    import tigerbeetle
                    self._client = tigerbeetle.Client(
                        cluster_id=self.cluster_id,
                        addresses=self.addresses
                    )
                    self._connected = True
                    logger.info(f"Connected to TigerBeetle cluster {self.cluster_id}")
                    return True
                except ImportError:
                    logger.warning("TigerBeetle Python client not installed, using HTTP fallback")
                    self._client = TigerBeetleHTTPClient(self.addresses[0])
                    await self._client.connect()
                    self._connected = True
                    return True
                    
            except Exception as e:
                logger.error(f"Failed to connect to TigerBeetle: {e}")
                return False
    
    async def disconnect(self):
        """Disconnect from TigerBeetle"""
        async with self._lock:
            if self._client and hasattr(self._client, 'close'):
                self._client.close()
            self._connected = False
            logger.info("Disconnected from TigerBeetle")
    
    async def create_accounts(self, accounts: List[Account]) -> List[Dict[str, Any]]:
        """Create accounts in TigerBeetle"""
        if not self._connected:
            await self.connect()
        
        try:
            if hasattr(self._client, 'create_accounts'):
                account_data = [self._account_to_bytes(acc) for acc in accounts]
                results = self._client.create_accounts(account_data)
                return self._parse_account_results(results, accounts)
            else:
                return await self._client.create_accounts(accounts)
                
        except Exception as e:
            logger.error(f"Failed to create accounts: {e}")
            raise TigerBeetleError(f"Account creation failed: {e}")
    
    async def create_transfers(self, transfers: List[Transfer]) -> List[Dict[str, Any]]:
        """Create transfers in TigerBeetle"""
        if not self._connected:
            await self.connect()
        
        try:
            if hasattr(self._client, 'create_transfers'):
                transfer_data = [self._transfer_to_bytes(tr) for tr in transfers]
                results = self._client.create_transfers(transfer_data)
                return self._parse_transfer_results(results, transfers)
            else:
                return await self._client.create_transfers(transfers)
                
        except Exception as e:
            logger.error(f"Failed to create transfers: {e}")
            raise TigerBeetleError(f"Transfer creation failed: {e}")
    
    async def lookup_accounts(self, account_ids: List[int]) -> List[Account]:
        """Lookup accounts by ID"""
        if not self._connected:
            await self.connect()
        
        try:
            if hasattr(self._client, 'lookup_accounts'):
                results = self._client.lookup_accounts(account_ids)
                return [self._bytes_to_account(r) for r in results]
            else:
                return await self._client.lookup_accounts(account_ids)
                
        except Exception as e:
            logger.error(f"Failed to lookup accounts: {e}")
            raise TigerBeetleError(f"Account lookup failed: {e}")
    
    async def lookup_transfers(self, transfer_ids: List[int]) -> List[Transfer]:
        """Lookup transfers by ID"""
        if not self._connected:
            await self.connect()
        
        try:
            if hasattr(self._client, 'lookup_transfers'):
                results = self._client.lookup_transfers(transfer_ids)
                return [self._bytes_to_transfer(r) for r in results]
            else:
                return await self._client.lookup_transfers(transfer_ids)
                
        except Exception as e:
            logger.error(f"Failed to lookup transfers: {e}")
            raise TigerBeetleError(f"Transfer lookup failed: {e}")
    
    async def get_account_balance(self, account_id: int) -> Dict[str, int]:
        """Get account balance"""
        accounts = await self.lookup_accounts([account_id])
        
        if not accounts:
            raise TigerBeetleError(f"Account {account_id} not found")
        
        account = accounts[0]
        
        return {
            "debits_pending": account.debits_pending,
            "debits_posted": account.debits_posted,
            "credits_pending": account.credits_pending,
            "credits_posted": account.credits_posted,
            "balance": account.credits_posted - account.debits_posted,
            "available_balance": (
                account.credits_posted - account.debits_posted - account.debits_pending
            )
        }
    
    async def transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: int,
        ledger: int = 1,
        code: int = 0,
        user_data: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute a simple transfer between accounts"""
        transfer_id = self._generate_id()
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=from_account_id,
            credit_account_id=to_account_id,
            amount=amount,
            ledger=ledger,
            code=code,
            user_data_128=user_data or 0
        )
        
        results = await self.create_transfers([transfer])
        
        if results and results[0].get("error"):
            raise TigerBeetleError(f"Transfer failed: {results[0]['error']}")
        
        return {
            "transfer_id": transfer_id,
            "from_account": from_account_id,
            "to_account": to_account_id,
            "amount": amount,
            "status": "completed"
        }
    
    async def pending_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: int,
        timeout_seconds: int = 3600,
        ledger: int = 1,
        code: int = 0
    ) -> Dict[str, Any]:
        """Create a pending (two-phase) transfer"""
        transfer_id = self._generate_id()
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=from_account_id,
            credit_account_id=to_account_id,
            amount=amount,
            timeout=timeout_seconds,
            ledger=ledger,
            code=code,
            flags=TransferFlags.PENDING.value
        )
        
        results = await self.create_transfers([transfer])
        
        if results and results[0].get("error"):
            raise TigerBeetleError(f"Pending transfer failed: {results[0]['error']}")
        
        return {
            "transfer_id": transfer_id,
            "from_account": from_account_id,
            "to_account": to_account_id,
            "amount": amount,
            "timeout_seconds": timeout_seconds,
            "status": "pending"
        }
    
    async def post_pending_transfer(self, pending_transfer_id: int) -> Dict[str, Any]:
        """Post (commit) a pending transfer"""
        transfer_id = self._generate_id()
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=0,
            credit_account_id=0,
            amount=0,
            pending_id=pending_transfer_id,
            flags=TransferFlags.POST_PENDING_TRANSFER.value
        )
        
        results = await self.create_transfers([transfer])
        
        if results and results[0].get("error"):
            raise TigerBeetleError(f"Post pending transfer failed: {results[0]['error']}")
        
        return {
            "transfer_id": transfer_id,
            "pending_transfer_id": pending_transfer_id,
            "status": "posted"
        }
    
    async def void_pending_transfer(self, pending_transfer_id: int) -> Dict[str, Any]:
        """Void (rollback) a pending transfer"""
        transfer_id = self._generate_id()
        
        transfer = Transfer(
            id=transfer_id,
            debit_account_id=0,
            credit_account_id=0,
            amount=0,
            pending_id=pending_transfer_id,
            flags=TransferFlags.VOID_PENDING_TRANSFER.value
        )
        
        results = await self.create_transfers([transfer])
        
        if results and results[0].get("error"):
            raise TigerBeetleError(f"Void pending transfer failed: {results[0]['error']}")
        
        return {
            "transfer_id": transfer_id,
            "pending_transfer_id": pending_transfer_id,
            "status": "voided"
        }
    
    async def linked_transfers(self, transfers: List[Transfer]) -> List[Dict[str, Any]]:
        """Execute linked transfers (all succeed or all fail)"""
        for i, transfer in enumerate(transfers[:-1]):
            transfer.flags |= TransferFlags.LINKED.value
        
        return await self.create_transfers(transfers)
    
    def _generate_id(self) -> int:
        """Generate unique 128-bit ID"""
        return uuid.uuid4().int & ((1 << 128) - 1)
    
    def _account_to_bytes(self, account: Account) -> bytes:
        """Serialize account to bytes"""
        return struct.pack(
            '<QQQQQQQQIHHIxxxx',
            account.id,
            account.debits_pending,
            account.debits_posted,
            account.credits_pending,
            account.credits_posted,
            account.user_data_128,
            account.user_data_64,
            account.user_data_32,
            account.reserved,
            account.ledger,
            account.code,
            account.flags
        )
    
    def _transfer_to_bytes(self, transfer: Transfer) -> bytes:
        """Serialize transfer to bytes"""
        return struct.pack(
            '<QQQQQQQQIHHI',
            transfer.id,
            transfer.debit_account_id,
            transfer.credit_account_id,
            transfer.amount,
            transfer.pending_id,
            transfer.user_data_128,
            transfer.user_data_64,
            transfer.user_data_32,
            transfer.timeout,
            transfer.ledger,
            transfer.code,
            transfer.flags
        )
    
    def _bytes_to_account(self, data: bytes) -> Account:
        """Deserialize account from bytes"""
        unpacked = struct.unpack('<QQQQQQQQIHHIxxxxQ', data)
        return Account(
            id=unpacked[0],
            debits_pending=unpacked[1],
            debits_posted=unpacked[2],
            credits_pending=unpacked[3],
            credits_posted=unpacked[4],
            user_data_128=unpacked[5],
            user_data_64=unpacked[6],
            user_data_32=unpacked[7],
            reserved=unpacked[8],
            ledger=unpacked[9],
            code=unpacked[10],
            flags=unpacked[11],
            timestamp=unpacked[12]
        )
    
    def _bytes_to_transfer(self, data: bytes) -> Transfer:
        """Deserialize transfer from bytes"""
        unpacked = struct.unpack('<QQQQQQQQIHHIQ', data)
        return Transfer(
            id=unpacked[0],
            debit_account_id=unpacked[1],
            credit_account_id=unpacked[2],
            amount=unpacked[3],
            pending_id=unpacked[4],
            user_data_128=unpacked[5],
            user_data_64=unpacked[6],
            user_data_32=unpacked[7],
            timeout=unpacked[8],
            ledger=unpacked[9],
            code=unpacked[10],
            flags=unpacked[11],
            timestamp=unpacked[12]
        )
    
    def _parse_account_results(
        self,
        results: List[Any],
        accounts: List[Account]
    ) -> List[Dict[str, Any]]:
        """Parse account creation results"""
        parsed = []
        for i, account in enumerate(accounts):
            error = results[i] if i < len(results) else None
            parsed.append({
                "account_id": account.id,
                "error": self._error_to_string(error) if error else None,
                "success": error is None or error == 0
            })
        return parsed
    
    def _parse_transfer_results(
        self,
        results: List[Any],
        transfers: List[Transfer]
    ) -> List[Dict[str, Any]]:
        """Parse transfer creation results"""
        parsed = []
        for i, transfer in enumerate(transfers):
            error = results[i] if i < len(results) else None
            parsed.append({
                "transfer_id": transfer.id,
                "error": self._error_to_string(error) if error else None,
                "success": error is None or error == 0
            })
        return parsed
    
    def _error_to_string(self, error_code: int) -> Optional[str]:
        """Convert error code to string"""
        if error_code == 0:
            return None
        
        error_map = {
            1: "linked_event_failed",
            2: "linked_event_chain_open",
            3: "timestamp_must_be_zero",
            4: "reserved_field",
            5: "reserved_flag",
            6: "id_must_not_be_zero",
            7: "id_must_not_be_int_max",
            8: "flags_are_mutually_exclusive",
            9: "ledger_must_not_be_zero",
            10: "code_must_not_be_zero",
            11: "debit_account_id_must_not_be_zero",
            12: "credit_account_id_must_not_be_zero",
            13: "accounts_must_be_different",
            14: "pending_id_must_be_zero",
            15: "pending_id_must_not_be_zero",
            16: "pending_id_must_not_be_int_max",
            17: "pending_id_must_be_different",
            18: "timeout_reserved_for_pending_transfer",
            19: "amount_must_not_be_zero",
            20: "ledger_must_not_be_zero",
            21: "code_must_not_be_zero",
            22: "exists_with_different_flags",
            23: "exists_with_different_user_data",
            24: "exists_with_different_ledger",
            25: "exists_with_different_code",
            26: "exists",
            27: "debit_account_not_found",
            28: "credit_account_not_found",
            29: "accounts_must_have_same_ledger",
            30: "transfer_must_have_same_ledger_as_accounts",
            31: "pending_transfer_not_found",
            32: "pending_transfer_not_pending",
            33: "pending_transfer_has_different_debit_account_id",
            34: "pending_transfer_has_different_credit_account_id",
            35: "pending_transfer_has_different_ledger",
            36: "pending_transfer_has_different_code",
            37: "exceeds_credits",
            38: "exceeds_debits",
            39: "pending_transfer_has_different_amount",
            40: "pending_transfer_already_posted",
            41: "pending_transfer_already_voided",
            42: "pending_transfer_expired",
            43: "overflows_debits_pending",
            44: "overflows_credits_pending",
            45: "overflows_debits_posted",
            46: "overflows_credits_posted",
            47: "overflows_debits",
            48: "overflows_credits",
            49: "overflows_timeout"
        }
        
        return error_map.get(error_code, f"unknown_error_{error_code}")


class TigerBeetleHTTPClient:
    """HTTP fallback client for TigerBeetle when native client is unavailable"""
    
    def __init__(self, address: str):
        self.base_url = f"http://{address}"
        self._session = None
    
    async def connect(self):
        """Initialize HTTP session"""
        import httpx
        self._session = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        logger.info(f"Connected to TigerBeetle HTTP API at {self.base_url}")
    
    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.aclose()
    
    async def create_accounts(self, accounts: List[Account]) -> List[Dict[str, Any]]:
        """Create accounts via HTTP API"""
        account_data = [
            {
                "id": str(acc.id),
                "ledger": acc.ledger,
                "code": acc.code,
                "flags": acc.flags,
                "user_data_128": str(acc.user_data_128),
                "user_data_64": str(acc.user_data_64),
                "user_data_32": acc.user_data_32
            }
            for acc in accounts
        ]
        
        response = await self._session.post("/accounts", json=account_data)
        
        if response.status_code != 200:
            raise TigerBeetleError(f"HTTP error: {response.text}")
        
        return response.json()
    
    async def create_transfers(self, transfers: List[Transfer]) -> List[Dict[str, Any]]:
        """Create transfers via HTTP API"""
        transfer_data = [
            {
                "id": str(tr.id),
                "debit_account_id": str(tr.debit_account_id),
                "credit_account_id": str(tr.credit_account_id),
                "amount": str(tr.amount),
                "pending_id": str(tr.pending_id) if tr.pending_id else None,
                "ledger": tr.ledger,
                "code": tr.code,
                "flags": tr.flags,
                "timeout": tr.timeout,
                "user_data_128": str(tr.user_data_128),
                "user_data_64": str(tr.user_data_64),
                "user_data_32": tr.user_data_32
            }
            for tr in transfers
        ]
        
        response = await self._session.post("/transfers", json=transfer_data)
        
        if response.status_code != 200:
            raise TigerBeetleError(f"HTTP error: {response.text}")
        
        return response.json()
    
    async def lookup_accounts(self, account_ids: List[int]) -> List[Account]:
        """Lookup accounts via HTTP API"""
        response = await self._session.post(
            "/accounts/lookup",
            json=[str(aid) for aid in account_ids]
        )
        
        if response.status_code != 200:
            raise TigerBeetleError(f"HTTP error: {response.text}")
        
        data = response.json()
        
        return [
            Account(
                id=int(acc["id"]),
                debits_pending=int(acc.get("debits_pending", 0)),
                debits_posted=int(acc.get("debits_posted", 0)),
                credits_pending=int(acc.get("credits_pending", 0)),
                credits_posted=int(acc.get("credits_posted", 0)),
                user_data_128=int(acc.get("user_data_128", 0)),
                user_data_64=int(acc.get("user_data_64", 0)),
                user_data_32=int(acc.get("user_data_32", 0)),
                ledger=acc.get("ledger", 1),
                code=acc.get("code", 0),
                flags=acc.get("flags", 0),
                timestamp=int(acc.get("timestamp", 0))
            )
            for acc in data
        ]
    
    async def lookup_transfers(self, transfer_ids: List[int]) -> List[Transfer]:
        """Lookup transfers via HTTP API"""
        response = await self._session.post(
            "/transfers/lookup",
            json=[str(tid) for tid in transfer_ids]
        )
        
        if response.status_code != 200:
            raise TigerBeetleError(f"HTTP error: {response.text}")
        
        data = response.json()
        
        return [
            Transfer(
                id=int(tr["id"]),
                debit_account_id=int(tr["debit_account_id"]),
                credit_account_id=int(tr["credit_account_id"]),
                amount=int(tr["amount"]),
                pending_id=int(tr.get("pending_id", 0)),
                user_data_128=int(tr.get("user_data_128", 0)),
                user_data_64=int(tr.get("user_data_64", 0)),
                user_data_32=int(tr.get("user_data_32", 0)),
                timeout=tr.get("timeout", 0),
                ledger=tr.get("ledger", 1),
                code=tr.get("code", 0),
                flags=tr.get("flags", 0),
                timestamp=int(tr.get("timestamp", 0))
            )
            for tr in data
        ]


class FinancialLedger:
    """High-level financial ledger operations using TigerBeetle"""
    
    LEDGER_AGENT_FLOAT = 1
    LEDGER_CUSTOMER = 2
    LEDGER_MERCHANT = 3
    LEDGER_COMMISSION = 4
    LEDGER_FEES = 5
    LEDGER_SETTLEMENT = 6
    
    CODE_CASH_IN = 1
    CODE_CASH_OUT = 2
    CODE_TRANSFER = 3
    CODE_PAYMENT = 4
    CODE_COMMISSION = 5
    CODE_FEE = 6
    CODE_REFUND = 7
    CODE_SETTLEMENT = 8
    
    def __init__(self, client: TigerBeetleClient):
        self.client = client
    
    async def create_agent_account(
        self,
        agent_id: str,
        initial_float: int = 0
    ) -> Dict[str, Any]:
        """Create agent float account"""
        account_id = self._string_to_id(f"agent:{agent_id}")
        
        account = Account(
            id=account_id,
            ledger=self.LEDGER_AGENT_FLOAT,
            code=0,
            flags=AccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS.value | AccountFlags.HISTORY.value,
            user_data_128=self._string_to_id(agent_id)
        )
        
        results = await self.client.create_accounts([account])
        
        if results[0].get("error") and results[0]["error"] != "exists":
            raise TigerBeetleError(f"Failed to create agent account: {results[0]['error']}")
        
        if initial_float > 0:
            await self.deposit_float(agent_id, initial_float)
        
        return {
            "account_id": account_id,
            "agent_id": agent_id,
            "ledger": self.LEDGER_AGENT_FLOAT,
            "initial_float": initial_float
        }
    
    async def create_customer_account(self, customer_id: str) -> Dict[str, Any]:
        """Create customer account"""
        account_id = self._string_to_id(f"customer:{customer_id}")
        
        account = Account(
            id=account_id,
            ledger=self.LEDGER_CUSTOMER,
            code=0,
            flags=AccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS.value | AccountFlags.HISTORY.value,
            user_data_128=self._string_to_id(customer_id)
        )
        
        results = await self.client.create_accounts([account])
        
        if results[0].get("error") and results[0]["error"] != "exists":
            raise TigerBeetleError(f"Failed to create customer account: {results[0]['error']}")
        
        return {
            "account_id": account_id,
            "customer_id": customer_id,
            "ledger": self.LEDGER_CUSTOMER
        }
    
    async def deposit_float(self, agent_id: str, amount: int) -> Dict[str, Any]:
        """Deposit float to agent account"""
        agent_account_id = self._string_to_id(f"agent:{agent_id}")
        settlement_account_id = self._get_settlement_account_id()
        
        return await self.client.transfer(
            from_account_id=settlement_account_id,
            to_account_id=agent_account_id,
            amount=amount,
            ledger=self.LEDGER_AGENT_FLOAT,
            code=self.CODE_SETTLEMENT
        )
    
    async def cash_in(
        self,
        agent_id: str,
        customer_id: str,
        amount: int,
        fee: int = 0
    ) -> Dict[str, Any]:
        """Process cash-in transaction (customer deposits cash with agent)"""
        agent_account_id = self._string_to_id(f"agent:{agent_id}")
        customer_account_id = self._string_to_id(f"customer:{customer_id}")
        fee_account_id = self._get_fee_account_id()
        
        transfers = []
        
        main_transfer = Transfer(
            id=self.client._generate_id(),
            debit_account_id=agent_account_id,
            credit_account_id=customer_account_id,
            amount=amount,
            ledger=self.LEDGER_CUSTOMER,
            code=self.CODE_CASH_IN
        )
        transfers.append(main_transfer)
        
        if fee > 0:
            fee_transfer = Transfer(
                id=self.client._generate_id(),
                debit_account_id=customer_account_id,
                credit_account_id=fee_account_id,
                amount=fee,
                ledger=self.LEDGER_FEES,
                code=self.CODE_FEE
            )
            transfers.append(fee_transfer)
        
        results = await self.client.linked_transfers(transfers)
        
        for result in results:
            if result.get("error"):
                raise TigerBeetleError(f"Cash-in failed: {result['error']}")
        
        return {
            "transaction_type": "cash_in",
            "agent_id": agent_id,
            "customer_id": customer_id,
            "amount": amount,
            "fee": fee,
            "net_amount": amount - fee,
            "transfer_ids": [r["transfer_id"] for r in results],
            "status": "completed"
        }
    
    async def cash_out(
        self,
        agent_id: str,
        customer_id: str,
        amount: int,
        fee: int = 0
    ) -> Dict[str, Any]:
        """Process cash-out transaction (customer withdraws cash from agent)"""
        agent_account_id = self._string_to_id(f"agent:{agent_id}")
        customer_account_id = self._string_to_id(f"customer:{customer_id}")
        fee_account_id = self._get_fee_account_id()
        
        transfers = []
        
        if fee > 0:
            fee_transfer = Transfer(
                id=self.client._generate_id(),
                debit_account_id=customer_account_id,
                credit_account_id=fee_account_id,
                amount=fee,
                ledger=self.LEDGER_FEES,
                code=self.CODE_FEE
            )
            transfers.append(fee_transfer)
        
        main_transfer = Transfer(
            id=self.client._generate_id(),
            debit_account_id=customer_account_id,
            credit_account_id=agent_account_id,
            amount=amount,
            ledger=self.LEDGER_CUSTOMER,
            code=self.CODE_CASH_OUT
        )
        transfers.append(main_transfer)
        
        results = await self.client.linked_transfers(transfers)
        
        for result in results:
            if result.get("error"):
                raise TigerBeetleError(f"Cash-out failed: {result['error']}")
        
        return {
            "transaction_type": "cash_out",
            "agent_id": agent_id,
            "customer_id": customer_id,
            "amount": amount,
            "fee": fee,
            "total_deducted": amount + fee,
            "transfer_ids": [r["transfer_id"] for r in results],
            "status": "completed"
        }
    
    async def transfer_funds(
        self,
        from_customer_id: str,
        to_customer_id: str,
        amount: int,
        fee: int = 0
    ) -> Dict[str, Any]:
        """Transfer funds between customers"""
        from_account_id = self._string_to_id(f"customer:{from_customer_id}")
        to_account_id = self._string_to_id(f"customer:{to_customer_id}")
        fee_account_id = self._get_fee_account_id()
        
        transfers = []
        
        if fee > 0:
            fee_transfer = Transfer(
                id=self.client._generate_id(),
                debit_account_id=from_account_id,
                credit_account_id=fee_account_id,
                amount=fee,
                ledger=self.LEDGER_FEES,
                code=self.CODE_FEE
            )
            transfers.append(fee_transfer)
        
        main_transfer = Transfer(
            id=self.client._generate_id(),
            debit_account_id=from_account_id,
            credit_account_id=to_account_id,
            amount=amount,
            ledger=self.LEDGER_CUSTOMER,
            code=self.CODE_TRANSFER
        )
        transfers.append(main_transfer)
        
        results = await self.client.linked_transfers(transfers)
        
        for result in results:
            if result.get("error"):
                raise TigerBeetleError(f"Transfer failed: {result['error']}")
        
        return {
            "transaction_type": "transfer",
            "from_customer_id": from_customer_id,
            "to_customer_id": to_customer_id,
            "amount": amount,
            "fee": fee,
            "total_deducted": amount + fee,
            "transfer_ids": [r["transfer_id"] for r in results],
            "status": "completed"
        }
    
    async def get_agent_balance(self, agent_id: str) -> Dict[str, Any]:
        """Get agent float balance"""
        account_id = self._string_to_id(f"agent:{agent_id}")
        balance = await self.client.get_account_balance(account_id)
        
        return {
            "agent_id": agent_id,
            "float_balance": balance["balance"],
            "available_float": balance["available_balance"],
            "pending_debits": balance["debits_pending"],
            "pending_credits": balance["credits_pending"]
        }
    
    async def get_customer_balance(self, customer_id: str) -> Dict[str, Any]:
        """Get customer balance"""
        account_id = self._string_to_id(f"customer:{customer_id}")
        balance = await self.client.get_account_balance(account_id)
        
        return {
            "customer_id": customer_id,
            "balance": balance["balance"],
            "available_balance": balance["available_balance"],
            "pending_debits": balance["debits_pending"],
            "pending_credits": balance["credits_pending"]
        }
    
    def _string_to_id(self, s: str) -> int:
        """Convert string to 128-bit ID"""
        import hashlib
        hash_bytes = hashlib.sha256(s.encode()).digest()[:16]
        return int.from_bytes(hash_bytes, 'little')
    
    def _get_settlement_account_id(self) -> int:
        """Get settlement account ID"""
        return self._string_to_id("system:settlement")
    
    def _get_fee_account_id(self) -> int:
        """Get fee account ID"""
        return self._string_to_id("system:fees")
    
    def _get_commission_account_id(self) -> int:
        """Get commission account ID"""
        return self._string_to_id("system:commission")
