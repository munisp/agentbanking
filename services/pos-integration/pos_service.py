import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Point of Sale (POS) Integration Service
Handles payment processing, card transactions, and POS device management
"""

import asyncio
import json
import logging
import os
import uuid
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import base64

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("pos-integration-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import aioredis
from cryptography.fernet import Fernet
import qrcode
import io
import serial
import socket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/pos_integration")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PaymentMethod(str, Enum):
    CARD_CHIP = "card_chip"
    CARD_SWIPE = "card_swipe"
    CARD_CONTACTLESS = "card_contactless"
    MOBILE_NFC = "mobile_nfc"
    QR_CODE = "qr_code"
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    DIGITAL_WALLET = "digital_wallet"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    FAILED = "failed"

class DeviceType(str, Enum):
    CARD_READER = "card_reader"
    PIN_PAD = "pin_pad"
    RECEIPT_PRINTER = "receipt_printer"
    CASH_DRAWER = "cash_drawer"
    BARCODE_SCANNER = "barcode_scanner"
    DISPLAY = "display"
    INTEGRATED_POS = "integrated_pos"

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UPDATING = "updating"

@dataclass
class PaymentRequest:
    amount: float
    currency: str
    payment_method: PaymentMethod
    merchant_id: str
    terminal_id: str
    transaction_reference: str
    idempotency_key: Optional[str] = None
    customer_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class PaymentResponse:
    transaction_id: str
    status: TransactionStatus
    amount: float
    currency: str
    authorization_code: Optional[str] = None
    receipt_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0

class POSTransaction(Base):
    __tablename__ = "pos_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(String, nullable=False, unique=True, index=True)
    merchant_id = Column(String, nullable=False, index=True)
    terminal_id = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    payment_method = Column(String, nullable=False, index=True)
    status = Column(String, default=TransactionStatus.PENDING.value, index=True)
    authorization_code = Column(String)
    card_last_four = Column(String)
    card_type = Column(String)
    customer_data = Column(JSON)
    receipt_data = Column(JSON)
    metadata = Column(JSON)
    error_message = Column(Text)
    processing_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)
    settled_at = Column(DateTime)
    refunded_at = Column(DateTime)
    refund_amount = Column(Float)

class POSDevice(Base):
    __tablename__ = "pos_devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String, nullable=False, unique=True, index=True)
    device_type = Column(String, nullable=False, index=True)
    device_name = Column(String, nullable=False)
    merchant_id = Column(String, nullable=False, index=True)
    terminal_id = Column(String, nullable=False, index=True)
    status = Column(String, default=DeviceStatus.OFFLINE.value, index=True)
    ip_address = Column(String)
    serial_port = Column(String)
    configuration = Column(JSON)
    capabilities = Column(JSON)
    firmware_version = Column(String)
    last_heartbeat = Column(DateTime)
    error_count = Column(Integer, default=0)
    total_transactions = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MerchantTerminal(Base):
    __tablename__ = "merchant_terminals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    terminal_id = Column(String, nullable=False, unique=True, index=True)
    merchant_id = Column(String, nullable=False, index=True)
    terminal_name = Column(String, nullable=False)
    location = Column(String)
    configuration = Column(JSON)
    supported_payment_methods = Column(JSON)
    daily_limit = Column(Float)
    transaction_limit = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)


class CircuitBreaker:
    """Circuit breaker pattern for external service calls.
    After `failure_threshold` consecutive failures, the circuit opens
    and skips calls for `recovery_timeout` seconds before trying again."""

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed | open | half_open

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            import time as _t
            if self._last_failure_time and (_t.time() - self._last_failure_time) > self.recovery_timeout:
                self._state = "half_open"
                return False
            return True
        return False

    def record_success(self):
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self):
        import time as _t
        self._failure_count += 1
        self._last_failure_time = _t.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker '{self.name}' OPEN after {self._failure_count} failures")

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


async def _retry_with_backoff(coro_factory, max_retries: int = 2, base_delay: float = 0.5):
    """Retry an async call with exponential backoff.
    `coro_factory` is a zero-arg callable that returns a new coroutine each time."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
    raise last_exc


_scoring_analytics: Dict[str, Any] = {
    "total_scored": 0,
    "total_approved": 0,
    "total_declined": 0,
    "total_review": 0,
    "total_errors": 0,
    "score_sum": 0.0,
    "recent_decisions": [],
}


class OfflineTransactionQueue:
    """Local store-and-forward queue for offline POS transactions.
    Persists queued transactions to a local JSON file so they survive restarts."""

    def __init__(self, queue_file: str = "/tmp/pos_offline_queue.json"):
        self.queue_file = queue_file
        self._queue: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, "r") as f:
                    self._queue = json.load(f)
                logger.info(f"Loaded {len(self._queue)} offline transactions from {self.queue_file}")
        except Exception as e:
            logger.warning(f"Failed to load offline queue: {e}")
            self._queue = []

    def _persist(self):
        try:
            with open(self.queue_file, "w") as f:
                json.dump(self._queue, f)
        except Exception as e:
            logger.error(f"Failed to persist offline queue: {e}")

    def enqueue(self, payment_data: Dict[str, Any]):
        entry = {
            "queued_at": datetime.utcnow().isoformat(),
            "attempts": 0,
            "status": "queued",
            "payment": payment_data,
        }
        self._queue.append(entry)
        self._persist()
        logger.info(f"Queued offline transaction (queue size={len(self._queue)})")

    def peek_all(self) -> List[Dict[str, Any]]:
        return [e for e in self._queue if e["status"] == "queued"]

    def mark_synced(self, index: int):
        if 0 <= index < len(self._queue):
            self._queue[index]["status"] = "synced"
            self._queue[index]["synced_at"] = datetime.utcnow().isoformat()
            self._persist()

    def mark_failed(self, index: int, error: str):
        if 0 <= index < len(self._queue):
            self._queue[index]["attempts"] += 1
            self._queue[index]["last_error"] = error
            if self._queue[index]["attempts"] >= 5:
                self._queue[index]["status"] = "permanently_failed"
            self._persist()

    def purge_synced(self):
        self._queue = [e for e in self._queue if e["status"] not in ("synced",)]
        self._persist()

    @property
    def pending_count(self) -> int:
        return sum(1 for e in self._queue if e["status"] == "queued")


class POSIntegrationService:
    def __init__(self):
        self.redis_client = None
        self.connected_devices = {}
        self.active_websockets = {}
        self.encryption_key = os.getenv("POS_ENCRYPTION_KEY", Fernet.generate_key())
        self.cipher_suite = Fernet(self.encryption_key)
        self.offline_queue = OfflineTransactionQueue()
        self._is_online = True

        # Feature integration URLs
        self.scoring_url = os.getenv("TRANSACTION_SCORING_URL", "http://localhost:8000/transaction-scoring")
        self.coa_url = os.getenv("COA_URL", "http://localhost:8000/chart-of-accounts")
        self.targets_url = os.getenv("TARGETS_URL", "http://localhost:8000/projections-targets")
        self.qr_tickets_url = os.getenv("QR_TICKETS_URL", "http://localhost:8000/qr-tickets")
        self.inventory_url = os.getenv("INVENTORY_URL", "http://localhost:8000/inventory-management")

        # Scoring configuration
        self.scoring_mode = os.getenv("SCORING_MODE", "blocking")  # blocking | non_blocking | disabled
        self.scoring_skip_threshold = float(os.getenv("SCORING_SKIP_THRESHOLD", "0"))  # skip scoring below this amount
        self.scoring_cache_ttl = int(os.getenv("SCORING_CACHE_TTL", "60"))  # seconds

        # Circuit breakers for feature services
        self._circuit_breakers = {
            "scoring": CircuitBreaker("scoring", failure_threshold=3, recovery_timeout=30.0),
            "coa": CircuitBreaker("coa", failure_threshold=5, recovery_timeout=60.0),
            "targets": CircuitBreaker("targets", failure_threshold=5, recovery_timeout=60.0),
            "inventory": CircuitBreaker("inventory", failure_threshold=5, recovery_timeout=60.0),
            "qr_tickets": CircuitBreaker("qr_tickets", failure_threshold=5, recovery_timeout=60.0),
        }

        # Payment processor configurations
        self.payment_processors = {
            "stripe": {
                "api_key": os.getenv("STRIPE_SECRET_KEY", ""),
                "endpoint": "https://api.stripe.com/v1"
            },
            "square": {
                "api_key": os.getenv("SQUARE_ACCESS_TOKEN", ""),
                "endpoint": "https://connect.squareup.com/v2"
            },
            "adyen": {
                "api_key": os.getenv("ADYEN_API_KEY", ""),
                "endpoint": "https://checkout-test.adyen.com/v70"
            }
        }
        
        # Device communication protocols
        self.device_protocols = {
            "serial": self._handle_serial_device,
            "tcp": self._handle_tcp_device,
            "usb": self._handle_usb_device,
            "bluetooth": self._handle_bluetooth_device
        }
    
    async def initialize(self):
        """Initialize the POS integration service"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            asyncio.create_task(self._device_discovery_loop())
            asyncio.create_task(self._device_monitoring_loop())
            asyncio.create_task(self._offline_sync_loop())
            
            logger.info("POS Integration Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize POS Integration Service: {e}")
            self.redis_client = None
    
    async def _check_idempotency(self, idempotency_key: str, db) -> Optional[PaymentResponse]:
        """Check if a request with this idempotency key was already processed.
        Returns the cached response if found, None otherwise."""
        if self.redis_client:
            cached = await self.redis_client.get(f"idem:{idempotency_key}")
            if cached:
                data = json.loads(cached)
                logger.info(f"Idempotency hit for key={idempotency_key}")
                return PaymentResponse(
                    transaction_id=data["transaction_id"],
                    status=TransactionStatus(data["status"]),
                    amount=data["amount"],
                    currency=data["currency"],
                    authorization_code=data.get("authorization_code"),
                    receipt_data=data.get("receipt_data"),
                    error_message=data.get("error_message"),
                    processing_time=data.get("processing_time", 0.0)
                )

        existing = db.query(POSTransaction).filter(
            POSTransaction.transaction_id == idempotency_key
        ).first()
        if existing and existing.status != TransactionStatus.PENDING.value:
            logger.info(f"Idempotency hit (DB) for key={idempotency_key}")
            return PaymentResponse(
                transaction_id=existing.transaction_id,
                status=TransactionStatus(existing.status),
                amount=existing.amount,
                currency=existing.currency,
                authorization_code=existing.authorization_code,
                receipt_data=existing.receipt_data,
                error_message=existing.error_message,
                processing_time=existing.processing_time or 0.0
            )
        return None

    async def _cache_idempotency(self, idempotency_key: str, response: PaymentResponse):
        """Cache the response for an idempotency key (TTL 24h)."""
        if self.redis_client:
            data = {
                "transaction_id": response.transaction_id,
                "status": response.status.value if isinstance(response.status, TransactionStatus) else response.status,
                "amount": response.amount,
                "currency": response.currency,
                "authorization_code": response.authorization_code,
                "receipt_data": response.receipt_data,
                "error_message": response.error_message,
                "processing_time": response.processing_time
            }
            await self.redis_client.setex(
                f"idem:{idempotency_key}", 86400, json.dumps(data)
            )

    async def _get_cached_score(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check Redis for a cached scoring result."""
        if self.redis_client and self.scoring_cache_ttl > 0:
            try:
                cached = await self.redis_client.get(f"score:{cache_key}")
                if cached:
                    return json.loads(cached)
            except Exception:
                pass
        return None

    async def _cache_score(self, cache_key: str, score_result: Dict[str, Any]):
        """Cache a scoring result in Redis."""
        if self.redis_client and self.scoring_cache_ttl > 0:
            try:
                await self.redis_client.setex(
                    f"score:{cache_key}", self.scoring_cache_ttl, json.dumps(score_result)
                )
            except Exception:
                pass

    def _record_scoring_analytics(self, score_result: Optional[Dict[str, Any]], error: bool = False):
        """Track scoring decisions for analytics."""
        global _scoring_analytics
        if error:
            _scoring_analytics["total_errors"] += 1
            return
        if not score_result:
            return
        _scoring_analytics["total_scored"] += 1
        recommendation = score_result.get("recommendation", "")
        if recommendation == "approve":
            _scoring_analytics["total_approved"] += 1
        elif recommendation == "decline":
            _scoring_analytics["total_declined"] += 1
        elif recommendation == "review":
            _scoring_analytics["total_review"] += 1
        overall = score_result.get("overall_score", 0)
        _scoring_analytics["score_sum"] += overall
        _scoring_analytics["recent_decisions"].append({
            "score": overall,
            "risk_level": score_result.get("risk_level"),
            "recommendation": recommendation,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(_scoring_analytics["recent_decisions"]) > 100:
            _scoring_analytics["recent_decisions"] = _scoring_analytics["recent_decisions"][-100:]

    async def _post_payment_tasks(self, transaction_id: str, payment_request: PaymentRequest, response: PaymentResponse):
        """Run all non-blocking post-payment integrations concurrently as a background task.
        Uses asyncio.gather() to parallelize COA, targets, inventory, and ledger calls."""
        tb_sync_url = os.getenv("TIGERBEETLE_SYNC_URL", "http://localhost:8085")

        async def _ledger_task():
            cb = self._circuit_breakers.get("coa")
            if cb and cb.is_open:
                return
            try:
                async with httpx.AsyncClient(timeout=5.0) as tb_client:
                    await tb_client.post(
                        f"{tb_sync_url}/api/v1/sync/transfers",
                        json={
                            "debit_account_id": payment_request.merchant_id,
                            "credit_account_id": "settlement_pool",
                            "amount": payment_request.amount,
                            "currency": payment_request.currency,
                            "ledger_id": 1,
                            "metadata": {
                                "source": "pos",
                                "transaction_id": transaction_id,
                                "terminal_id": payment_request.terminal_id,
                                "payment_method": payment_request.payment_method.value,
                            },
                        },
                    )
                logger.info(f"Ledger transfer recorded for txn {transaction_id}")
            except Exception as ledger_err:
                logger.warning(f"Ledger record failed (non-blocking): {ledger_err}")

        async def _coa_task():
            cb = self._circuit_breakers["coa"]
            if cb.is_open:
                return
            try:
                tx_type = "cash_in" if payment_request.payment_method == PaymentMethod.CASH else "transfer"
                async with httpx.AsyncClient(timeout=5.0) as coa_client:
                    await coa_client.post(
                        f"{self.coa_url}/auto-post",
                        params={
                            "transaction_ref": transaction_id,
                            "transaction_type": tx_type,
                            "amount": payment_request.amount,
                            "currency": payment_request.currency,
                            "agent_id": payment_request.merchant_id,
                        },
                    )
                cb.record_success()
                logger.info(f"COA GL entry posted for txn {transaction_id}")
            except Exception as coa_err:
                cb.record_failure()
                logger.debug(f"COA posting unavailable (non-blocking): {coa_err}")

        async def _targets_task():
            cb = self._circuit_breakers["targets"]
            if cb.is_open:
                return
            try:
                async with httpx.AsyncClient(timeout=5.0) as tgt_client:
                    targets_resp = await tgt_client.get(
                        f"{self.targets_url}/targets",
                        params={"agent_id": payment_request.merchant_id, "status": "active"},
                    )
                    if targets_resp.status_code == 200:
                        active_targets = targets_resp.json()
                        for target in active_targets:
                            metric = target.get("metric", "")
                            if metric in ("transaction_count", "transaction_volume", "revenue"):
                                record_value = 1 if metric == "transaction_count" else payment_request.amount
                                await tgt_client.post(
                                    f"{self.targets_url}/targets/{target['id']}/record-actual",
                                    params={"value": record_value},
                                )
                cb.record_success()
                logger.info(f"Target actuals recorded for agent {payment_request.merchant_id}")
            except Exception as tgt_err:
                cb.record_failure()
                logger.debug(f"Targets recording unavailable (non-blocking): {tgt_err}")

        async def _inventory_task():
            cb = self._circuit_breakers["inventory"]
            if cb.is_open:
                return
            try:
                async with httpx.AsyncClient(timeout=3.0) as inv_client:
                    inv_resp = await inv_client.get(
                        f"{self.inventory_url}/agent/{payment_request.merchant_id}",
                    )
                    if inv_resp.status_code == 200:
                        inv_data = inv_resp.json()
                        for item in inv_data.get("inventory", []):
                            if item.get("category") in ("pos_paper", "receipt_roll") and item.get("quantity", 0) > 0:
                                await inv_client.post(
                                    f"{self.inventory_url}/agent/{payment_request.merchant_id}/transfer",
                                    json={
                                        "item_id": item["item_id"],
                                        "quantity": 1,
                                        "transfer_type": "usage",
                                        "reason": f"Auto-deduct for receipt print (txn {transaction_id})",
                                        "from_agent_id": payment_request.merchant_id,
                                        "to_agent_id": "consumed",
                                    },
                                )
                                logger.debug(f"Auto-deducted receipt paper for agent {payment_request.merchant_id}")
                                break
                cb.record_success()
            except Exception as inv_err:
                cb.record_failure()
                logger.debug(f"Inventory auto-deduct failed (non-blocking): {inv_err}")

        try:
            await asyncio.gather(
                _ledger_task(), _coa_task(), _targets_task(), _inventory_task(),
                return_exceptions=True,
            )
        except Exception:
            pass

    async def process_payment(self, payment_request: PaymentRequest) -> PaymentResponse:
        """Process a payment transaction with idempotency, circuit breakers,
        configurable scoring (blocking/non-blocking/disabled), retry with backoff,
        scoring cache, and parallelized post-payment background tasks."""
        db = SessionLocal()
        try:
            start_time = datetime.utcnow()

            idem_key = payment_request.idempotency_key or payment_request.transaction_reference
            if idem_key:
                cached_response = await self._check_idempotency(idem_key, db)
                if cached_response is not None:
                    return cached_response

            transaction_id = idem_key if idem_key else str(uuid.uuid4())

            # --- Transaction Scoring with circuit breaker, cache, retry, and configurable mode ---
            score_result = None
            scoring_cb = self._circuit_breakers["scoring"]
            if self.scoring_mode != "disabled" and payment_request.amount >= self.scoring_skip_threshold and not scoring_cb.is_open:
                score_payload = {
                    "sender_id": payment_request.merchant_id,
                    "recipient_id": payment_request.customer_data.get("customer_id", "unknown") if payment_request.customer_data else "unknown",
                    "amount": payment_request.amount,
                    "currency": payment_request.currency,
                    "transaction_type": "cash_in" if payment_request.payment_method == PaymentMethod.CASH else "merchant",
                    "channel": "pos",
                }
                cache_key = hashlib.sha256(json.dumps(score_payload, sort_keys=True).encode()).hexdigest()
                score_result = await self._get_cached_score(cache_key)

                if not score_result:
                    try:
                        async def _do_score():
                            async with httpx.AsyncClient(timeout=5.0) as sc:
                                resp = await sc.post(f"{self.scoring_url}/score", json=score_payload)
                                resp.raise_for_status()
                                return resp.json()

                        score_result = await _retry_with_backoff(_do_score, max_retries=1, base_delay=0.3)
                        scoring_cb.record_success()
                        await self._cache_score(cache_key, score_result)
                    except Exception as score_err:
                        scoring_cb.record_failure()
                        self._record_scoring_analytics(None, error=True)
                        logger.debug(f"Transaction scoring unavailable: {score_err}")

                if score_result:
                    self._record_scoring_analytics(score_result)
                    if self.scoring_mode == "blocking" and score_result.get("recommendation") == "decline":
                        logger.warning(f"Transaction scoring declined txn {transaction_id}: score={score_result.get('overall_score')}")
                        return PaymentResponse(
                            transaction_id=transaction_id,
                            status=TransactionStatus.DECLINED,
                            amount=payment_request.amount,
                            currency=payment_request.currency,
                            error_message=f"Transaction declined by risk engine (score: {score_result.get('overall_score')}, level: {score_result.get('risk_level')})"
                        )
                    logger.info(f"Transaction score for {transaction_id}: {score_result.get('overall_score')} ({score_result.get('risk_level')})")

            # Validate merchant and terminal
            terminal = db.query(MerchantTerminal).filter(
                MerchantTerminal.terminal_id == payment_request.terminal_id,
                MerchantTerminal.merchant_id == payment_request.merchant_id,
                MerchantTerminal.is_active == True
            ).first()
            
            if not terminal:
                raise HTTPException(status_code=404, detail="Terminal not found or inactive")
            
            # Validate payment limits
            if payment_request.amount > terminal.transaction_limit:
                raise HTTPException(status_code=400, detail="Amount exceeds transaction limit")
            
            # Check daily limit
            daily_total = await self._get_daily_transaction_total(
                payment_request.merchant_id, payment_request.terminal_id
            )
            if daily_total + payment_request.amount > terminal.daily_limit:
                raise HTTPException(status_code=400, detail="Amount exceeds daily limit")
            
            # Create transaction record
            transaction = POSTransaction(
                transaction_id=transaction_id,
                merchant_id=payment_request.merchant_id,
                terminal_id=payment_request.terminal_id,
                amount=payment_request.amount,
                currency=payment_request.currency,
                payment_method=payment_request.payment_method.value,
                customer_data=payment_request.customer_data,
                metadata=payment_request.metadata
            )
            
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            
            # Process payment based on method
            if payment_request.payment_method in [PaymentMethod.CARD_CHIP, PaymentMethod.CARD_SWIPE, PaymentMethod.CARD_CONTACTLESS]:
                response = await self._process_card_payment(payment_request, transaction)
            elif payment_request.payment_method == PaymentMethod.MOBILE_NFC:
                response = await self._process_nfc_payment(payment_request, transaction)
            elif payment_request.payment_method == PaymentMethod.QR_CODE:
                response = await self._process_qr_payment(payment_request, transaction)
            elif payment_request.payment_method == PaymentMethod.CASH:
                response = await self._process_cash_payment(payment_request, transaction)
            elif payment_request.payment_method == PaymentMethod.DIGITAL_WALLET:
                response = await self._process_wallet_payment(payment_request, transaction)
            else:
                raise HTTPException(status_code=400, detail="Unsupported payment method")
            
            # Update transaction with response
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            transaction.status = response.status.value
            transaction.authorization_code = response.authorization_code
            transaction.receipt_data = response.receipt_data
            transaction.error_message = response.error_message
            transaction.processing_time = processing_time
            transaction.processed_at = datetime.utcnow()
            
            db.commit()
            
            # Cache idempotency response
            if idem_key:
                await self._cache_idempotency(idem_key, response)

            # Attach score to response metadata if available
            if score_result and response.receipt_data:
                response.receipt_data["transaction_score"] = {
                    "overall_score": score_result.get("overall_score"),
                    "risk_level": score_result.get("risk_level"),
                    "recommendation": score_result.get("recommendation"),
                }

            # Fire all post-payment integrations as a background task (non-blocking, parallelized)
            if response.status == TransactionStatus.APPROVED:
                asyncio.create_task(self._post_payment_tasks(transaction_id, payment_request, response))

            # Send real-time update
            await self._send_transaction_update(transaction_id, response)
            
            return response
            
        except Exception as e:
            db.rollback()
            logger.error(f"Payment processing failed: {e}")
            
            # Update transaction with error
            if 'transaction' in locals():
                transaction.status = TransactionStatus.FAILED.value
                transaction.error_message = str(e)
                db.commit()
            
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def _process_card_payment(self, payment_request: PaymentRequest, 
                                   transaction: POSTransaction) -> PaymentResponse:
        """Process card payment through payment processor with multi-gateway failover"""
        gateways = [
            ("stripe", self.payment_processors["stripe"]),
            ("square", self.payment_processors["square"]),
            ("adyen", self.payment_processors["adyen"]),
        ]
        
        last_error = None
        for gateway_name, config in gateways:
            if not config["api_key"]:
                continue
            try:
                return await self._call_card_gateway(gateway_name, config, payment_request, transaction)
            except Exception as e:
                last_error = e
                logger.warning(f"Gateway {gateway_name} failed, trying next: {e}")
        
        if last_error:
            logger.error(f"All card payment gateways failed. Last error: {last_error}")
            return PaymentResponse(
                transaction_id=transaction.transaction_id,
                status=TransactionStatus.FAILED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message=f"All payment gateways unavailable: {last_error}"
            )
        
        return PaymentResponse(
            transaction_id=transaction.transaction_id,
            status=TransactionStatus.FAILED,
            amount=payment_request.amount,
            currency=payment_request.currency,
            error_message="No payment gateway configured. Set STRIPE_SECRET_KEY, SQUARE_ACCESS_TOKEN, or ADYEN_API_KEY."
        )
    
    async def _call_card_gateway(self, gateway_name: str, config: Dict[str, Any],
                                payment_request: PaymentRequest,
                                transaction: POSTransaction) -> PaymentResponse:
        """Call a specific card payment gateway"""
        async with httpx.AsyncClient() as client:
            if gateway_name == "stripe":
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data = {
                    "amount": int(payment_request.amount * 100),
                    "currency": payment_request.currency.lower(),
                    "payment_method_types[]": "card",
                    "metadata[transaction_id]": transaction.transaction_id,
                    "metadata[terminal_id]": payment_request.terminal_id
                }
                response = await client.post(
                    f"{config['endpoint']}/payment_intents",
                    headers=headers, data=data, timeout=30.0
                )
            elif gateway_name == "square":
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                payload = {
                    "idempotency_key": transaction.transaction_id,
                    "amount_money": {
                        "amount": int(payment_request.amount * 100),
                        "currency": payment_request.currency.upper()
                    },
                    "source_id": payment_request.metadata.get("source_id", "cnon:card-nonce-ok") if payment_request.metadata else "cnon:card-nonce-ok",
                    "reference_id": transaction.transaction_id
                }
                response = await client.post(
                    f"{config['endpoint']}/payments",
                    headers=headers, json=payload, timeout=30.0
                )
            elif gateway_name == "adyen":
                headers = {
                    "X-API-Key": config["api_key"],
                    "Content-Type": "application/json"
                }
                payload = {
                    "amount": {
                        "value": int(payment_request.amount * 100),
                        "currency": payment_request.currency.upper()
                    },
                    "reference": transaction.transaction_id,
                    "merchantAccount": os.getenv("ADYEN_MERCHANT_ACCOUNT", "default"),
                    "paymentMethod": {"type": "scheme"}
                }
                response = await client.post(
                    f"{config['endpoint']}/payments",
                    headers=headers, json=payload, timeout=30.0
                )
            else:
                raise ValueError(f"Unknown gateway: {gateway_name}")
            
            if response.status_code in (200, 201):
                result = response.json()
                return PaymentResponse(
                    transaction_id=transaction.transaction_id,
                    status=TransactionStatus.APPROVED,
                    amount=payment_request.amount,
                    currency=payment_request.currency,
                    authorization_code=result.get("id", result.get("payment", {}).get("id", "")),
                    receipt_data=self._generate_receipt_data(payment_request, {
                        "provider": gateway_name, **result
                    })
                )
            else:
                error_data = response.json()
                raise ValueError(f"{gateway_name} returned {response.status_code}: {error_data}")
    
    async def _process_nfc_payment(self, payment_request: PaymentRequest,
                                 transaction: POSTransaction) -> PaymentResponse:
        """Process NFC mobile payment via payment gateway"""
        try:
            payment_app = payment_request.metadata.get("payment_app", "apple_pay") if payment_request.metadata else "apple_pay"
            nfc_token = payment_request.metadata.get("nfc_token", "") if payment_request.metadata else ""
            
            config = self.payment_processors["stripe"]
            if not config["api_key"]:
                config = self.payment_processors["adyen"]
            if not config["api_key"]:
                return PaymentResponse(
                    transaction_id=transaction.transaction_id,
                    status=TransactionStatus.FAILED,
                    amount=payment_request.amount,
                    currency=payment_request.currency,
                    error_message="No payment gateway configured for NFC payments"
                )
            
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data = {
                    "amount": int(payment_request.amount * 100),
                    "currency": payment_request.currency.lower(),
                    "payment_method_types[]": "card",
                    "metadata[transaction_id]": transaction.transaction_id,
                    "metadata[terminal_id]": payment_request.terminal_id,
                    "metadata[nfc_app]": payment_app,
                    "metadata[nfc_token]": nfc_token
                }
                response = await client.post(
                    f"{config['endpoint']}/payment_intents",
                    headers=headers, data=data, timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return PaymentResponse(
                        transaction_id=transaction.transaction_id,
                        status=TransactionStatus.APPROVED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        authorization_code=result.get("id", ""),
                        receipt_data=self._generate_receipt_data(payment_request, {
                            "provider": "stripe", "nfc_app": payment_app, **result
                        })
                    )
                else:
                    error_data = response.json()
                    return PaymentResponse(
                        transaction_id=transaction.transaction_id,
                        status=TransactionStatus.DECLINED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        error_message=error_data.get("error", {}).get("message", "NFC payment failed")
                    )
                    
        except Exception as e:
            logger.error(f"NFC payment processing failed: {e}")
            return PaymentResponse(
                transaction_id=transaction.transaction_id,
                status=TransactionStatus.FAILED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message=str(e)
            )
    
    async def _process_qr_payment(self, payment_request: PaymentRequest,
                                transaction: POSTransaction) -> PaymentResponse:
        """Process QR code payment with QR ticket verification integration"""
        try:
            qr_data = {
                "transaction_id": transaction.transaction_id,
                "amount": payment_request.amount,
                "currency": payment_request.currency,
                "merchant_id": payment_request.merchant_id,
                "terminal_id": payment_request.terminal_id,
                "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }

            qr_code_data = await self._generate_qr_code(qr_data)

            config = self.payment_processors["stripe"]
            if not config["api_key"]:
                config = self.payment_processors["square"]
            if not config["api_key"]:
                return PaymentResponse(
                    transaction_id=transaction.transaction_id,
                    status=TransactionStatus.FAILED,
                    amount=payment_request.amount,
                    currency=payment_request.currency,
                    error_message="No payment gateway configured for QR payments"
                )

            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data = {
                    "amount": int(payment_request.amount * 100),
                    "currency": payment_request.currency.lower(),
                    "payment_method_types[]": "card",
                    "metadata[transaction_id]": transaction.transaction_id,
                    "metadata[terminal_id]": payment_request.terminal_id,
                    "metadata[payment_type]": "qr_code"
                }
                response = await client.post(
                    f"{config['endpoint']}/payment_intents",
                    headers=headers, data=data, timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()

                    ticket_qr = None
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as tkt_client:
                            tkt_resp = await tkt_client.post(
                                f"{self.qr_tickets_url}/create",
                                json={
                                    "transaction_id": transaction.transaction_id,
                                    "amount": payment_request.amount,
                                    "currency": payment_request.currency,
                                    "merchant_id": payment_request.merchant_id,
                                    "terminal_id": payment_request.terminal_id,
                                    "ticket_type": "payment_receipt",
                                },
                            )
                            if tkt_resp.status_code == 200:
                                ticket_data = tkt_resp.json()
                                ticket_qr = ticket_data.get("qr_code_data")
                                logger.info(f"QR verification ticket created for txn {transaction.transaction_id}")
                    except Exception as tkt_err:
                        logger.debug(f"QR ticket service unavailable (non-blocking): {tkt_err}")

                    receipt = {
                        "qr_code": qr_code_data,
                        "payment_method": "QR Code",
                        **self._generate_receipt_data(payment_request, result),
                    }
                    if ticket_qr:
                        receipt["verification_qr"] = ticket_qr

                    return PaymentResponse(
                        transaction_id=transaction.transaction_id,
                        status=TransactionStatus.APPROVED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        authorization_code=result.get("id", ""),
                        receipt_data=receipt,
                    )
                else:
                    error_data = response.json()
                    return PaymentResponse(
                        transaction_id=transaction.transaction_id,
                        status=TransactionStatus.DECLINED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        error_message=error_data.get("error", {}).get("message", "QR payment failed")
                    )

        except Exception as e:
            logger.error(f"QR payment processing failed: {e}")
            return PaymentResponse(
                transaction_id=transaction.transaction_id,
                status=TransactionStatus.FAILED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message=str(e)
            )
    
    async def _process_cash_payment(self, payment_request: PaymentRequest,
                                  transaction: POSTransaction) -> PaymentResponse:
        """Process cash payment"""
        try:
            # Cash payments are immediately approved
            return PaymentResponse(
                transaction_id=transaction.transaction_id,
                status=TransactionStatus.APPROVED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                authorization_code=f"CASH{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                receipt_data=self._generate_receipt_data(payment_request, {"payment_method": "Cash"})
            )
            
        except Exception as e:
            logger.error(f"Cash payment processing failed: {e}")
            return PaymentResponse(
                transaction_id=transaction.transaction_id,
                status=TransactionStatus.FAILED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message=str(e)
            )
    
    async def _process_wallet_payment(self, payment_request: PaymentRequest,
                                    transaction: POSTransaction) -> PaymentResponse:
        """Process digital wallet payment via payment gateway"""
        try:
            wallet_type = payment_request.metadata.get("wallet_type", "unknown") if payment_request.metadata else "unknown"
            wallet_token = payment_request.metadata.get("wallet_token", "") if payment_request.metadata else ""
            
            config = self.payment_processors["stripe"]
            if not config["api_key"]:
                config = self.payment_processors["adyen"]
            if not config["api_key"]:
                return PaymentResponse(
                    transaction_id=transaction.transaction_id,
                    status=TransactionStatus.FAILED,
                    amount=payment_request.amount,
                    currency=payment_request.currency,
                    error_message="No payment gateway configured for wallet payments"
                )
            
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data = {
                    "amount": int(payment_request.amount * 100),
                    "currency": payment_request.currency.lower(),
                    "payment_method_types[]": "card",
                    "metadata[transaction_id]": transaction.transaction_id,
                    "metadata[terminal_id]": payment_request.terminal_id,
                    "metadata[wallet_type]": wallet_type,
                    "metadata[wallet_token]": wallet_token
                }
                response = await client.post(
                    f"{config['endpoint']}/payment_intents",
                    headers=headers, data=data, timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return PaymentResponse(
                        transaction_id=transaction.transaction_id,
                        status=TransactionStatus.APPROVED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        authorization_code=result.get("id", ""),
                        receipt_data=self._generate_receipt_data(payment_request, {
                            "wallet_type": wallet_type,
                            "payment_method": "Digital Wallet",
                            **result
                        })
                    )
                else:
                    error_data = response.json()
                    return PaymentResponse(
                        transaction_id=transaction.transaction_id,
                        status=TransactionStatus.DECLINED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        error_message=error_data.get("error", {}).get("message", "Wallet payment failed")
                    )
                    
        except Exception as e:
            logger.error(f"Wallet payment processing failed: {e}")
            return PaymentResponse(
                transaction_id=transaction.transaction_id,
                status=TransactionStatus.FAILED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message=str(e)
            )
    
    def _generate_receipt_data(self, payment_request: PaymentRequest, 
                              processor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate receipt data for transaction"""
        return {
            "merchant_id": payment_request.merchant_id,
            "terminal_id": payment_request.terminal_id,
            "transaction_reference": payment_request.transaction_reference,
            "amount": payment_request.amount,
            "currency": payment_request.currency,
            "payment_method": payment_request.payment_method.value,
            "timestamp": datetime.utcnow().isoformat(),
            "processor_data": processor_data,
            "receipt_number": f"RCP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
        }
    
    def _generate_receipt(self, payment_request: PaymentRequest, auth_code: str) -> Dict[str, Any]:
        """Generate receipt data"""
        return {
            "merchant_id": payment_request.merchant_id,
            "terminal_id": payment_request.terminal_id,
            "transaction_reference": payment_request.transaction_reference,
            "amount": payment_request.amount,
            "currency": payment_request.currency,
            "payment_method": payment_request.payment_method.value,
            "authorization_code": auth_code,
            "timestamp": datetime.utcnow().isoformat(),
            "receipt_number": f"RCP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        }
    
    async def _generate_qr_code(self, data: Dict[str, Any]) -> str:
        """Generate QR code for payment"""
        try:
            qr_string = json.dumps(data)
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"QR code generation failed: {e}")
            return ""
    
    async def _get_daily_transaction_total(self, merchant_id: str, terminal_id: str) -> float:
        """Get daily transaction total for limits checking"""
        db = SessionLocal()
        try:
            today = datetime.utcnow().date()
            
            result = db.query(POSTransaction).filter(
                POSTransaction.merchant_id == merchant_id,
                POSTransaction.terminal_id == terminal_id,
                POSTransaction.status == TransactionStatus.APPROVED.value,
                POSTransaction.created_at >= today
            ).all()
            
            return sum(t.amount for t in result)
            
        except Exception as e:
            logger.error(f"Failed to get daily total: {e}")
            return 0.0
        finally:
            db.close()
    
    async def register_device(self, device_data: Dict[str, Any]) -> str:
        """Register a new POS device"""
        db = SessionLocal()
        try:
            device_id = device_data.get("device_id") or str(uuid.uuid4())
            
            # Check if device already exists
            existing_device = db.query(POSDevice).filter(
                POSDevice.device_id == device_id
            ).first()
            
            if existing_device:
                # Update existing device
                for key, value in device_data.items():
                    if hasattr(existing_device, key):
                        setattr(existing_device, key, value)
                existing_device.updated_at = datetime.utcnow()
                existing_device.status = DeviceStatus.ONLINE.value
                db.commit()
                return device_id
            
            # Create new device
            device = POSDevice(
                device_id=device_id,
                device_type=device_data.get("device_type", DeviceType.INTEGRATED_POS.value),
                device_name=device_data.get("device_name", f"Device {device_id[:8]}"),
                merchant_id=device_data.get("merchant_id", ""),
                terminal_id=device_data.get("terminal_id", ""),
                ip_address=device_data.get("ip_address"),
                serial_port=device_data.get("serial_port"),
                configuration=device_data.get("configuration", {}),
                capabilities=device_data.get("capabilities", []),
                firmware_version=device_data.get("firmware_version", "1.0.0"),
                status=DeviceStatus.ONLINE.value,
                last_heartbeat=datetime.utcnow()
            )
            
            db.add(device)
            db.commit()
            db.refresh(device)
            
            # Store device connection info
            self.connected_devices[device_id] = {
                "device": device,
                "last_seen": datetime.utcnow(),
                "connection_type": device_data.get("connection_type", "tcp")
            }
            
            return device_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Device registration failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def _device_discovery_loop(self):
        """Discover POS devices on the network"""
        while True:
            try:
                # Scan for devices on common POS ports
                await self._scan_network_devices()
                await self._scan_serial_devices()
                
                await asyncio.sleep(30)  # Scan every 30 seconds
                
            except Exception as e:
                logger.error(f"Device discovery error: {e}")
                await asyncio.sleep(60)
    
    async def _scan_network_devices(self):
        """Scan network for POS devices"""
        try:
            # Common POS device ports
            pos_ports = [9100, 8080, 80, 443, 23, 9001, 9002]
            
            # Scan local network (simplified)
            base_ip = "192.168.1."
            
            for i in range(1, 255):
                ip = f"{base_ip}{i}"
                
                for port in pos_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex((ip, port))
                        
                        if result == 0:
                            # Device found, try to identify
                            await self._identify_network_device(ip, port)
                        
                        sock.close()
                        
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.error(f"Network device scan failed: {e}")
    
    async def _scan_serial_devices(self):
        """Scan for serial POS devices"""
        try:
            import serial.tools.list_ports
            
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                try:
                    # Try to connect to serial device
                    ser = serial.Serial(port.device, 9600, timeout=1)
                    
                    # Send identification command
                    ser.write(b'\x1B\x1D\x49\x01')  # ESC GS I command
                    response = ser.read(100)
                    
                    if response:
                        await self._identify_serial_device(port.device, response)
                    
                    ser.close()
                    
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"Serial device scan failed: {e}")
    
    async def _identify_network_device(self, ip: str, port: int):
        """Identify network POS device"""
        try:
            # Try to get device information via HTTP
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{ip}:{port}/device/info", timeout=5.0)
                
                if response.status_code == 200:
                    device_info = response.json()
                    device_info["ip_address"] = ip
                    device_info["connection_type"] = "tcp"
                    
                    await self.register_device(device_info)
                    
        except Exception as e:
            logger.debug(f"Failed to identify device at {ip}:{port}: {e}")
    
    async def _identify_serial_device(self, port: str, response: bytes):
        """Identify serial POS device"""
        try:
            device_info = {
                "device_id": f"serial_{port.replace('/', '_')}",
                "device_type": DeviceType.INTEGRATED_POS.value,
                "device_name": f"Serial Device {port}",
                "serial_port": port,
                "connection_type": "serial",
                "capabilities": ["print", "payment"],
                "firmware_version": "unknown"
            }
            
            await self.register_device(device_info)
            
        except Exception as e:
            logger.error(f"Failed to identify serial device: {e}")
    
    async def _device_monitoring_loop(self):
        """Monitor connected devices"""
        while True:
            try:
                current_time = datetime.utcnow()
                
                # Check device heartbeats
                for device_id, device_info in list(self.connected_devices.items()):
                    last_seen = device_info["last_seen"]
                    
                    if (current_time - last_seen).total_seconds() > 300:  # 5 minutes timeout
                        # Mark device as offline
                        await self._mark_device_offline(device_id)
                        del self.connected_devices[device_id]
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Device monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _mark_device_offline(self, device_id: str):
        """Mark device as offline"""
        db = SessionLocal()
        try:
            device = db.query(POSDevice).filter(POSDevice.device_id == device_id).first()
            if device:
                device.status = DeviceStatus.OFFLINE.value
                device.updated_at = datetime.utcnow()
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to mark device offline: {e}")
        finally:
            db.close()
    
    async def _handle_serial_device(self, device_id: str, command: str, data: Any):
        """Handle serial device communication"""
        try:
            device_info = self.connected_devices.get(device_id)
            if not device_info:
                return {"error": "Device not found"}
            
            serial_port = device_info["device"].serial_port
            
            ser = serial.Serial(serial_port, 9600, timeout=5)
            
            if command == "print_receipt":
                # Send receipt data to printer
                receipt_data = data.get("receipt_data", "")
                ser.write(receipt_data.encode())
                
            elif command == "open_cash_drawer":
                # Send cash drawer open command
                ser.write(b'\x1B\x70\x00\x19\xFA')  # ESC p command
                
            elif command == "read_card":
                # Request card read
                ser.write(b'\x02READ_CARD\x03')
                response = ser.read(100)
                return {"card_data": response.decode()}
            
            ser.close()
            return {"status": "success"}
            
        except Exception as e:
            logger.error(f"Serial device communication failed: {e}")
            return {"error": str(e)}
    
    async def _handle_tcp_device(self, device_id: str, command: str, data: Any):
        """Handle TCP device communication"""
        try:
            device_info = self.connected_devices.get(device_id)
            if not device_info:
                return {"error": "Device not found"}
            
            ip_address = device_info["device"].ip_address
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://{ip_address}/command",
                    json={"command": command, "data": data},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Device returned {response.status_code}"}
                    
        except Exception as e:
            logger.error(f"TCP device communication failed: {e}")
            return {"error": str(e)}
    
    async def _handle_usb_device(self, device_id: str, command: str, data: Any):
        """Handle USB device communication via device_drivers"""
        try:
            from device_drivers import DeviceDriverManager, DeviceCommand
            manager = DeviceDriverManager()
            
            driver = manager.drivers.get(device_id)
            if not driver:
                return {"error": f"USB device {device_id} not registered in driver manager"}
            
            cmd_map = {
                "print_receipt": DeviceCommand.PRINT_RECEIPT,
                "open_cash_drawer": DeviceCommand.OPEN_CASH_DRAWER,
                "read_card": DeviceCommand.READ_CARD,
                "display_message": DeviceCommand.DISPLAY_MESSAGE,
                "get_status": DeviceCommand.GET_STATUS,
            }
            device_cmd = cmd_map.get(command)
            if not device_cmd:
                return {"error": f"Unknown USB command: {command}"}
            
            response = await driver.send_command(device_cmd, data)
            return {"success": response.success, "data": response.data, "error": response.error}
            
        except ImportError:
            return {"error": "USB driver module not available"}
        except Exception as e:
            logger.error(f"USB device communication failed: {e}")
            return {"error": str(e)}
    
    async def _handle_bluetooth_device(self, device_id: str, command: str, data: Any):
        """Handle Bluetooth device communication via device_drivers"""
        try:
            from device_drivers import DeviceDriverManager, DeviceCommand
            manager = DeviceDriverManager()
            
            driver = manager.drivers.get(device_id)
            if not driver:
                return {"error": f"Bluetooth device {device_id} not registered in driver manager"}
            
            cmd_map = {
                "print_receipt": DeviceCommand.PRINT_RECEIPT,
                "open_cash_drawer": DeviceCommand.OPEN_CASH_DRAWER,
                "read_card": DeviceCommand.READ_CARD,
                "display_message": DeviceCommand.DISPLAY_MESSAGE,
                "get_status": DeviceCommand.GET_STATUS,
            }
            device_cmd = cmd_map.get(command)
            if not device_cmd:
                return {"error": f"Unknown Bluetooth command: {command}"}
            
            response = await driver.send_command(device_cmd, data)
            return {"success": response.success, "data": response.data, "error": response.error}
            
        except ImportError:
            return {"error": "Bluetooth driver module not available"}
        except Exception as e:
            logger.error(f"Bluetooth device communication failed: {e}")
            return {"error": str(e)}
    
    async def send_device_command(self, device_id: str, command: str, data: Any = None) -> Dict[str, Any]:
        """Send command to POS device"""
        try:
            device_info = self.connected_devices.get(device_id)
            if not device_info:
                raise HTTPException(status_code=404, detail="Device not found")
            
            connection_type = device_info.get("connection_type", "tcp")
            handler = self.device_protocols.get(connection_type)
            
            if not handler:
                raise HTTPException(status_code=400, detail="Unsupported connection type")
            
            result = await handler(device_id, command, data)
            
            # Update device last seen
            device_info["last_seen"] = datetime.utcnow()
            
            return result
            
        except Exception as e:
            logger.error(f"Device command failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _send_transaction_update(self, transaction_id: str, response: PaymentResponse):
        """Send real-time transaction update via WebSocket"""
        try:
            if self.redis_client:
                update_data = {
                    "transaction_id": transaction_id,
                    "status": response.status.value,
                    "amount": response.amount,
                    "authorization_code": response.authorization_code,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await self.redis_client.publish(
                    f"transaction_updates:{transaction_id}",
                    json.dumps(update_data)
                )
                
        except Exception as e:
            logger.error(f"Failed to send transaction update: {e}")
    
    async def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction status"""
        db = SessionLocal()
        try:
            transaction = db.query(POSTransaction).filter(
                POSTransaction.transaction_id == transaction_id
            ).first()
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            return {
                "transaction_id": transaction.transaction_id,
                "status": transaction.status,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "payment_method": transaction.payment_method,
                "authorization_code": transaction.authorization_code,
                "receipt_data": transaction.receipt_data,
                "error_message": transaction.error_message,
                "processing_time": transaction.processing_time,
                "created_at": transaction.created_at.isoformat(),
                "processed_at": transaction.processed_at.isoformat() if transaction.processed_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get transaction status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def refund_transaction(self, transaction_id: str, refund_amount: Optional[float] = None,
                               reason: str = "") -> Dict[str, Any]:
        """Refund a transaction"""
        db = SessionLocal()
        try:
            transaction = db.query(POSTransaction).filter(
                POSTransaction.transaction_id == transaction_id,
                POSTransaction.status == TransactionStatus.APPROVED.value
            ).first()
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found or not approved")
            
            # Determine refund amount
            if refund_amount is None:
                refund_amount = transaction.amount
            elif refund_amount > transaction.amount:
                raise HTTPException(status_code=400, detail="Refund amount exceeds transaction amount")
            
            # Process refund
            refund_id = str(uuid.uuid4())
            
            # Update transaction
            if refund_amount == transaction.amount:
                transaction.status = TransactionStatus.REFUNDED.value
            else:
                transaction.status = TransactionStatus.PARTIALLY_REFUNDED.value
            
            transaction.refunded_at = datetime.utcnow()
            transaction.refund_amount = (transaction.refund_amount or 0) + refund_amount
            
            db.commit()
            
            return {
                "refund_id": refund_id,
                "transaction_id": transaction_id,
                "refund_amount": refund_amount,
                "status": "processed",
                "reason": reason,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Refund processing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def get_device_list(self, merchant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of registered devices"""
        db = SessionLocal()
        try:
            query = db.query(POSDevice)
            
            if merchant_id:
                query = query.filter(POSDevice.merchant_id == merchant_id)
            
            devices = query.all()
            
            return [
                {
                    "device_id": device.device_id,
                    "device_type": device.device_type,
                    "device_name": device.device_name,
                    "merchant_id": device.merchant_id,
                    "terminal_id": device.terminal_id,
                    "status": device.status,
                    "ip_address": device.ip_address,
                    "capabilities": device.capabilities,
                    "firmware_version": device.firmware_version,
                    "last_heartbeat": device.last_heartbeat.isoformat() if device.last_heartbeat else None,
                    "total_transactions": device.total_transactions
                }
                for device in devices
            ]
            
        except Exception as e:
            logger.error(f"Failed to get device list: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def _check_connectivity(self) -> bool:
        """Check if we can reach external payment gateways."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.stripe.com/v1", timeout=5.0)
                return resp.status_code in (200, 401, 403)
        except Exception:
            return False

    async def _offline_sync_loop(self):
        """Background loop that drains the offline queue when connectivity returns."""
        while True:
            try:
                await asyncio.sleep(30)
                pending = self.offline_queue.peek_all()
                if not pending:
                    continue

                online = await self._check_connectivity()
                if not online:
                    self._is_online = False
                    logger.info(f"Still offline — {self.offline_queue.pending_count} transactions queued")
                    continue

                self._is_online = True
                logger.info(f"Connectivity restored — syncing {len(pending)} offline transactions")

                for idx, entry in enumerate(self.offline_queue._queue):
                    if entry["status"] != "queued":
                        continue
                    try:
                        payment_data = entry["payment"]
                        payment_request = PaymentRequest(
                            amount=payment_data["amount"],
                            currency=payment_data["currency"],
                            payment_method=PaymentMethod(payment_data["payment_method"]),
                            merchant_id=payment_data["merchant_id"],
                            terminal_id=payment_data["terminal_id"],
                            transaction_reference=payment_data["transaction_reference"],
                            idempotency_key=payment_data.get("idempotency_key"),
                            customer_data=payment_data.get("customer_data"),
                            metadata=payment_data.get("metadata")
                        )
                        await self.process_payment(payment_request)
                        self.offline_queue.mark_synced(idx)
                        logger.info(f"Synced offline transaction {payment_data.get('transaction_reference')}")
                    except Exception as e:
                        self.offline_queue.mark_failed(idx, str(e))
                        logger.warning(f"Failed to sync offline transaction: {e}")

                self.offline_queue.purge_synced()

            except Exception as e:
                logger.error(f"Offline sync loop error: {e}")
                await asyncio.sleep(60)

    async def queue_offline_payment(self, payment_request: PaymentRequest) -> Dict[str, Any]:
        """Queue a payment for later processing when connectivity is unavailable."""
        payment_data = {
            "amount": payment_request.amount,
            "currency": payment_request.currency,
            "payment_method": payment_request.payment_method.value,
            "merchant_id": payment_request.merchant_id,
            "terminal_id": payment_request.terminal_id,
            "transaction_reference": payment_request.transaction_reference,
            "idempotency_key": payment_request.idempotency_key,
            "customer_data": payment_request.customer_data,
            "metadata": payment_request.metadata,
        }
        self.offline_queue.enqueue(payment_data)
        return {
            "status": "queued",
            "message": "Payment queued for processing when connectivity is restored",
            "queue_position": self.offline_queue.pending_count,
            "transaction_reference": payment_request.transaction_reference
        }

    async def get_offline_queue_status(self) -> Dict[str, Any]:
        """Return current offline queue status."""
        return {
            "is_online": self._is_online,
            "pending_count": self.offline_queue.pending_count,
            "queue": [
                {
                    "transaction_reference": e["payment"].get("transaction_reference"),
                    "amount": e["payment"].get("amount"),
                    "status": e["status"],
                    "queued_at": e["queued_at"],
                    "attempts": e["attempts"],
                }
                for e in self.offline_queue._queue
                if e["status"] in ("queued", "permanently_failed")
            ]
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        db = SessionLocal()
        try:
            # Check database connection
            db.execute("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False
        finally:
            db.close()
        
        # Check Redis connection
        redis_healthy = False
        if self.redis_client:
            try:
                await self.redis_client.ping()
                redis_healthy = True
            except Exception:
                redis_healthy = False
        
        # Check connected devices
        connected_devices_count = len(self.connected_devices)
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "pos-integration-service",
            "version": "2.0.0",
            "components": {
                "database": db_healthy,
                "redis": redis_healthy,
                "connected_devices": connected_devices_count,
                "is_online": self._is_online,
                "offline_queue_pending": self.offline_queue.pending_count
            }
        }

# FastAPI application
app = FastAPI(title="POS Integration Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
pos_service = POSIntegrationService()

# Pydantic models for API
class PaymentRequestModel(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    payment_method: PaymentMethod
    merchant_id: str
    terminal_id: str
    transaction_reference: str
    idempotency_key: Optional[str] = None
    customer_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class DeviceRegistrationModel(BaseModel):
    device_id: Optional[str] = None
    device_type: DeviceType
    device_name: str
    merchant_id: str
    terminal_id: str
    ip_address: Optional[str] = None
    serial_port: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    firmware_version: Optional[str] = None

class DeviceCommandModel(BaseModel):
    command: str
    data: Optional[Dict[str, Any]] = None

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await pos_service.initialize()

@app.post("/process-payment")
async def process_payment(request: PaymentRequestModel):
    """Process a payment transaction"""
    payment_request = PaymentRequest(**request.dict())
    response = await pos_service.process_payment(payment_request)
    return asdict(response)

@app.get("/transaction/{transaction_id}/status")
async def get_transaction_status(transaction_id: str):
    """Get transaction status"""
    return await pos_service.get_transaction_status(transaction_id)

@app.post("/transaction/{transaction_id}/refund")
async def refund_transaction(
    transaction_id: str,
    refund_amount: Optional[float] = None,
    reason: str = ""
):
    """Refund a transaction"""
    return await pos_service.refund_transaction(transaction_id, refund_amount, reason)

@app.post("/device/register")
async def register_device(device: DeviceRegistrationModel):
    """Register a POS device"""
    device_id = await pos_service.register_device(device.dict())
    return {"device_id": device_id, "status": "registered"}

@app.get("/devices")
async def get_devices(merchant_id: Optional[str] = None):
    """Get list of registered devices"""
    return await pos_service.get_device_list(merchant_id)

@app.post("/device/{device_id}/command")
async def send_device_command(device_id: str, command: DeviceCommandModel):
    """Send command to POS device"""
    return await pos_service.send_device_command(device_id, command.command, command.data)

@app.websocket("/ws/transactions/{terminal_id}")
async def websocket_endpoint(websocket: WebSocket, terminal_id: str):
    """WebSocket endpoint for real-time transaction updates"""
    await websocket.accept()
    pos_service.active_websockets[terminal_id] = websocket
    
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming WebSocket messages if needed
            
    except WebSocketDisconnect:
        if terminal_id in pos_service.active_websockets:
            del pos_service.active_websockets[terminal_id]

@app.post("/queue-offline-payment")
async def queue_offline_payment(request: PaymentRequestModel):
    """Queue a payment for offline processing"""
    payment_request = PaymentRequest(**request.dict())
    return await pos_service.queue_offline_payment(payment_request)

@app.get("/offline-queue-status")
async def offline_queue_status():
    """Get offline queue status"""
    return await pos_service.get_offline_queue_status()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await pos_service.health_check()

@app.get("/scoring/analytics")
async def scoring_analytics():
    """Return scoring analytics: approval rate, avg score, decline trends."""
    total = _scoring_analytics["total_scored"]
    avg_score = round(_scoring_analytics["score_sum"] / max(total, 1), 1)
    approval_rate = round(_scoring_analytics["total_approved"] / max(total, 1) * 100, 1)
    decline_rate = round(_scoring_analytics["total_declined"] / max(total, 1) * 100, 1)
    return {
        "total_scored": total,
        "total_approved": _scoring_analytics["total_approved"],
        "total_declined": _scoring_analytics["total_declined"],
        "total_review": _scoring_analytics["total_review"],
        "total_errors": _scoring_analytics["total_errors"],
        "avg_score": avg_score,
        "approval_rate_pct": approval_rate,
        "decline_rate_pct": decline_rate,
        "recent_decisions": _scoring_analytics["recent_decisions"][-20:],
    }


@app.get("/circuit-breakers")
async def circuit_breaker_status():
    """Return circuit breaker status for all feature services."""
    return {
        name: cb.get_status()
        for name, cb in pos_service._circuit_breakers.items()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8016)
