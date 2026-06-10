"""
Circuit Breaker Module
Implements circuit breaker pattern for resilient external service calls
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic
from functools import wraps
import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_requests: int = 3,
        excluded_exceptions: tuple = ()
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        self.excluded_exceptions = excluded_exceptions
        
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._last_state_change = time.time()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def stats(self) -> CircuitBreakerStats:
        return self._stats
    
    async def _check_state(self) -> bool:
        """Check and potentially update circuit state"""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._last_state_change >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    return True
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                if self._half_open_calls < self.half_open_requests:
                    self._half_open_calls += 1
                    return True
                return False
            
            return True  # CLOSED state
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state"""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        logger.info(f"Circuit breaker '{self.name}' transitioned from {old_state} to {new_state}")
    
    async def _record_success(self):
        """Record a successful call"""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # If enough successes in half-open, close the circuit
                if self._stats.consecutive_successes >= self.half_open_requests:
                    self._transition_to(CircuitState.CLOSED)
    
    async def _record_failure(self, exception: Exception):
        """Record a failed call"""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open opens the circuit
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with circuit breaker protection"""
        if not await self._check_state():
            self._stats.rejected_calls += 1
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open, rejecting request"
            )
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except self.excluded_exceptions:
            # Don't count excluded exceptions as failures
            raise
        except Exception as e:
            await self._record_failure(e)
            raise
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator for circuit breaker protection"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        return wrapper


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_requests: int = 3
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_requests=half_open_requests
            )
        return self._breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {
            name: {
                "state": breaker.state.value,
                "total_calls": breaker.stats.total_calls,
                "successful_calls": breaker.stats.successful_calls,
                "failed_calls": breaker.stats.failed_calls,
                "rejected_calls": breaker.stats.rejected_calls,
                "consecutive_failures": breaker.stats.consecutive_failures
            }
            for name, breaker in self._breakers.items()
        }


# Global registry
circuit_breaker_registry = CircuitBreakerRegistry()


class ResilientHttpClient:
    """HTTP client with circuit breaker protection"""
    
    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout: float = 30.0,
        failure_threshold: int = 5,
        recovery_timeout: int = 30
    ):
        self.service_name = service_name
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker_registry.get_or_create(
            name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get(self, path: str, **kwargs) -> httpx.Response:
        """GET request with circuit breaker"""
        async def _request():
            client = await self._get_client()
            response = await client.get(path, **kwargs)
            response.raise_for_status()
            return response
        
        return await self.circuit_breaker.call(_request)
    
    async def post(self, path: str, **kwargs) -> httpx.Response:
        """POST request with circuit breaker"""
        async def _request():
            client = await self._get_client()
            response = await client.post(path, **kwargs)
            response.raise_for_status()
            return response
        
        return await self.circuit_breaker.call(_request)
    
    async def put(self, path: str, **kwargs) -> httpx.Response:
        """PUT request with circuit breaker"""
        async def _request():
            client = await self._get_client()
            response = await client.put(path, **kwargs)
            response.raise_for_status()
            return response
        
        return await self.circuit_breaker.call(_request)
    
    async def delete(self, path: str, **kwargs) -> httpx.Response:
        """DELETE request with circuit breaker"""
        async def _request():
            client = await self._get_client()
            response = await client.delete(path, **kwargs)
            response.raise_for_status()
            return response
        
        return await self.circuit_breaker.call(_request)


# Pre-configured clients for common services
def get_payment_client(base_url: str) -> ResilientHttpClient:
    """Get payment service client with circuit breaker"""
    return ResilientHttpClient(
        service_name="payment-service",
        base_url=base_url,
        timeout=30.0,
        failure_threshold=3,
        recovery_timeout=60
    )


def get_email_client(base_url: str) -> ResilientHttpClient:
    """Get email service client with circuit breaker"""
    return ResilientHttpClient(
        service_name="email-service",
        base_url=base_url,
        timeout=10.0,
        failure_threshold=5,
        recovery_timeout=30
    )


def get_supply_chain_client(base_url: str) -> ResilientHttpClient:
    """Get supply chain service client with circuit breaker"""
    return ResilientHttpClient(
        service_name="supply-chain-service",
        base_url=base_url,
        timeout=15.0,
        failure_threshold=5,
        recovery_timeout=30
    )


def get_inventory_client(base_url: str) -> ResilientHttpClient:
    """Get inventory service client with circuit breaker"""
    return ResilientHttpClient(
        service_name="inventory-service",
        base_url=base_url,
        timeout=10.0,
        failure_threshold=5,
        recovery_timeout=30
    )
