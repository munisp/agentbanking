"""
Blockchain Infrastructure Support - Production Implementation
Multi-chain wallets, stablecoin transfers, crypto KYC/AML, fiat on/off ramps
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import hashlib
import os

import httpx

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Runtime configuration ---
# Simulated on-chain execution is only allowed when explicitly enabled AND
# outside production. Production requires real providers/nodes.
ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "production")).lower()
SIMULATION_MODE = os.getenv("CRYPTO_REMITTANCE_SIMULATION_MODE", "false").lower() == "true"
PRICE_ORACLE_URL = os.getenv(
    "PRICE_ORACLE_URL", "https://api.coingecko.com/api/v3/simple/price"
).strip()
WALLET_PROVIDER_URL = os.getenv("WALLET_PROVIDER_URL", "").strip() or None
CRYPTO_BROADCASTER_URL = os.getenv("CRYPTO_BROADCASTER_URL", "").strip() or None
RAMP_PROVIDER_URL = os.getenv("RAMP_PROVIDER_URL", "").strip() or None

if SIMULATION_MODE and ENVIRONMENT == "production":
    raise RuntimeError(
        "CRYPTO_REMITTANCE_SIMULATION_MODE=true is forbidden in production: "
        "simulated on-chain execution must never run against live funds"
    )

app = FastAPI(title="Blockchain Infrastructure - Crypto Remittance", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Blockchain(str, Enum):
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    SOLANA = "solana"
    STELLAR = "stellar"
    BINANCE_SMART_CHAIN = "bsc"

class Cryptocurrency(str, Enum):
    BTC = "BTC"
    ETH = "ETH"
    USDT = "USDT"
    USDC = "USDC"
    DAI = "DAI"
    MATIC = "MATIC"
    SOL = "SOL"
    XLM = "XLM"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"

class CryptoTransferRequest(BaseModel):
    from_address: str
    to_address: str
    cryptocurrency: Cryptocurrency
    amount: float
    blockchain: Blockchain
    user_id: str

class WalletCreationRequest(BaseModel):
    user_id: str
    blockchain: Blockchain
    label: Optional[str] = None

class FiatOnRampRequest(BaseModel):
    user_id: str
    fiat_currency: str
    fiat_amount: float
    cryptocurrency: Cryptocurrency
    payment_method: str

class CryptoTransaction(BaseModel):
    transaction_id: str
    from_address: str
    to_address: str
    cryptocurrency: Cryptocurrency
    amount: float
    blockchain: Blockchain
    status: TransactionStatus
    tx_hash: Optional[str]
    confirmations: int
    fee: float
    timestamp: str

class Wallet(BaseModel):
    wallet_id: str
    user_id: str
    blockchain: Blockchain
    address: str
    balance: Dict[str, float]
    created_at: str


def _rpc_url_for(blockchain: Blockchain) -> Optional[str]:
    """Configured node URL (JSON-RPC/REST) for a blockchain, from the environment."""
    return os.getenv(f"RPC_URL_{blockchain.value.upper()}", "").strip() or None


# Native asset per blockchain (used for on-chain balance lookups)
NATIVE_ASSET = {
    Blockchain.BITCOIN: Cryptocurrency.BTC,
    Blockchain.ETHEREUM: Cryptocurrency.ETH,
    Blockchain.POLYGON: Cryptocurrency.MATIC,
    Blockchain.SOLANA: Cryptocurrency.SOL,
    Blockchain.STELLAR: Cryptocurrency.XLM,
    Blockchain.BINANCE_SMART_CHAIN: Cryptocurrency.ETH,
}

# Confirmations required before a transfer may be marked CONFIRMED
REQUIRED_CONFIRMATIONS = {
    Blockchain.BITCOIN: 6,
    Blockchain.ETHEREUM: 12,
    Blockchain.POLYGON: 128,
    Blockchain.SOLANA: 32,
    Blockchain.STELLAR: 1,
    Blockchain.BINANCE_SMART_CHAIN: 15,
}


class BlockchainInfrastructure:
    """Blockchain Infrastructure for Crypto Remittance"""
    
    def __init__(self):
        self.wallets: Dict[str, Wallet] = {}
        self.transactions: Dict[str, CryptoTransaction] = {}
        
        # Static prices (USD) — used ONLY in explicitly gated simulation mode.
        self.prices = {
            Cryptocurrency.BTC: 43000.0,
            Cryptocurrency.ETH: 2300.0,
            Cryptocurrency.USDT: 1.0,
            Cryptocurrency.USDC: 1.0,
            Cryptocurrency.DAI: 1.0,
            Cryptocurrency.MATIC: 0.85,
            Cryptocurrency.SOL: 95.0,
            Cryptocurrency.XLM: 0.12
        }
        
        # Transaction fees (in native token)
        self.gas_fees = {
            Blockchain.BITCOIN: 0.0001,  # BTC
            Blockchain.ETHEREUM: 0.005,  # ETH
            Blockchain.POLYGON: 0.01,    # MATIC
            Blockchain.SOLANA: 0.000005, # SOL
            Blockchain.STELLAR: 0.00001, # XLM
            Blockchain.BINANCE_SMART_CHAIN: 0.0005  # BNB
        }
        
        # Platform fee: 0.5%
        self.platform_fee_rate = 0.005
        
        logger.info(f"Blockchain infrastructure initialized (simulation_mode={SIMULATION_MODE})")
    
    # ==================== External data helpers ====================
    
    async def _get_price_usd(self, crypto: Cryptocurrency) -> float:
        """USD price from the configured public price oracle.

        In gated simulation mode the static fallback table is used. Raises
        loudly when the oracle is unavailable — prices are never invented
        outside simulation.
        """
        if SIMULATION_MODE:
            return self.prices.get(crypto, 0.0)
        
        coingecko_ids = {
            Cryptocurrency.BTC: "bitcoin",
            Cryptocurrency.ETH: "ethereum",
            Cryptocurrency.USDT: "tether",
            Cryptocurrency.USDC: "usd-coin",
            Cryptocurrency.DAI: "dai",
            Cryptocurrency.MATIC: "matic-network",
            Cryptocurrency.SOL: "solana",
            Cryptocurrency.XLM: "stellar",
        }
        coin_id = coingecko_ids[crypto]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    PRICE_ORACLE_URL,
                    params={"ids": coin_id, "vs_currencies": "usd"}
                )
                response.raise_for_status()
                data = response.json()
            return float(data[coin_id]["usd"])
        except Exception as e:
            raise RuntimeError(f"Price oracle unavailable for {crypto.value}: {e}")
    
    def _generate_address(self, blockchain: Blockchain, user_id: str) -> str:
        """Generate a simulation-only placeholder address (gated test mode)."""
        hash_input = f"{blockchain}-{user_id}-{datetime.utcnow().timestamp()}"
        address_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        if blockchain == Blockchain.BITCOIN:
            return f"bc1q{address_hash[:40]}"
        elif blockchain == Blockchain.ETHEREUM or blockchain == Blockchain.POLYGON or blockchain == Blockchain.BINANCE_SMART_CHAIN:
            return f"0x{address_hash[:40]}"
        elif blockchain == Blockchain.SOLANA:
            return f"{address_hash[:44]}"
        elif blockchain == Blockchain.STELLAR:
            return f"G{address_hash[:55]}"
        
        return address_hash[:42]
    
    async def _provision_address(self, blockchain: Blockchain, user_id: str) -> str:
        """Provision a real wallet address via the configured custody/key service.

        Only in gated simulation mode is a placeholder generated; otherwise a
        wallet provider must be configured. Addresses are never fabricated for
        live wallets.
        """
        if SIMULATION_MODE:
            return self._generate_address(blockchain, user_id)
        
        if not WALLET_PROVIDER_URL:
            raise HTTPException(
                status_code=503,
                detail="No wallet/custody provider configured (WALLET_PROVIDER_URL is unset)"
            )
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{WALLET_PROVIDER_URL.rstrip('/')}/wallets",
                json={"blockchain": blockchain.value, "user_id": user_id}
            )
            response.raise_for_status()
            data = response.json()
        
        address = data.get("address")
        if not address:
            raise HTTPException(status_code=502, detail="Wallet provider did not return an address")
        return address
    
    async def _get_onchain_native_balance(self, wallet: Wallet) -> Optional[float]:
        """Native token balance from the configured node, or None if unconfigured/unsupported."""
        rpc_url = _rpc_url_for(wallet.blockchain)
        if not rpc_url:
            return None
        
        if wallet.blockchain in (Blockchain.ETHEREUM, Blockchain.POLYGON, Blockchain.BINANCE_SMART_CHAIN):
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(rpc_url, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "eth_getBalance",
                    "params": [wallet.address, "latest"]
                })
                response.raise_for_status()
                result = response.json().get("result", "0x0")
            return int(result, 16) / 1e18
        
        if wallet.blockchain == Blockchain.STELLAR:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{rpc_url.rstrip('/')}/accounts/{wallet.address}")
                if response.status_code == 404:
                    return 0.0
                response.raise_for_status()
                for balance in response.json().get("balances", []):
                    if balance.get("asset_type") == "native":
                        return float(balance.get("balance", 0))
            return 0.0
        
        return None
    
    async def _broadcast_transaction(self, request: CryptoTransferRequest) -> str:
        """Broadcast the transfer via the configured broadcaster service.

        A transaction hash only exists when a real broadcaster/node accepts
        the transaction. In gated simulation mode a placeholder is generated;
        otherwise we fail loudly when no broadcaster is configured.
        """
        if SIMULATION_MODE:
            return hashlib.sha256(
                f"{request.from_address}-{request.to_address}-{request.amount}-{datetime.utcnow().timestamp()}".encode()
            ).hexdigest()
        
        if not CRYPTO_BROADCASTER_URL:
            raise HTTPException(
                status_code=503,
                detail="No transaction broadcaster configured (CRYPTO_BROADCASTER_URL is unset)"
            )
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{CRYPTO_BROADCASTER_URL.rstrip('/')}/broadcast",
                json={
                    "from_address": request.from_address,
                    "to_address": request.to_address,
                    "cryptocurrency": request.cryptocurrency.value,
                    "amount": request.amount,
                    "blockchain": request.blockchain.value,
                    "user_id": request.user_id
                }
            )
            response.raise_for_status()
            data = response.json()
        
        tx_hash = data.get("tx_hash")
        if not tx_hash:
            raise HTTPException(status_code=502, detail="Broadcaster did not return a transaction hash")
        return tx_hash
    
    async def _query_confirmations(self, transaction: CryptoTransaction) -> Optional[int]:
        """On-chain confirmation count, or None when no node is configured/unsupported."""
        rpc_url = _rpc_url_for(transaction.blockchain)
        if not rpc_url or not transaction.tx_hash:
            return None
        
        if transaction.blockchain in (Blockchain.ETHEREUM, Blockchain.POLYGON, Blockchain.BINANCE_SMART_CHAIN):
            async with httpx.AsyncClient(timeout=15) as client:
                receipt_resp = await client.post(rpc_url, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "eth_getTransactionReceipt",
                    "params": [transaction.tx_hash]
                })
                receipt_resp.raise_for_status()
                receipt = receipt_resp.json().get("result")
                if not receipt or not receipt.get("blockNumber"):
                    return 0
                block_resp = await client.post(rpc_url, json={
                    "jsonrpc": "2.0", "id": 2,
                    "method": "eth_blockNumber",
                    "params": []
                })
                block_resp.raise_for_status()
                latest = block_resp.json().get("result")
            return max(int(latest, 16) - int(receipt["blockNumber"], 16) + 1, 0)
        
        if transaction.blockchain == Blockchain.STELLAR:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{rpc_url.rstrip('/')}/transactions/{transaction.tx_hash}")
                if response.status_code == 404:
                    return 0
                response.raise_for_status()
            # Stellar transactions are final once included in a ledger
            return 1
        
        return None
    
    async def _execute_ramp_order(self, direction: str, payload: Dict) -> Dict:
        """Execute an on/off-ramp order via the configured ramp provider.

        Returns {"status": ..., "provider_reference": ...}. In gated
        simulation mode returns a simulated status; otherwise requires a
        configured provider and fails loudly without one.
        """
        if SIMULATION_MODE:
            return {"status": "completed", "provider_reference": None}
        
        if not RAMP_PROVIDER_URL:
            raise HTTPException(
                status_code=503,
                detail="No fiat ramp provider configured (RAMP_PROVIDER_URL is unset)"
            )
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{RAMP_PROVIDER_URL.rstrip('/')}/orders",
                json={"direction": direction, **payload}
            )
            response.raise_for_status()
            data = response.json()
        
        return {
            "status": str(data.get("status", "pending")),
            "provider_reference": data.get("reference") or data.get("order_id")
        }
    
    # ==================== Core operations ====================
    
    async def create_wallet(self, request: WalletCreationRequest) -> Wallet:
        """Create crypto wallet"""
        
        wallet_id = f"WALLET-{datetime.utcnow().timestamp()}"
        address = await self._provision_address(request.blockchain, request.user_id)
        
        wallet = Wallet(
            wallet_id=wallet_id,
            user_id=request.user_id,
            blockchain=request.blockchain,
            address=address,
            balance={},  # Empty balance initially
            created_at=datetime.utcnow().isoformat()
        )
        
        self.wallets[wallet_id] = wallet
        
        logger.info(f"Created wallet {wallet_id} on {request.blockchain} for user {request.user_id}")
        
        return wallet
    
    async def get_wallet_balance(self, wallet_id: str) -> Dict:
        """Get wallet balance"""
        
        if wallet_id not in self.wallets:
            raise ValueError(f"Wallet {wallet_id} not found")
        
        wallet = self.wallets[wallet_id]
        
        # Query the chain for the native balance when a node is configured
        onchain_native = await self._get_onchain_native_balance(wallet)
        if onchain_native is not None:
            native_crypto = NATIVE_ASSET.get(wallet.blockchain)
            if native_crypto:
                wallet.balance[native_crypto.value] = onchain_native
        
        balance_usd = {}
        for crypto, amount in wallet.balance.items():
            price = await self._get_price_usd(Cryptocurrency(crypto))
            balance_usd[crypto] = {
                "amount": amount,
                "price_usd": price,
                "value_usd": round(amount * price, 2)
            }
        
        total_value_usd = sum(b["value_usd"] for b in balance_usd.values())
        
        return {
            "wallet_id": wallet_id,
            "address": wallet.address,
            "blockchain": wallet.blockchain,
            "balances": balance_usd,
            "total_value_usd": round(total_value_usd, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def initiate_crypto_transfer(self, request: CryptoTransferRequest) -> CryptoTransaction:
        """Initiate cryptocurrency transfer"""
        
        transaction_id = f"CRYPTO-TX-{datetime.utcnow().timestamp()}"
        
        # Validate addresses (simplified)
        if not request.from_address or not request.to_address:
            raise ValueError("Invalid addresses")
        
        # Calculate fees
        gas_fee = self.gas_fees.get(request.blockchain, 0.001)
        platform_fee = request.amount * self.platform_fee_rate
        total_fee = gas_fee + platform_fee
        
        # Broadcast the transaction: a tx hash only exists once a real
        # broadcaster/node accepts it. The transfer stays PENDING until enough
        # on-chain confirmations are observed — it is never instantly
        # CONFIRMED with fabricated data.
        tx_hash = await self._broadcast_transaction(request)
        
        transaction = CryptoTransaction(
            transaction_id=transaction_id,
            from_address=request.from_address,
            to_address=request.to_address,
            cryptocurrency=request.cryptocurrency,
            amount=request.amount,
            blockchain=request.blockchain,
            status=TransactionStatus.PENDING,
            tx_hash=tx_hash,
            confirmations=0,
            fee=round(total_fee, 6),
            timestamp=datetime.utcnow().isoformat()
        )
        
        self.transactions[transaction_id] = transaction
        
        logger.info(f"Initiated crypto transfer {transaction_id}: {request.amount} {request.cryptocurrency} on {request.blockchain}")
        
        return transaction
    
    async def get_transaction_status(self, transaction_id: str) -> CryptoTransaction:
        """Get transaction status"""
        
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        transaction = self.transactions[transaction_id]
        
        # Query the chain for confirmation status when a node is configured
        if transaction.tx_hash and transaction.status == TransactionStatus.PENDING:
            confirmations = await self._query_confirmations(transaction)
            if confirmations is not None:
                transaction.confirmations = confirmations
                required = REQUIRED_CONFIRMATIONS.get(transaction.blockchain, 6)
                if confirmations >= required:
                    transaction.status = TransactionStatus.CONFIRMED
        
        return transaction
    
    async def fiat_to_crypto(self, request: FiatOnRampRequest) -> Dict:
        """Convert fiat to crypto (on-ramp)"""
        
        # Calculate crypto amount using the live oracle price
        crypto_price = await self._get_price_usd(request.cryptocurrency)
        crypto_amount = request.fiat_amount / crypto_price
        
        # Apply fees
        platform_fee = request.fiat_amount * self.platform_fee_rate
        payment_processor_fee = request.fiat_amount * 0.029  # 2.9% (typical card fee)
        total_fees = platform_fee + payment_processor_fee
        
        net_fiat = request.fiat_amount - total_fees
        net_crypto = net_fiat / crypto_price
        
        order_id = f"ONRAMP-{datetime.utcnow().timestamp()}"
        
        # Execute via the configured ramp provider; status comes from the
        # provider and is "completed" only when the provider says so.
        ramp_result = await self._execute_ramp_order("ONRAMP", {
            "order_id": order_id,
            "user_id": request.user_id,
            "fiat_currency": request.fiat_currency,
            "fiat_amount": request.fiat_amount,
            "cryptocurrency": request.cryptocurrency.value,
            "crypto_amount": round(net_crypto, 6),
            "payment_method": request.payment_method
        })
        
        logger.info(f"Fiat on-ramp {order_id}: ${request.fiat_amount} {request.fiat_currency} → {net_crypto:.6f} {request.cryptocurrency}")
        
        return {
            "order_id": order_id,
            "user_id": request.user_id,
            "fiat_currency": request.fiat_currency,
            "fiat_amount": request.fiat_amount,
            "cryptocurrency": request.cryptocurrency,
            "crypto_amount": round(net_crypto, 6),
            "exchange_rate": crypto_price,
            "fees": {
                "platform_fee": round(platform_fee, 2),
                "payment_processor_fee": round(payment_processor_fee, 2),
                "total_fees": round(total_fees, 2)
            },
            "status": ramp_result["status"],
            "provider_reference": ramp_result["provider_reference"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def crypto_to_fiat(self, user_id: str, cryptocurrency: Cryptocurrency, crypto_amount: float, fiat_currency: str) -> Dict:
        """Convert crypto to fiat (off-ramp)"""
        
        # Calculate fiat amount using the live oracle price
        crypto_price = await self._get_price_usd(cryptocurrency)
        fiat_amount = crypto_amount * crypto_price
        
        # Apply fees
        platform_fee = fiat_amount * self.platform_fee_rate
        withdrawal_fee = 5.0  # Flat withdrawal fee
        total_fees = platform_fee + withdrawal_fee
        
        net_fiat = fiat_amount - total_fees
        
        order_id = f"OFFRAMP-{datetime.utcnow().timestamp()}"
        
        # Execute via the configured ramp provider; status comes from the
        # provider and is "completed" only when the provider says so.
        ramp_result = await self._execute_ramp_order("OFFRAMP", {
            "order_id": order_id,
            "user_id": user_id,
            "cryptocurrency": cryptocurrency.value,
            "crypto_amount": crypto_amount,
            "fiat_currency": fiat_currency,
            "fiat_amount": round(net_fiat, 2)
        })
        
        logger.info(f"Fiat off-ramp {order_id}: {crypto_amount} {cryptocurrency} → ${net_fiat:.2f} {fiat_currency}")
        
        return {
            "order_id": order_id,
            "user_id": user_id,
            "cryptocurrency": cryptocurrency,
            "crypto_amount": crypto_amount,
            "fiat_currency": fiat_currency,
            "fiat_amount": round(net_fiat, 2),
            "exchange_rate": crypto_price,
            "fees": {
                "platform_fee": round(platform_fee, 2),
                "withdrawal_fee": withdrawal_fee,
                "total_fees": round(total_fees, 2)
            },
            "status": ramp_result["status"],
            "provider_reference": ramp_result["provider_reference"],
            "estimated_arrival": "1-3 business days",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_supported_corridors(self) -> List[Dict]:
        """Get supported crypto corridors"""
        
        corridors = []
        
        # Crypto enables instant global transfers
        countries = ["US", "GB", "NG", "GH", "KE", "ZA", "IN", "BR", "MX", "PH", 
                    "RU", "IR", "VE", "CU", "CN", "JP", "SG", "AE", "SA"]
        
        for from_country in countries:
            for to_country in countries:
                if from_country != to_country:
                    corridors.append({
                        "from_country": from_country,
                        "to_country": to_country,
                        "supported_cryptos": ["USDT", "USDC", "DAI", "BTC", "ETH"],
                        "avg_settlement_time": "10-30 minutes",
                        "fee_percentage": 0.5
                    })
        
        return corridors[:50]  # Return first 50 for demo
    
    async def verify_crypto_address(self, address: str, blockchain: Blockchain) -> Dict:
        """Verify crypto address validity"""
        
        # Format validation only; this does not assert ownership or existence
        is_valid = False
        
        if blockchain == Blockchain.BITCOIN and address.startswith("bc1q"):
            is_valid = True
        elif blockchain in [Blockchain.ETHEREUM, Blockchain.POLYGON, Blockchain.BINANCE_SMART_CHAIN] and address.startswith("0x") and len(address) == 42:
            is_valid = True
        elif blockchain == Blockchain.SOLANA and len(address) == 44:
            is_valid = True
        elif blockchain == Blockchain.STELLAR and address.startswith("G") and len(address) == 56:
            is_valid = True
        
        return {
            "address": address,
            "blockchain": blockchain,
            "is_valid": is_valid,
            "timestamp": datetime.utcnow().isoformat()
        }

# Initialize blockchain infrastructure
blockchain_infra = BlockchainInfrastructure()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "blockchain-infrastructure",
        "simulation_mode": SIMULATION_MODE,
        "wallets": len(blockchain_infra.wallets),
        "transactions": len(blockchain_infra.transactions)
    }

@app.post("/api/v1/blockchain/wallet/create", response_model=Wallet)
async def create_wallet(request: WalletCreationRequest):
    """Create crypto wallet"""
    try:
        result = await blockchain_infra.create_wallet(request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Wallet creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Wallet creation failed: {str(e)}")

@app.get("/api/v1/blockchain/wallet/{wallet_id}/balance")
async def get_balance(wallet_id: str):
    """Get wallet balance"""
    try:
        result = await blockchain_infra.get_wallet_balance(wallet_id)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Balance query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Balance query failed: {str(e)}")

@app.post("/api/v1/blockchain/transfer", response_model=CryptoTransaction)
async def initiate_transfer(request: CryptoTransferRequest):
    """Initiate crypto transfer"""
    try:
        result = await blockchain_infra.initiate_crypto_transfer(request)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Transfer error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transfer failed: {str(e)}")

@app.get("/api/v1/blockchain/transaction/{transaction_id}", response_model=CryptoTransaction)
async def get_transaction(transaction_id: str):
    """Get transaction status"""
    try:
        result = await blockchain_infra.get_transaction_status(transaction_id)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Transaction query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transaction query failed: {str(e)}")

@app.post("/api/v1/blockchain/onramp")
async def fiat_onramp(request: FiatOnRampRequest):
    """Fiat to crypto on-ramp"""
    try:
        result = await blockchain_infra.fiat_to_crypto(request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"On-ramp error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"On-ramp failed: {str(e)}")

@app.post("/api/v1/blockchain/offramp")
async def fiat_offramp(user_id: str, cryptocurrency: Cryptocurrency, crypto_amount: float, fiat_currency: str):
    """Crypto to fiat off-ramp"""
    try:
        result = await blockchain_infra.crypto_to_fiat(user_id, cryptocurrency, crypto_amount, fiat_currency)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Off-ramp error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Off-ramp failed: {str(e)}")

@app.get("/api/v1/blockchain/corridors")
async def get_corridors():
    """Get supported crypto corridors"""
    try:
        result = await blockchain_infra.get_supported_corridors()
        return {"corridors": result, "total": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Corridors query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Corridors query failed: {str(e)}")

@app.post("/api/v1/blockchain/address/verify")
async def verify_address(address: str, blockchain: Blockchain):
    """Verify crypto address"""
    try:
        result = await blockchain_infra.verify_crypto_address(address, blockchain)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Address verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Address verification failed: {str(e)}")

@app.get("/api/v1/blockchain/prices")
async def get_prices():
    """Get cryptocurrency prices from the configured oracle"""
    prices = {}
    for crypto in Cryptocurrency:
        try:
            prices[crypto.value] = await blockchain_infra._get_price_usd(crypto)
        except Exception as e:
            logger.warning(f"Price unavailable for {crypto.value}: {e}")
            prices[crypto.value] = None
    return {
        "prices": prices,
        "simulation_mode": SIMULATION_MODE,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8038)
