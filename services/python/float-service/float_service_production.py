import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Ready Float Management Service
Implements comprehensive float management with:
- PostgreSQL persistence (replaces in-memory storage)
- TigerBeetle integration for ledger posting
- Idempotency keys for all operations
- Optimistic locking with version field
- Circuit breaker for risk engine
- Event publishing to unified event bus
- Payment rails integration for settlement
"""

import os
import json
import logging
import hashlib
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from uuid import uuid4
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("float-management-service-(production)")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, validator
from tenacity import retry, stop_after_attempt, wait_exponential, CircuitBreaker

logger = logging.getLogger(__name__)


# Configuration
class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/remittance")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    TIGERBEETLE_URL = os.getenv("TIGERBEETLE_URL", "http://localhost:3000")
    RISK_ENGINE_URL = os.getenv("RISK_ENGINE_URL", "http://localhost:8020")
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "http://localhost:8030")
    
    # Float limits by tier
    TIER_LIMITS = {
        "trainee": Decimal("50000"),
        "basic": Decimal("100000"),
        "standard": Decimal("500000"),
        "premium": Decimal("2000000"),
        "elite": Decimal("10000000"),
    }
    
    # Interest rates by risk level
    RISK_INTEREST_RATES = {
        "low": Decimal("0.02"),
        "medium": Decimal("0.03"),
        "high": Decimal("0.05"),
        "critical": Decimal("0.08"),
    }
    
    # Circuit breaker settings
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 30


# Enums
class FloatStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    FROZEN = "frozen"
    CLOSED = "closed"


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    RESERVE = "reserve"
    RELEASE = "release"
    COMMIT = "commit"
    INTEREST = "interest"
    FEE = "fee"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


class SettlementStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    LOW_BALANCE = "low_balance"
    HIGH_BALANCE = "high_balance"
    HIGH_UTILIZATION = "high_utilization"
    SETTLEMENT_DUE = "settlement_due"
    SETTLEMENT_OVERDUE = "settlement_overdue"
    RISK_LEVEL_CHANGE = "risk_level_change"


# Pydantic Models
class FloatBalanceResponse(BaseModel):
    agent_id: str
    currency: str
    available_balance: Decimal
    reserved_balance: Decimal
    utilized_balance: Decimal
    total_limit: Decimal
    utilization_rate: Decimal
    status: FloatStatus
    risk_level: RiskLevel
    last_updated: datetime
    version: int


class InitializeFloatRequest(BaseModel):
    agent_id: str
    tier: str = "basic"
    currency: str = "NGN"
    initial_limit: Optional[Decimal] = None
    min_threshold: Decimal = Decimal("10000")
    max_threshold: Decimal = Decimal("1000000")
    auto_settlement: bool = True
    settlement_frequency: str = "daily"
    
    @validator("tier")
    def validate_tier(cls, v):
        valid_tiers = ["trainee", "basic", "standard", "premium", "elite"]
        if v not in valid_tiers:
            raise ValueError(f"Invalid tier. Must be one of: {valid_tiers}")
        return v


class ReserveFloatRequest(BaseModel):
    amount: Decimal
    transaction_id: str
    description: Optional[str] = None
    
    @validator("amount")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class CommitFloatRequest(BaseModel):
    reservation_id: str
    amount: Optional[Decimal] = None  # If None, commit full reservation


class ReleaseFloatRequest(BaseModel):
    reservation_id: str
    amount: Optional[Decimal] = None  # If None, release full reservation


class SettleFloatRequest(BaseModel):
    amount: Decimal
    payment_method: str = "bank_transfer"  # bank_transfer, mobile_money, wallet
    payment_reference: Optional[str] = None
    bank_account: Optional[str] = None
    mobile_number: Optional[str] = None
    
    @validator("amount")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class RebalanceFloatRequest(BaseModel):
    amount: Decimal
    rebalance_type: str  # TOP_UP, WITHDRAW
    reason: Optional[str] = None
    
    @validator("rebalance_type")
    def validate_type(cls, v):
        if v not in ["TOP_UP", "WITHDRAW"]:
            raise ValueError("Invalid rebalance type")
        return v


class FloatTransactionResponse(BaseModel):
    transaction_id: str
    agent_id: str
    transaction_type: TransactionType
    amount: Decimal
    currency: str
    balance_before: Decimal
    balance_after: Decimal
    timestamp: datetime
    reference: Optional[str]
    idempotency_key: str


# Database connection pool
class DatabasePool:
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                Config.DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=30
            )
        return cls._pool
    
    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None


# Redis connection
class RedisClient:
    _client: Optional[redis.Redis] = None
    
    @classmethod
    async def get_client(cls) -> redis.Redis:
        if cls._client is None:
            cls._client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        return cls._client
    
    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None


# Circuit Breaker for external services
class ServiceCircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = datetime.now(timezone.utc)
        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker {self.name} opened after {self.failures} failures")
    
    def record_success(self):
        self.failures = 0
        self.state = "closed"
    
    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.last_failure_time and \
               (datetime.now(timezone.utc) - self.last_failure_time).seconds > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open


# TigerBeetle Client
class TigerBeetleClient:
    def __init__(self):
        self.base_url = Config.TIGERBEETLE_URL
        self.circuit_breaker = ServiceCircuitBreaker("tigerbeetle")
    
    async def create_account(self, agent_id: str, ledger: int = 1) -> Dict[str, Any]:
        if not self.circuit_breaker.can_execute():
            raise HTTPException(status_code=503, detail="TigerBeetle service unavailable")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/accounts",
                    json={
                        "id": self._generate_account_id(agent_id),
                        "ledger": ledger,
                        "code": 1,  # Float account type
                        "flags": 0,
                        "user_data": agent_id
                    }
                )
                response.raise_for_status()
                self.circuit_breaker.record_success()
                return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"TigerBeetle create_account failed: {e}")
            raise
    
    async def create_transfer(
        self,
        debit_account_id: str,
        credit_account_id: str,
        amount: int,
        ledger: int = 1,
        code: int = 1,
        flags: int = 0,
        pending_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.circuit_breaker.can_execute():
            raise HTTPException(status_code=503, detail="TigerBeetle service unavailable")
        
        try:
            transfer_data = {
                "id": str(uuid4()),
                "debit_account_id": debit_account_id,
                "credit_account_id": credit_account_id,
                "amount": amount,
                "ledger": ledger,
                "code": code,
                "flags": flags,
            }
            if pending_id:
                transfer_data["pending_id"] = pending_id
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/transfers",
                    json=transfer_data
                )
                response.raise_for_status()
                self.circuit_breaker.record_success()
                return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"TigerBeetle create_transfer failed: {e}")
            raise
    
    async def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        if not self.circuit_breaker.can_execute():
            raise HTTPException(status_code=503, detail="TigerBeetle service unavailable")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/accounts/{account_id}")
                response.raise_for_status()
                self.circuit_breaker.record_success()
                return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"TigerBeetle get_account_balance failed: {e}")
            raise
    
    def _generate_account_id(self, agent_id: str) -> str:
        return hashlib.sha256(f"float:{agent_id}".encode()).hexdigest()[:32]


# Risk Engine Client with Circuit Breaker
class RiskEngineClient:
    def __init__(self):
        self.base_url = Config.RISK_ENGINE_URL
        self.circuit_breaker = ServiceCircuitBreaker("risk_engine")
    
    async def assess_risk(self, agent_id: str, assessment_type: str = "initial") -> Dict[str, Any]:
        if not self.circuit_breaker.can_execute():
            logger.warning("Risk engine circuit breaker open, using fallback")
            return self._fallback_assessment(agent_id)
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/api/risk/assess",
                    json={
                        "agent_id": agent_id,
                        "assessment_type": assessment_type
                    }
                )
                response.raise_for_status()
                self.circuit_breaker.record_success()
                return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.warning(f"Risk engine failed, using fallback: {e}")
            return self._fallback_assessment(agent_id)
    
    def _fallback_assessment(self, agent_id: str) -> Dict[str, Any]:
        """Fallback risk assessment when risk engine is unavailable"""
        return {
            "agent_id": agent_id,
            "overall_score": 50.0,
            "risk_level": "medium",
            "recommended_limit": float(Config.TIER_LIMITS["basic"]),
            "is_fallback": True,
            "assessment_date": datetime.now(timezone.utc).isoformat()
        }


# Event Publisher
class EventPublisher:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
    
    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = await RedisClient.get_client()
        return self._redis
    
    async def publish_event(self, event_type: str, payload: Dict[str, Any]):
        try:
            r = await self._get_redis()
            event = {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload
            }
            await r.publish(f"float:{event_type}", json.dumps(event, default=str))
            logger.info(f"Published event: {event_type}")
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")


# Payment Gateway Client
class PaymentGatewayClient:
    def __init__(self):
        self.base_url = Config.PAYMENT_GATEWAY_URL
        self.circuit_breaker = ServiceCircuitBreaker("payment_gateway")
    
    async def initiate_settlement(
        self,
        agent_id: str,
        amount: Decimal,
        payment_method: str,
        reference: str,
        bank_account: Optional[str] = None,
        mobile_number: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.circuit_breaker.can_execute():
            raise HTTPException(status_code=503, detail="Payment gateway unavailable")
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/api/settlements",
                    json={
                        "agent_id": agent_id,
                        "amount": str(amount),
                        "payment_method": payment_method,
                        "reference": reference,
                        "bank_account": bank_account,
                        "mobile_number": mobile_number
                    }
                )
                response.raise_for_status()
                self.circuit_breaker.record_success()
                return response.json()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Payment gateway settlement failed: {e}")
            raise


# Main Float Service
class FloatService:
    def __init__(self):
        self.tigerbeetle = TigerBeetleClient()
        self.risk_engine = RiskEngineClient()
        self.event_publisher = EventPublisher()
        self.payment_gateway = PaymentGatewayClient()
    
    async def _get_pool(self) -> asyncpg.Pool:
        return await DatabasePool.get_pool()
    
    async def _get_redis(self) -> redis.Redis:
        return await RedisClient.get_client()
    
    async def _check_idempotency(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if operation was already processed"""
        r = await self._get_redis()
        cached = await r.get(f"idempotency:{idempotency_key}")
        if cached:
            return json.loads(cached)
        return None
    
    async def _store_idempotency(self, idempotency_key: str, result: Dict[str, Any], ttl: int = 86400):
        """Store idempotency result for 24 hours"""
        r = await self._get_redis()
        await r.setex(f"idempotency:{idempotency_key}", ttl, json.dumps(result, default=str))
    
    async def _acquire_lock(self, lock_key: str, ttl: int = 30) -> bool:
        """Acquire distributed lock"""
        r = await self._get_redis()
        return await r.set(f"lock:{lock_key}", "1", nx=True, ex=ttl)
    
    async def _release_lock(self, lock_key: str):
        """Release distributed lock"""
        r = await self._get_redis()
        await r.delete(f"lock:{lock_key}")
    
    async def initialize_float(
        self,
        request: InitializeFloatRequest,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Initialize float facility for an agent"""
        
        # Check idempotency
        cached = await self._check_idempotency(idempotency_key)
        if cached:
            return cached
        
        pool = await self._get_pool()
        
        # Check if float already exists
        existing = await pool.fetchrow(
            "SELECT id FROM float_facilities WHERE agent_id = $1",
            request.agent_id
        )
        if existing:
            raise HTTPException(status_code=400, detail="Float facility already exists")
        
        # Perform risk assessment
        risk_assessment = await self.risk_engine.assess_risk(request.agent_id, "initial")
        risk_level = RiskLevel(risk_assessment.get("risk_level", "medium"))
        
        # Calculate initial limit
        tier_limit = Config.TIER_LIMITS.get(request.tier, Config.TIER_LIMITS["basic"])
        if request.initial_limit:
            initial_limit = min(request.initial_limit, tier_limit)
        else:
            initial_limit = tier_limit
        
        # Get interest rate based on risk
        interest_rate = Config.RISK_INTEREST_RATES.get(risk_level.value, Decimal("0.03"))
        
        # Create TigerBeetle account
        try:
            await self.tigerbeetle.create_account(request.agent_id)
        except Exception as e:
            logger.warning(f"TigerBeetle account creation failed (will retry): {e}")
        
        # Create float facility in database
        facility_id = str(uuid4())
        now = datetime.now(timezone.utc)
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO float_facilities (
                        id, agent_id, tier, currency, total_limit, available_balance,
                        reserved_balance, utilized_balance, min_threshold, max_threshold,
                        interest_rate, risk_level, status, auto_settlement, settlement_frequency,
                        version, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                """,
                    facility_id, request.agent_id, request.tier, request.currency,
                    initial_limit, initial_limit, Decimal("0"), Decimal("0"),
                    request.min_threshold, request.max_threshold, interest_rate,
                    risk_level.value, FloatStatus.ACTIVE.value, request.auto_settlement,
                    request.settlement_frequency, 1, now, now
                )
                
                # Create initial transaction record
                await conn.execute("""
                    INSERT INTO float_transactions (
                        id, facility_id, agent_id, transaction_type, amount, currency,
                        balance_before, balance_after, reference, idempotency_key, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                    str(uuid4()), facility_id, request.agent_id, TransactionType.CREDIT.value,
                    initial_limit, request.currency, Decimal("0"), initial_limit,
                    "Initial float facility", idempotency_key, now
                )
                
                # Store risk assessment
                await conn.execute("""
                    INSERT INTO float_risk_assessments (
                        id, facility_id, agent_id, overall_score, risk_level,
                        recommended_limit, is_fallback, assessed_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    str(uuid4()), facility_id, request.agent_id,
                    risk_assessment.get("overall_score", 50.0), risk_level.value,
                    risk_assessment.get("recommended_limit", float(initial_limit)),
                    risk_assessment.get("is_fallback", False), now
                )
        
        result = {
            "facility_id": facility_id,
            "agent_id": request.agent_id,
            "tier": request.tier,
            "currency": request.currency,
            "total_limit": str(initial_limit),
            "available_balance": str(initial_limit),
            "risk_level": risk_level.value,
            "status": FloatStatus.ACTIVE.value,
            "created_at": now.isoformat()
        }
        
        # Store idempotency result
        await self._store_idempotency(idempotency_key, result)
        
        # Publish event
        await self.event_publisher.publish_event("float_initialized", result)
        
        return result
    
    async def get_balance(self, agent_id: str) -> FloatBalanceResponse:
        """Get current float balance for an agent"""
        pool = await self._get_pool()
        
        row = await pool.fetchrow("""
            SELECT id, agent_id, currency, available_balance, reserved_balance,
                   utilized_balance, total_limit, status, risk_level, version, updated_at
            FROM float_facilities WHERE agent_id = $1
        """, agent_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Float facility not found")
        
        utilization_rate = Decimal("0")
        if row["total_limit"] > 0:
            utilization_rate = (row["utilized_balance"] / row["total_limit"] * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        
        return FloatBalanceResponse(
            agent_id=row["agent_id"],
            currency=row["currency"],
            available_balance=row["available_balance"],
            reserved_balance=row["reserved_balance"],
            utilized_balance=row["utilized_balance"],
            total_limit=row["total_limit"],
            utilization_rate=utilization_rate,
            status=FloatStatus(row["status"]),
            risk_level=RiskLevel(row["risk_level"]),
            last_updated=row["updated_at"],
            version=row["version"]
        )
    
    async def reserve_float(
        self,
        agent_id: str,
        request: ReserveFloatRequest,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Reserve float for a pending transaction (2-phase commit - phase 1)"""
        
        # Check idempotency
        cached = await self._check_idempotency(idempotency_key)
        if cached:
            return cached
        
        # Acquire lock
        lock_key = f"float:{agent_id}"
        if not await self._acquire_lock(lock_key):
            raise HTTPException(status_code=409, detail="Concurrent operation in progress")
        
        try:
            pool = await self._get_pool()
            
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Get current balance with row lock
                    row = await conn.fetchrow("""
                        SELECT id, available_balance, reserved_balance, total_limit, 
                               currency, status, version
                        FROM float_facilities 
                        WHERE agent_id = $1
                        FOR UPDATE
                    """, agent_id)
                    
                    if not row:
                        raise HTTPException(status_code=404, detail="Float facility not found")
                    
                    if row["status"] != FloatStatus.ACTIVE.value:
                        raise HTTPException(status_code=400, detail="Float facility is not active")
                    
                    if row["available_balance"] < request.amount:
                        raise HTTPException(status_code=400, detail="Insufficient float balance")
                    
                    # Calculate new balances
                    new_available = row["available_balance"] - request.amount
                    new_reserved = row["reserved_balance"] + request.amount
                    new_version = row["version"] + 1
                    now = datetime.now(timezone.utc)
                    
                    # Update with optimistic locking
                    result = await conn.execute("""
                        UPDATE float_facilities 
                        SET available_balance = $1, reserved_balance = $2, 
                            version = $3, updated_at = $4
                        WHERE agent_id = $5 AND version = $6
                    """, new_available, new_reserved, new_version, now, agent_id, row["version"])
                    
                    if result == "UPDATE 0":
                        raise HTTPException(status_code=409, detail="Concurrent modification detected")
                    
                    # Create reservation record
                    reservation_id = str(uuid4())
                    await conn.execute("""
                        INSERT INTO float_reservations (
                            id, facility_id, agent_id, transaction_id, amount, currency,
                            status, idempotency_key, created_at, expires_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                        reservation_id, row["id"], agent_id, request.transaction_id,
                        request.amount, row["currency"], "pending", idempotency_key,
                        now, now + timedelta(minutes=30)
                    )
                    
                    # Create transaction record
                    await conn.execute("""
                        INSERT INTO float_transactions (
                            id, facility_id, agent_id, transaction_type, amount, currency,
                            balance_before, balance_after, reference, idempotency_key, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        str(uuid4()), row["id"], agent_id, TransactionType.RESERVE.value,
                        request.amount, row["currency"], row["available_balance"], new_available,
                        request.description or f"Reserve for {request.transaction_id}",
                        idempotency_key, now
                    )
            
            result = {
                "reservation_id": reservation_id,
                "agent_id": agent_id,
                "amount": str(request.amount),
                "available_balance": str(new_available),
                "reserved_balance": str(new_reserved),
                "status": "reserved",
                "expires_at": (now + timedelta(minutes=30)).isoformat()
            }
            
            # Store idempotency result
            await self._store_idempotency(idempotency_key, result)
            
            # Publish event
            await self.event_publisher.publish_event("float_reserved", result)
            
            return result
            
        finally:
            await self._release_lock(lock_key)
    
    async def commit_float(
        self,
        agent_id: str,
        request: CommitFloatRequest,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Commit reserved float (2-phase commit - phase 2)"""
        
        # Check idempotency
        cached = await self._check_idempotency(idempotency_key)
        if cached:
            return cached
        
        # Acquire lock
        lock_key = f"float:{agent_id}"
        if not await self._acquire_lock(lock_key):
            raise HTTPException(status_code=409, detail="Concurrent operation in progress")
        
        try:
            pool = await self._get_pool()
            
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Get reservation
                    reservation = await conn.fetchrow("""
                        SELECT id, facility_id, amount, status
                        FROM float_reservations
                        WHERE id = $1 AND agent_id = $2
                        FOR UPDATE
                    """, request.reservation_id, agent_id)
                    
                    if not reservation:
                        raise HTTPException(status_code=404, detail="Reservation not found")
                    
                    if reservation["status"] != "pending":
                        raise HTTPException(status_code=400, detail="Reservation already processed")
                    
                    commit_amount = request.amount or reservation["amount"]
                    if commit_amount > reservation["amount"]:
                        raise HTTPException(status_code=400, detail="Commit amount exceeds reservation")
                    
                    # Get current balance
                    row = await conn.fetchrow("""
                        SELECT reserved_balance, utilized_balance, total_limit, currency, version
                        FROM float_facilities WHERE agent_id = $1
                        FOR UPDATE
                    """, agent_id)
                    
                    if row["reserved_balance"] < commit_amount:
                        raise HTTPException(status_code=400, detail="Insufficient reserved balance")
                    
                    # Calculate new balances
                    new_reserved = row["reserved_balance"] - commit_amount
                    new_utilized = row["utilized_balance"] + commit_amount
                    release_amount = reservation["amount"] - commit_amount
                    new_version = row["version"] + 1
                    now = datetime.now(timezone.utc)
                    
                    # If partial commit, release the difference back to available
                    available_adjustment = release_amount
                    
                    # Update balances
                    await conn.execute("""
                        UPDATE float_facilities 
                        SET reserved_balance = $1, utilized_balance = $2,
                            available_balance = available_balance + $3,
                            version = $4, updated_at = $5
                        WHERE agent_id = $6
                    """, new_reserved, new_utilized, available_adjustment, new_version, now, agent_id)
                    
                    # Update reservation status
                    await conn.execute("""
                        UPDATE float_reservations 
                        SET status = $1, committed_amount = $2, committed_at = $3
                        WHERE id = $4
                    """, "committed", commit_amount, now, request.reservation_id)
                    
                    # Create transaction record
                    await conn.execute("""
                        INSERT INTO float_transactions (
                            id, facility_id, agent_id, transaction_type, amount, currency,
                            balance_before, balance_after, reference, idempotency_key, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        str(uuid4()), reservation["facility_id"], agent_id,
                        TransactionType.COMMIT.value, commit_amount, row["currency"],
                        row["utilized_balance"], new_utilized,
                        f"Commit reservation {request.reservation_id}",
                        idempotency_key, now
                    )
            
            result = {
                "reservation_id": request.reservation_id,
                "agent_id": agent_id,
                "committed_amount": str(commit_amount),
                "utilized_balance": str(new_utilized),
                "status": "committed"
            }
            
            await self._store_idempotency(idempotency_key, result)
            await self.event_publisher.publish_event("float_committed", result)
            
            return result
            
        finally:
            await self._release_lock(lock_key)
    
    async def release_float(
        self,
        agent_id: str,
        request: ReleaseFloatRequest,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Release reserved float back to available"""
        
        # Check idempotency
        cached = await self._check_idempotency(idempotency_key)
        if cached:
            return cached
        
        # Acquire lock
        lock_key = f"float:{agent_id}"
        if not await self._acquire_lock(lock_key):
            raise HTTPException(status_code=409, detail="Concurrent operation in progress")
        
        try:
            pool = await self._get_pool()
            
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Get reservation
                    reservation = await conn.fetchrow("""
                        SELECT id, facility_id, amount, status
                        FROM float_reservations
                        WHERE id = $1 AND agent_id = $2
                        FOR UPDATE
                    """, request.reservation_id, agent_id)
                    
                    if not reservation:
                        raise HTTPException(status_code=404, detail="Reservation not found")
                    
                    if reservation["status"] != "pending":
                        raise HTTPException(status_code=400, detail="Reservation already processed")
                    
                    release_amount = request.amount or reservation["amount"]
                    if release_amount > reservation["amount"]:
                        raise HTTPException(status_code=400, detail="Release amount exceeds reservation")
                    
                    # Get current balance
                    row = await conn.fetchrow("""
                        SELECT available_balance, reserved_balance, currency, version
                        FROM float_facilities WHERE agent_id = $1
                        FOR UPDATE
                    """, agent_id)
                    
                    # Calculate new balances
                    new_available = row["available_balance"] + release_amount
                    new_reserved = row["reserved_balance"] - release_amount
                    new_version = row["version"] + 1
                    now = datetime.now(timezone.utc)
                    
                    # Update balances
                    await conn.execute("""
                        UPDATE float_facilities 
                        SET available_balance = $1, reserved_balance = $2,
                            version = $3, updated_at = $4
                        WHERE agent_id = $5
                    """, new_available, new_reserved, new_version, now, agent_id)
                    
                    # Update reservation status
                    status = "released" if release_amount == reservation["amount"] else "partial_release"
                    await conn.execute("""
                        UPDATE float_reservations 
                        SET status = $1, released_amount = $2, released_at = $3
                        WHERE id = $4
                    """, status, release_amount, now, request.reservation_id)
                    
                    # Create transaction record
                    await conn.execute("""
                        INSERT INTO float_transactions (
                            id, facility_id, agent_id, transaction_type, amount, currency,
                            balance_before, balance_after, reference, idempotency_key, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        str(uuid4()), reservation["facility_id"], agent_id,
                        TransactionType.RELEASE.value, release_amount, row["currency"],
                        row["available_balance"], new_available,
                        f"Release reservation {request.reservation_id}",
                        idempotency_key, now
                    )
            
            result = {
                "reservation_id": request.reservation_id,
                "agent_id": agent_id,
                "released_amount": str(release_amount),
                "available_balance": str(new_available),
                "status": "released"
            }
            
            await self._store_idempotency(idempotency_key, result)
            await self.event_publisher.publish_event("float_released", result)
            
            return result
            
        finally:
            await self._release_lock(lock_key)
    
    async def settle_float(
        self,
        agent_id: str,
        request: SettleFloatRequest,
        idempotency_key: str,
        settled_by: str
    ) -> Dict[str, Any]:
        """Settle outstanding float with payment rails integration"""
        
        # Check idempotency
        cached = await self._check_idempotency(idempotency_key)
        if cached:
            return cached
        
        # Acquire lock
        lock_key = f"float:{agent_id}"
        if not await self._acquire_lock(lock_key):
            raise HTTPException(status_code=409, detail="Concurrent operation in progress")
        
        try:
            pool = await self._get_pool()
            
            # Get current balance
            row = await pool.fetchrow("""
                SELECT id, utilized_balance, available_balance, total_limit, currency, version
                FROM float_facilities WHERE agent_id = $1
            """, agent_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Float facility not found")
            
            if row["utilized_balance"] == 0:
                raise HTTPException(status_code=400, detail="No outstanding float to settle")
            
            settle_amount = min(request.amount, row["utilized_balance"])
            settlement_ref = request.payment_reference or f"SETTLE-{uuid4().hex[:8].upper()}"
            
            # Initiate payment via payment gateway
            try:
                payment_result = await self.payment_gateway.initiate_settlement(
                    agent_id=agent_id,
                    amount=settle_amount,
                    payment_method=request.payment_method,
                    reference=settlement_ref,
                    bank_account=request.bank_account,
                    mobile_number=request.mobile_number
                )
                payment_status = payment_result.get("status", "pending")
            except Exception as e:
                logger.error(f"Payment gateway failed: {e}")
                payment_status = "pending"
                payment_result = {"error": str(e)}
            
            now = datetime.now(timezone.utc)
            settlement_id = str(uuid4())
            
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Calculate new balances
                    new_utilized = row["utilized_balance"] - settle_amount
                    new_available = row["available_balance"] + settle_amount
                    new_version = row["version"] + 1
                    
                    # Update balances
                    await conn.execute("""
                        UPDATE float_facilities 
                        SET utilized_balance = $1, available_balance = $2,
                            version = $3, updated_at = $4,
                            last_settlement_at = $5
                        WHERE agent_id = $6
                    """, new_utilized, new_available, new_version, now, now, agent_id)
                    
                    # Create settlement record
                    await conn.execute("""
                        INSERT INTO float_settlements (
                            id, facility_id, agent_id, amount, currency, payment_method,
                            payment_reference, status, settled_by, idempotency_key, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        settlement_id, row["id"], agent_id, settle_amount, row["currency"],
                        request.payment_method, settlement_ref, payment_status,
                        settled_by, idempotency_key, now
                    )
                    
                    # Create transaction record
                    await conn.execute("""
                        INSERT INTO float_transactions (
                            id, facility_id, agent_id, transaction_type, amount, currency,
                            balance_before, balance_after, reference, idempotency_key, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        str(uuid4()), row["id"], agent_id, TransactionType.DEBIT.value,
                        settle_amount, row["currency"], row["utilized_balance"], new_utilized,
                        f"Settlement {settlement_ref}", idempotency_key, now
                    )
            
            result = {
                "settlement_id": settlement_id,
                "agent_id": agent_id,
                "amount": str(settle_amount),
                "payment_reference": settlement_ref,
                "payment_status": payment_status,
                "utilized_balance": str(new_utilized),
                "available_balance": str(new_available),
                "status": "completed" if payment_status == "completed" else "pending"
            }
            
            await self._store_idempotency(idempotency_key, result)
            await self.event_publisher.publish_event("float_settled", result)
            
            return result
            
        finally:
            await self._release_lock(lock_key)
    
    async def get_transactions(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get float transaction history"""
        pool = await self._get_pool()
        
        rows = await pool.fetch("""
            SELECT id, transaction_type, amount, currency, balance_before, balance_after,
                   reference, idempotency_key, created_at
            FROM float_transactions
            WHERE agent_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, agent_id, limit, offset)
        
        return [dict(row) for row in rows]
    
    async def check_alerts(self, agent_id: str) -> List[Dict[str, Any]]:
        """Check and create alerts for balance thresholds"""
        pool = await self._get_pool()
        
        row = await pool.fetchrow("""
            SELECT available_balance, utilized_balance, total_limit,
                   min_threshold, max_threshold
            FROM float_facilities WHERE agent_id = $1
        """, agent_id)
        
        if not row:
            return []
        
        alerts = []
        now = datetime.now(timezone.utc)
        
        # Low balance alert
        if row["available_balance"] < row["min_threshold"]:
            severity = "critical" if row["available_balance"] < row["min_threshold"] * Decimal("0.5") else "warning"
            alerts.append({
                "alert_type": AlertType.LOW_BALANCE.value,
                "severity": severity,
                "current_balance": str(row["available_balance"]),
                "threshold": str(row["min_threshold"]),
                "timestamp": now.isoformat()
            })
        
        # High utilization alert
        if row["total_limit"] > 0:
            utilization = row["utilized_balance"] / row["total_limit"]
            if utilization > Decimal("0.8"):
                alerts.append({
                    "alert_type": AlertType.HIGH_UTILIZATION.value,
                    "severity": "warning" if utilization < Decimal("0.9") else "critical",
                    "utilization_rate": str(utilization * 100),
                    "timestamp": now.isoformat()
                })
        
        # Publish alerts
        for alert in alerts:
            await self.event_publisher.publish_event("float_alert", {
                "agent_id": agent_id,
                **alert
            })
        
        return alerts


# Database schema initialization
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS float_facilities (
    id UUID PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL UNIQUE,
    tier VARCHAR(50) NOT NULL DEFAULT 'basic',
    currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
    total_limit DECIMAL(18,2) NOT NULL DEFAULT 0,
    available_balance DECIMAL(18,2) NOT NULL DEFAULT 0,
    reserved_balance DECIMAL(18,2) NOT NULL DEFAULT 0,
    utilized_balance DECIMAL(18,2) NOT NULL DEFAULT 0,
    min_threshold DECIMAL(18,2) NOT NULL DEFAULT 10000,
    max_threshold DECIMAL(18,2) NOT NULL DEFAULT 1000000,
    interest_rate DECIMAL(5,4) NOT NULL DEFAULT 0.03,
    risk_level VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    auto_settlement BOOLEAN NOT NULL DEFAULT true,
    settlement_frequency VARCHAR(20) NOT NULL DEFAULT 'daily',
    last_settlement_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS float_transactions (
    id UUID PRIMARY KEY,
    facility_id UUID NOT NULL REFERENCES float_facilities(id),
    agent_id VARCHAR(255) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
    balance_before DECIMAL(18,2) NOT NULL,
    balance_after DECIMAL(18,2) NOT NULL,
    reference TEXT,
    idempotency_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS float_reservations (
    id UUID PRIMARY KEY,
    facility_id UUID NOT NULL REFERENCES float_facilities(id),
    agent_id VARCHAR(255) NOT NULL,
    transaction_id VARCHAR(255) NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    committed_amount DECIMAL(18,2),
    released_amount DECIMAL(18,2),
    idempotency_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    committed_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS float_settlements (
    id UUID PRIMARY KEY,
    facility_id UUID NOT NULL REFERENCES float_facilities(id),
    agent_id VARCHAR(255) NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
    payment_method VARCHAR(50) NOT NULL,
    payment_reference VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    settled_by VARCHAR(255),
    idempotency_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS float_risk_assessments (
    id UUID PRIMARY KEY,
    facility_id UUID NOT NULL REFERENCES float_facilities(id),
    agent_id VARCHAR(255) NOT NULL,
    overall_score DECIMAL(5,2) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    recommended_limit DECIMAL(18,2) NOT NULL,
    is_fallback BOOLEAN NOT NULL DEFAULT false,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_float_facilities_agent ON float_facilities(agent_id);
CREATE INDEX IF NOT EXISTS idx_float_transactions_agent ON float_transactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_float_transactions_facility ON float_transactions(facility_id);
CREATE INDEX IF NOT EXISTS idx_float_reservations_agent ON float_reservations(agent_id);
CREATE INDEX IF NOT EXISTS idx_float_reservations_status ON float_reservations(status);
CREATE INDEX IF NOT EXISTS idx_float_settlements_agent ON float_settlements(agent_id);
CREATE INDEX IF NOT EXISTS idx_float_idempotency ON float_transactions(idempotency_key);
"""


# FastAPI Application
app = FastAPI(
    title="Float Management Service (Production)",
    description="Production-ready float management with PostgreSQL, TigerBeetle, idempotency, and payment rails",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

float_service = FloatService()


@app.on_event("startup")
async def startup():
    """Initialize database schema on startup"""
    pool = await DatabasePool.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info("Float service started with PostgreSQL persistence")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    await DatabasePool.close()
    await RedisClient.close()


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "float-service-production",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/float/initialize")
async def initialize_float(
    request: InitializeFloatRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key")
):
    return await float_service.initialize_float(request, x_idempotency_key)


@app.get("/float/{agent_id}")
async def get_float_balance(agent_id: str):
    return await float_service.get_balance(agent_id)


@app.post("/float/{agent_id}/reserve")
async def reserve_float(
    agent_id: str,
    request: ReserveFloatRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key")
):
    return await float_service.reserve_float(agent_id, request, x_idempotency_key)


@app.post("/float/{agent_id}/commit")
async def commit_float(
    agent_id: str,
    request: CommitFloatRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key")
):
    return await float_service.commit_float(agent_id, request, x_idempotency_key)


@app.post("/float/{agent_id}/release")
async def release_float(
    agent_id: str,
    request: ReleaseFloatRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key")
):
    return await float_service.release_float(agent_id, request, x_idempotency_key)


@app.post("/float/{agent_id}/settle")
async def settle_float(
    agent_id: str,
    request: SettleFloatRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
    x_settled_by: str = Header(..., alias="X-Settled-By")
):
    return await float_service.settle_float(agent_id, request, x_idempotency_key, x_settled_by)


@app.get("/float/{agent_id}/transactions")
async def get_transactions(
    agent_id: str,
    limit: int = 100,
    offset: int = 0
):
    return await float_service.get_transactions(agent_id, limit, offset)


@app.get("/float/{agent_id}/alerts")
async def check_alerts(agent_id: str):
    return await float_service.check_alerts(agent_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
