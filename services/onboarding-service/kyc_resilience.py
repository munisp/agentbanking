"""
KYC/KYB Resilience Patterns
Circuit breaker, retry logic, and rate limiting for KYC services
"""

import os
import time
import asyncio
import logging
import hashlib
import functools
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, TypeVar, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 30.0
    half_open_max_calls: int = 3
    excluded_exceptions: tuple = ()


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_calls: int = 0


class CircuitBreaker:
    """
    Production-ready circuit breaker for KYC external service calls
    Prevents cascading failures when external services are down
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()
        
    @property
    def state(self) -> CircuitState:
        return self._state.state
    
    async def _check_state_transition(self):
        """Check if circuit should transition states"""
        if self._state.state == CircuitState.OPEN:
            if self._state.last_failure_time:
                elapsed = (datetime.utcnow() - self._state.last_failure_time).total_seconds()
                if elapsed >= self.config.timeout:
                    self._state.state = CircuitState.HALF_OPEN
                    self._state.half_open_calls = 0
                    self._state.success_count = 0
                    logger.info(f"Circuit {self.name} transitioned to HALF_OPEN")
    
    async def _record_success(self):
        """Record successful call"""
        async with self._lock:
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1
                if self._state.success_count >= self.config.success_threshold:
                    self._state.state = CircuitState.CLOSED
                    self._state.failure_count = 0
                    logger.info(f"Circuit {self.name} transitioned to CLOSED")
            elif self._state.state == CircuitState.CLOSED:
                self._state.failure_count = max(0, self._state.failure_count - 1)
    
    async def _record_failure(self, exception: Exception):
        """Record failed call"""
        async with self._lock:
            if isinstance(exception, self.config.excluded_exceptions):
                return
            
            self._state.failure_count += 1
            self._state.last_failure_time = datetime.utcnow()
            
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} transitioned to OPEN (half-open failure)")
            elif self._state.state == CircuitState.CLOSED:
                if self._state.failure_count >= self.config.failure_threshold:
                    self._state.state = CircuitState.OPEN
                    logger.warning(f"Circuit {self.name} transitioned to OPEN (threshold reached)")
    
    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection"""
        await self._check_state_transition()
        
        if self._state.state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")
        
        if self._state.state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._state.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(f"Circuit {self.name} half-open limit reached")
                self._state.half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure(e)
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure_time": self._state.last_failure_time.isoformat() if self._state.last_failure_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


@dataclass
class RetryConfig:
    """Retry configuration with exponential backoff"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


class RetryWithBackoff:
    """
    Retry mechanism with exponential backoff for KYC external services
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter"""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay
    
    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e
                
                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.config.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.config.max_attempts} attempts failed")
        
        raise last_exception


class RateLimiter:
    """
    Token bucket rate limiter for KYC endpoints
    Prevents abuse and ensures fair usage
    """
    
    def __init__(
        self,
        redis_url: str,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        self.redis_url = redis_url
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self._client: Optional[aioredis.Redis] = None
    
    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self.redis_url)
        return self._client
    
    async def is_allowed(self, key: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed under rate limit
        Returns (allowed, rate_limit_info)
        """
        client = await self._get_client()
        
        now = time.time()
        window_start = now - 60  # 1 minute window
        
        rate_key = f"kyc:rate_limit:{key}"
        
        # Use Redis sorted set for sliding window
        pipe = client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(rate_key, 0, window_start)
        
        # Count current requests
        pipe.zcard(rate_key)
        
        # Add current request
        pipe.zadd(rate_key, {str(now): now})
        
        # Set expiry
        pipe.expire(rate_key, 120)
        
        results = await pipe.execute()
        current_count = results[1]
        
        allowed = current_count < self.requests_per_minute
        
        rate_info = {
            "limit": self.requests_per_minute,
            "remaining": max(0, self.requests_per_minute - current_count - 1),
            "reset": int(now + 60),
            "retry_after": None if allowed else 60
        }
        
        if not allowed:
            # Remove the request we just added
            await client.zrem(rate_key, str(now))
        
        return allowed, rate_info
    
    async def close(self):
        if self._client:
            await self._client.close()


class KYCRateLimitMiddleware:
    """
    FastAPI middleware for KYC rate limiting
    """
    
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
    
    async def __call__(self, request, call_next):
        # Extract client identifier (IP or user ID)
        client_id = request.headers.get("X-User-ID") or request.client.host
        
        allowed, rate_info = await self.rate_limiter.is_allowed(client_id)
        
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": rate_info["retry_after"]
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                    "Retry-After": str(rate_info["retry_after"])
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
        
        return response


# Pre-configured circuit breakers for KYC services
class KYCCircuitBreakers:
    """Pre-configured circuit breakers for KYC external services"""
    
    _breakers: Dict[str, CircuitBreaker] = {}
    
    @classmethod
    def get_workflow_breaker(cls) -> CircuitBreaker:
        if "workflow" not in cls._breakers:
            cls._breakers["workflow"] = CircuitBreaker(
                "workflow",
                CircuitBreakerConfig(
                    failure_threshold=3,
                    success_threshold=2,
                    timeout=60.0
                )
            )
        return cls._breakers["workflow"]
    
    @classmethod
    def get_ocr_breaker(cls) -> CircuitBreaker:
        if "ocr" not in cls._breakers:
            cls._breakers["ocr"] = CircuitBreaker(
                "ocr",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    success_threshold=3,
                    timeout=30.0
                )
            )
        return cls._breakers["ocr"]
    
    @classmethod
    def get_sanctions_breaker(cls) -> CircuitBreaker:
        if "sanctions" not in cls._breakers:
            cls._breakers["sanctions"] = CircuitBreaker(
                "sanctions",
                CircuitBreakerConfig(
                    failure_threshold=3,
                    success_threshold=2,
                    timeout=120.0  # Longer timeout for compliance services
                )
            )
        return cls._breakers["sanctions"]
    
    @classmethod
    def get_pep_breaker(cls) -> CircuitBreaker:
        if "pep" not in cls._breakers:
            cls._breakers["pep"] = CircuitBreaker(
                "pep",
                CircuitBreakerConfig(
                    failure_threshold=3,
                    success_threshold=2,
                    timeout=120.0
                )
            )
        return cls._breakers["pep"]
    
    @classmethod
    def get_adverse_media_breaker(cls) -> CircuitBreaker:
        if "adverse_media" not in cls._breakers:
            cls._breakers["adverse_media"] = CircuitBreaker(
                "adverse_media",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    success_threshold=3,
                    timeout=60.0
                )
            )
        return cls._breakers["adverse_media"]
    
    @classmethod
    def get_liveness_breaker(cls) -> CircuitBreaker:
        if "liveness" not in cls._breakers:
            cls._breakers["liveness"] = CircuitBreaker(
                "liveness",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    success_threshold=3,
                    timeout=30.0
                )
            )
        return cls._breakers["liveness"]
    
    @classmethod
    def get_biometric_breaker(cls) -> CircuitBreaker:
        if "biometric" not in cls._breakers:
            cls._breakers["biometric"] = CircuitBreaker(
                "biometric",
                CircuitBreakerConfig(
                    failure_threshold=5,
                    success_threshold=3,
                    timeout=30.0
                )
            )
        return cls._breakers["biometric"]
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        return {name: breaker.get_stats() for name, breaker in cls._breakers.items()}


# Pre-configured retry policies
class KYCRetryPolicies:
    """Pre-configured retry policies for KYC services"""
    
    @classmethod
    def get_external_api_retry(cls) -> RetryWithBackoff:
        return RetryWithBackoff(RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        ))
    
    @classmethod
    def get_screening_retry(cls) -> RetryWithBackoff:
        return RetryWithBackoff(RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True
        ))
    
    @classmethod
    def get_document_processing_retry(cls) -> RetryWithBackoff:
        return RetryWithBackoff(RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=True
        ))


def with_circuit_breaker(breaker: CircuitBreaker):
    """Decorator to wrap async function with circuit breaker"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def with_retry(retry_policy: RetryWithBackoff):
    """Decorator to wrap async function with retry logic"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_policy.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def with_resilience(breaker: CircuitBreaker, retry_policy: RetryWithBackoff):
    """Decorator combining circuit breaker and retry logic"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async def retryable():
                return await breaker.call(func, *args, **kwargs)
            return await retry_policy.execute(retryable)
        return wrapper
    return decorator
