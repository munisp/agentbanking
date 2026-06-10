"""
Cryptocurrency Integration Service
Stablecoin support for remittances (USDC, USDT)

Features:
- On-ramp/off-ramp
- Multi-chain support (Ethereum, Polygon, Stellar)
- Instant settlement
- Low fees (0.1-0.5%)
- 24/7 availability
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import httpx


class Blockchain(Enum):
    """Supported blockchains"""
    ETHEREUM = "ETHEREUM"
    POLYGON = "POLYGON"
    STELLAR = "STELLAR"


class Stablecoin(Enum):
    """Supported stablecoins"""
    USDC = "USDC"
    USDT = "USDT"


class TransactionStatus(Enum):
    """Transaction status"""
    PENDING = "PENDING"
    CONFIRMING = "CONFIRMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CryptoService:
    """
    Cryptocurrency Integration Service
    
    Provides stablecoin on/off-ramp for remittances
    
    Features:
    - USDC/USDT support
    - Multi-chain (Ethereum, Polygon, Stellar)
    - Instant settlement
    - Low fees
    - KYC/AML compliance
    - Wallet management
    """
    
    def __init__(
        self,
        exchange_api_url: str,
        exchange_api_key: str,
        exchange_api_secret: str,
        blockchain_rpc_urls: Dict[str, str],
        hot_wallet_addresses: Dict[str, str]
    ):
        """
        Initialize crypto service
        
        Args:
            exchange_api_url: Exchange API endpoint
            exchange_api_key: Exchange API key
            exchange_api_secret: Exchange API secret
            blockchain_rpc_urls: RPC URLs for each blockchain
            hot_wallet_addresses: Hot wallet addresses
        """
        self.exchange_api_url = exchange_api_url
        self.exchange_api_key = exchange_api_key
        self.exchange_api_secret = exchange_api_secret
        self.blockchain_rpc_urls = blockchain_rpc_urls
        self.hot_wallet_addresses = hot_wallet_addresses
        
        self.client: Optional[httpx.AsyncClient] = None
        self._transactions: Dict[str, Dict] = {}
        self._wallets: Dict[str, Dict] = {}
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=60)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def fiat_to_crypto(
        self,
        transaction_id: str,
        user_id: str,
        fiat_amount: Decimal,
        fiat_currency: str,
        stablecoin: Stablecoin,
        blockchain: Blockchain,
        destination_address: str
    ) -> Dict:
        """
        Convert fiat to cryptocurrency (on-ramp)
        
        Args:
            transaction_id: Transaction ID
            user_id: User ID
            fiat_amount: Fiat amount
            fiat_currency: Fiat currency code
            stablecoin: Target stablecoin
            blockchain: Target blockchain
            destination_address: Recipient wallet address
            
        Returns:
            On-ramp result
        """
        if not self.client:
            raise RuntimeError("Service not initialized")
        
        # Validate address
        if not self._validate_address(destination_address, blockchain):
            return {
                "status": "REJECTED",
                "reason": "Invalid wallet address"
            }
        
        # Get exchange rate
        rate = await self._get_exchange_rate(fiat_currency, stablecoin.value)
        
        if not rate:
            return {
                "status": "FAILED",
                "reason": "Unable to get exchange rate"
            }
        
        # Calculate crypto amount
        crypto_amount = fiat_amount / Decimal(str(rate))
        
        # Calculate fee (0.5%)
        fee = fiat_amount * Decimal("0.005")
        net_crypto_amount = (fiat_amount - fee) / Decimal(str(rate))
        
        try:
            # Execute exchange order
            order_result = await self._execute_exchange_order(
                fiat_amount=fiat_amount,
                fiat_currency=fiat_currency,
                crypto_amount=net_crypto_amount,
                stablecoin=stablecoin
            )
            
            if order_result["status"] != "SUCCESS":
                return order_result
            
            # Send crypto to destination
            tx_hash = await self._send_crypto(
                stablecoin=stablecoin,
                blockchain=blockchain,
                amount=net_crypto_amount,
                to_address=destination_address
            )
            
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "type": "FIAT_TO_CRYPTO",
                "fiat_amount": float(fiat_amount),
                "fiat_currency": fiat_currency,
                "crypto_amount": float(net_crypto_amount),
                "stablecoin": stablecoin.value,
                "blockchain": blockchain.value,
                "destination_address": destination_address,
                "tx_hash": tx_hash,
                "status": TransactionStatus.CONFIRMING.value,
                "fee": float(fee),
                "initiated_at": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "crypto_amount": float(net_crypto_amount),
                "stablecoin": stablecoin.value,
                "blockchain": blockchain.value,
                "tx_hash": tx_hash,
                "fee": float(fee),
                "estimated_confirmation": self._estimate_confirmation_time(blockchain)
            }
            
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e)
            }
    
    async def crypto_to_fiat(
        self,
        transaction_id: str,
        user_id: str,
        crypto_amount: Decimal,
        stablecoin: Stablecoin,
        blockchain: Blockchain,
        fiat_currency: str,
        bank_account: Dict
    ) -> Dict:
        """
        Convert cryptocurrency to fiat (off-ramp)
        
        Args:
            transaction_id: Transaction ID
            user_id: User ID
            crypto_amount: Crypto amount
            stablecoin: Source stablecoin
            blockchain: Source blockchain
            fiat_currency: Target fiat currency
            bank_account: Bank account details
            
        Returns:
            Off-ramp result
        """
        if not self.client:
            raise RuntimeError("Service not initialized")
        
        # Get exchange rate
        rate = await self._get_exchange_rate(fiat_currency, stablecoin.value)
        
        if not rate:
            return {
                "status": "FAILED",
                "reason": "Unable to get exchange rate"
            }
        
        # Calculate fiat amount
        fiat_amount = crypto_amount * Decimal(str(rate))
        
        # Calculate fee (0.5%)
        fee = fiat_amount * Decimal("0.005")
        net_fiat_amount = fiat_amount - fee
        
        try:
            # Verify crypto balance
            balance = await self._get_crypto_balance(
                user_id=user_id,
                stablecoin=stablecoin,
                blockchain=blockchain
            )
            
            if balance < crypto_amount:
                return {
                    "status": "REJECTED",
                    "reason": "Insufficient balance"
                }
            
            # Execute exchange order
            order_result = await self._execute_exchange_order(
                fiat_amount=net_fiat_amount,
                fiat_currency=fiat_currency,
                crypto_amount=crypto_amount,
                stablecoin=stablecoin,
                direction="SELL"
            )
            
            if order_result["status"] != "SUCCESS":
                return order_result
            
            # Initiate bank transfer
            bank_transfer_result = await self._initiate_bank_transfer(
                amount=net_fiat_amount,
                currency=fiat_currency,
                bank_account=bank_account
            )
            
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "type": "CRYPTO_TO_FIAT",
                "crypto_amount": float(crypto_amount),
                "stablecoin": stablecoin.value,
                "blockchain": blockchain.value,
                "fiat_amount": float(net_fiat_amount),
                "fiat_currency": fiat_currency,
                "bank_reference": bank_transfer_result.get("reference"),
                "status": TransactionStatus.CONFIRMING.value,
                "fee": float(fee),
                "initiated_at": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "fiat_amount": float(net_fiat_amount),
                "fiat_currency": fiat_currency,
                "bank_reference": bank_transfer_result.get("reference"),
                "fee": float(fee),
                "estimated_completion": "1-2 business days"
            }
            
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e)
            }
    
    async def send_crypto(
        self,
        transaction_id: str,
        user_id: str,
        stablecoin: Stablecoin,
        blockchain: Blockchain,
        amount: Decimal,
        to_address: str
    ) -> Dict:
        """Send cryptocurrency"""
        if not self.client:
            raise RuntimeError("Service not initialized")
        
        # Validate address
        if not self._validate_address(to_address, blockchain):
            return {
                "status": "REJECTED",
                "reason": "Invalid wallet address"
            }
        
        # Check balance
        balance = await self._get_crypto_balance(user_id, stablecoin, blockchain)
        
        if balance < amount:
            return {
                "status": "REJECTED",
                "reason": "Insufficient balance"
            }
        
        try:
            # Send transaction
            tx_hash = await self._send_crypto(
                stablecoin=stablecoin,
                blockchain=blockchain,
                amount=amount,
                to_address=to_address
            )
            
            # Calculate fee
            fee = await self._estimate_gas_fee(blockchain)
            
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "type": "CRYPTO_TRANSFER",
                "amount": float(amount),
                "stablecoin": stablecoin.value,
                "blockchain": blockchain.value,
                "to_address": to_address,
                "tx_hash": tx_hash,
                "status": TransactionStatus.CONFIRMING.value,
                "fee": float(fee),
                "initiated_at": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "tx_hash": tx_hash,
                "fee": float(fee),
                "estimated_confirmation": self._estimate_confirmation_time(blockchain)
            }
            
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e)
            }
    
    async def get_transaction_status(
        self,
        transaction_id: str
    ) -> Dict:
        """Get transaction status"""
        if transaction_id not in self._transactions:
            return {"status": "NOT_FOUND"}
        
        txn = self._transactions[transaction_id]
        
        # Check blockchain confirmation if applicable
        if "tx_hash" in txn and txn["status"] == TransactionStatus.CONFIRMING.value:
            confirmations = await self._get_confirmations(
                tx_hash=txn["tx_hash"],
                blockchain=Blockchain[txn["blockchain"]]
            )
            
            required_confirmations = self._get_required_confirmations(
                Blockchain[txn["blockchain"]]
            )
            
            if confirmations >= required_confirmations:
                txn["status"] = TransactionStatus.COMPLETED.value
                txn["completed_at"] = datetime.now(timezone.utc).isoformat()
                txn["confirmations"] = confirmations
        
        return txn
    
    async def _get_exchange_rate(
        self,
        fiat_currency: str,
        crypto: str
    ) -> Optional[float]:
        """Get exchange rate"""
        if not self.client:
            return None
        
        try:
            response = await self.client.get(
                f"{self.exchange_api_url}/rates",
                params={
                    "from": fiat_currency,
                    "to": crypto
                },
                headers={"Authorization": f"Bearer {self.exchange_api_key}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("rate")
            
            return None
            
        except:
            return None
    
    async def _execute_exchange_order(
        self,
        fiat_amount: Decimal,
        fiat_currency: str,
        crypto_amount: Decimal,
        stablecoin: Stablecoin,
        direction: str = "BUY"
    ) -> Dict:
        """Execute exchange order"""
        if not self.client:
            return {"status": "FAILED"}
        
        try:
            response = await self.client.post(
                f"{self.exchange_api_url}/orders",
                json={
                    "direction": direction,
                    "fiat_currency": fiat_currency,
                    "fiat_amount": float(fiat_amount),
                    "crypto": stablecoin.value,
                    "crypto_amount": float(crypto_amount)
                },
                headers={"Authorization": f"Bearer {self.exchange_api_key}"}
            )
            
            response.raise_for_status()
            
            return {
                "status": "SUCCESS",
                "order_id": response.json().get("order_id")
            }
            
        except:
            return {"status": "FAILED"}
    
    async def _send_crypto(
        self,
        stablecoin: Stablecoin,
        blockchain: Blockchain,
        amount: Decimal,
        to_address: str
    ) -> str:
        """Send cryptocurrency on blockchain"""
        # Simplified - would use web3.py or stellar-sdk in production
        # Return mock transaction hash
        return f"0x{hashlib.sha256(f'{stablecoin}{blockchain}{amount}{to_address}'.encode()).hexdigest()}"
    
    async def _get_crypto_balance(
        self,
        user_id: str,
        stablecoin: Stablecoin,
        blockchain: Blockchain
    ) -> Decimal:
        """Get user crypto balance"""
        # Simplified - would query actual blockchain
        return Decimal("1000")  # Mock balance
    
    async def _initiate_bank_transfer(
        self,
        amount: Decimal,
        currency: str,
        bank_account: Dict
    ) -> Dict:
        """Initiate bank transfer for off-ramp"""
        # Would integrate with ACH/SWIFT/etc
        return {
            "reference": f"BT{uuid.uuid4().hex[:8].upper()}"
        }
    
    async def _estimate_gas_fee(self, blockchain: Blockchain) -> Decimal:
        """Estimate gas fee"""
        fees = {
            Blockchain.ETHEREUM: Decimal("5.00"),  # ~$5
            Blockchain.POLYGON: Decimal("0.01"),   # ~$0.01
            Blockchain.STELLAR: Decimal("0.00001") # ~$0.00001
        }
        return fees.get(blockchain, Decimal("1.00"))
    
    async def _get_confirmations(
        self,
        tx_hash: str,
        blockchain: Blockchain
    ) -> int:
        """Get transaction confirmations"""
        # Simplified - would query actual blockchain
        return 12  # Mock confirmations
    
    def _get_required_confirmations(self, blockchain: Blockchain) -> int:
        """Get required confirmations"""
        confirmations = {
            Blockchain.ETHEREUM: 12,
            Blockchain.POLYGON: 128,
            Blockchain.STELLAR: 1
        }
        return confirmations.get(blockchain, 6)
    
    def _validate_address(self, address: str, blockchain: Blockchain) -> bool:
        """Validate wallet address"""
        if blockchain == Blockchain.ETHEREUM or blockchain == Blockchain.POLYGON:
            # Ethereum address validation
            return address.startswith("0x") and len(address) == 42
        elif blockchain == Blockchain.STELLAR:
            # Stellar address validation
            return address.startswith("G") and len(address) == 56
        return False
    
    def _estimate_confirmation_time(self, blockchain: Blockchain) -> str:
        """Estimate confirmation time"""
        times = {
            Blockchain.ETHEREUM: "2-5 minutes",
            Blockchain.POLYGON: "1-2 minutes",
            Blockchain.STELLAR: "5-10 seconds"
        }
        return times.get(blockchain, "5 minutes")
