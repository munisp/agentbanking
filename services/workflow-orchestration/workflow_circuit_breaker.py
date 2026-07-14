"""
Circuit Breaker for Workflow External Service Calls

Provides resilient external service calls with:
- Circuit breaker pattern (CLOSED -> OPEN -> HALF_OPEN)
- Configurable failure thresholds
- Automatic recovery testing
- Fail-closed option for critical services (fraud detection)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic

import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class FailureMode(str, Enum):
    FAIL_OPEN = "fail_open"    # Return default on failure (non-critical)
    FAIL_CLOSED = "fail_closed"  # Raise exception on failure (critical)


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_requests: int = 3
    failure_mode: FailureMode = FailureMode.FAIL_OPEN
    default_response: Optional[Dict[str, Any]] = None


@dataclass
class CircuitStats:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    half_open_successes: int = 0
    total_calls: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit tripped, requests fail immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitStats()
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self.stats.state
    
    @property
    def is_closed(self) -> bool:
        return self.stats.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.stats.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.stats.state == CircuitState.HALF_OPEN
    
    async def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.stats.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.stats.last_failure_time
        return elapsed >= self.config.recovery_timeout
    
    async def _transition_to(self, new_state: CircuitState):
        """Transition to a new state"""
        old_state = self.stats.state
        self.stats.state = new_state
        
        if new_state == CircuitState.HALF_OPEN:
            self.stats.half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self.stats.failure_count = 0
        
        logger.info(f"Circuit breaker '{self.name}': {old_state} -> {new_state}")
    
    async def _record_success(self):
        """Record a successful call"""
        async with self._lock:
            self.stats.success_count += 1
            self.stats.last_success_time = time.time()
            
            if self.is_half_open:
                self.stats.half_open_successes += 1
                if self.stats.half_open_successes >= self.config.half_open_requests:
                    await self._transition_to(CircuitState.CLOSED)
    
    async def _record_failure(self):
        """Record a failed call"""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.last_failure_time = time.time()
            
            if self.is_half_open:
                await self._transition_to(CircuitState.OPEN)
            elif self.stats.failure_count >= self.config.failure_threshold:
                await self._transition_to(CircuitState.OPEN)
    
    async def call(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result or default response if circuit is open
            
        Raises:
            CircuitOpenError: If circuit is open and fail_closed mode
        """
        self.stats.total_calls += 1
        
        async with self._lock:
            if self.is_open:
                if await self._should_attempt_reset():
                    await self._transition_to(CircuitState.HALF_OPEN)
                else:
                    if self.config.failure_mode == FailureMode.FAIL_CLOSED:
                        raise CircuitOpenError(
                            f"Circuit breaker '{self.name}' is OPEN"
                        )
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN, "
                        f"returning default response"
                    )
                    return self.config.default_response
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure()
            
            if self.config.failure_mode == FailureMode.FAIL_CLOSED:
                raise
            
            logger.warning(
                f"Circuit breaker '{self.name}' caught error: {e}, "
                f"returning default response"
            )
            return self.config.default_response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "total_calls": self.stats.total_calls,
            "total_failures": self.stats.total_failures,
            "failure_mode": self.config.failure_mode.value,
            "last_failure": datetime.fromtimestamp(
                self.stats.last_failure_time
            ).isoformat() if self.stats.last_failure_time else None
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and fail_closed mode"""
    pass


class WorkflowCircuitBreakerRegistry:
    """Registry of circuit breakers for workflow services"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def register(
        self,
        name: str,
        config: CircuitBreakerConfig = None
    ) -> CircuitBreaker:
        """Register a new circuit breaker"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)
    
    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }


# Global registry
workflow_circuit_registry = WorkflowCircuitBreakerRegistry()


# Pre-configured circuit breakers for workflow services
def get_fraud_detection_breaker() -> CircuitBreaker:
    """
    Fraud detection circuit breaker - FAIL CLOSED
    
    Critical service: if fraud detection fails, block transaction
    """
    return workflow_circuit_registry.get_or_create(
        "fraud_detection",
        CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_requests=2,
            failure_mode=FailureMode.FAIL_CLOSED,
            default_response=None
        )
    )


def get_notification_breaker() -> CircuitBreaker:
    """
    Notification service circuit breaker - FAIL OPEN
    
    Non-critical: transaction should complete even if notifications fail
    """
    return workflow_circuit_registry.get_or_create(
        "notification",
        CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_requests=3,
            failure_mode=FailureMode.FAIL_OPEN,
            default_response={"sent": False, "reason": "service_unavailable"}
        )
    )


def get_analytics_breaker() -> CircuitBreaker:
    """
    Analytics service circuit breaker - FAIL OPEN
    
    Non-critical: transaction should complete even if analytics fail
    """
    return workflow_circuit_registry.get_or_create(
        "analytics",
        CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_requests=3,
            failure_mode=FailureMode.FAIL_OPEN,
            default_response={"recorded": False, "reason": "service_unavailable"}
        )
    )


def get_commission_breaker() -> CircuitBreaker:
    """
    Commission service circuit breaker - FAIL OPEN with logging
    
    Important but not blocking: commission can be calculated later
    """
    return workflow_circuit_registry.get_or_create(
        "commission",
        CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=45.0,
            half_open_requests=2,
            failure_mode=FailureMode.FAIL_OPEN,
            default_response={"calculated": False, "amount": 0, "deferred": True}
        )
    )


def get_receipt_breaker() -> CircuitBreaker:
    """
    Receipt service circuit breaker - FAIL OPEN
    
    Non-critical: receipt can be generated later
    """
    return workflow_circuit_registry.get_or_create(
        "receipt",
        CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_requests=3,
            failure_mode=FailureMode.FAIL_OPEN,
            default_response={"generated": False, "url": None, "deferred": True}
        )
    )


def get_ledger_breaker() -> CircuitBreaker:
    """
    Ledger (TigerBeetle) circuit breaker - FAIL CLOSED
    
    Critical service: if ledger fails, transaction must fail
    """
    return workflow_circuit_registry.get_or_create(
        "ledger",
        CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=120.0,
            half_open_requests=1,
            failure_mode=FailureMode.FAIL_CLOSED,
            default_response=None
        )
    )


class ResilientWorkflowClient:
    """
    HTTP client with circuit breaker protection for workflow activities
    """
    
    def __init__(
        self,
        base_url: str,
        circuit_breaker: CircuitBreaker,
        timeout: float = 30.0
    ):
        self.base_url = base_url
        self.circuit_breaker = circuit_breaker
        self.timeout = timeout
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
    
    async def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """GET request with circuit breaker"""
        async def _request():
            client = await self._get_client()
            response = await client.get(path, **kwargs)
            response.raise_for_status()
            return response.json()
        
        return await self.circuit_breaker.call(_request)
    
    async def post(self, path: str, json: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """POST request with circuit breaker"""
        async def _request():
            client = await self._get_client()
            response = await client.post(path, json=json, **kwargs)
            response.raise_for_status()
            return response.json()
        
        return await self.circuit_breaker.call(_request)


# Factory functions for resilient clients
def create_fraud_client(base_url: str) -> ResilientWorkflowClient:
    """Create fraud detection client with fail-closed circuit breaker"""
    return ResilientWorkflowClient(
        base_url=base_url,
        circuit_breaker=get_fraud_detection_breaker(),
        timeout=10.0
    )


def create_notification_client(base_url: str) -> ResilientWorkflowClient:
    """Create notification client with fail-open circuit breaker"""
    return ResilientWorkflowClient(
        base_url=base_url,
        circuit_breaker=get_notification_breaker(),
        timeout=30.0
    )


def create_analytics_client(base_url: str) -> ResilientWorkflowClient:
    """Create analytics client with fail-open circuit breaker"""
    return ResilientWorkflowClient(
        base_url=base_url,
        circuit_breaker=get_analytics_breaker(),
        timeout=30.0
    )
