"""
Resilience utilities for 54Agent Banking Platform

Provides circuit breakers, retry with exponential backoff, and explicit
timeouts for all outbound HTTP calls.

Usage::

    from shared.resilience import resilient_client, circuit_breaker

    async with resilient_client() as client:
        resp = await client.get("https://api.example.com/health")

    @circuit_breaker("payment-gateway")
    async def call_gateway(payload):
        ...
"""

import os
import time
import asyncio
import logging
import random
from typing import Optional, Dict, Any, Callable, TypeVar, Awaitable
from functools import wraps
from enum import Enum

import httpx

logger = logging.getLogger("platform.resilience")

T = TypeVar("T")

DEFAULT_CONNECT_TIMEOUT = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5"))
DEFAULT_READ_TIMEOUT = float(os.getenv("HTTP_READ_TIMEOUT", "30"))
DEFAULT_RETRIES = int(os.getenv("HTTP_RETRIES", "3"))
DEFAULT_BACKOFF_BASE = float(os.getenv("HTTP_BACKOFF_BASE", "0.5"))
DEFAULT_BACKOFF_MAX = float(os.getenv("HTTP_BACKOFF_MAX", "30"))


def resilient_client(
    *,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = DEFAULT_READ_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    headers: Optional[Dict[str, str]] = None,
) -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(retries=retries)
    timeout = httpx.Timeout(connect_timeout, read=read_timeout)
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        headers=headers or {},
    )


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    retries: int = DEFAULT_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    backoff_max: float = DEFAULT_BACKOFF_MAX,
    retryable_exceptions: tuple = (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, ConnectionError, OSError),
    **kwargs: Any,
) -> T:
    last_exc: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt == retries:
                break
            delay = min(backoff_base * (2 ** (attempt - 1)), backoff_max)
            jitter = random.uniform(0, delay * 0.25)
            logger.warning(
                "Retry %d/%d for %s after %.2fs: %s",
                attempt, retries, fn.__name__, delay + jitter, exc,
            )
            await asyncio.sleep(delay + jitter)
    raise last_exc  # type: ignore[misc]


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    __slots__ = (
        "name", "failure_threshold", "recovery_timeout", "half_open_max",
        "_state", "_failure_count", "_success_count", "_last_failure_time",
    )

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit %s CLOSED (recovered)", self.name)
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning("Circuit %s OPEN after %d failures", self.name, self._failure_count)

    def allow_request(self) -> bool:
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF_OPEN:
            return True
        return False


_breakers: Dict[str, _CircuitBreaker] = {}


def get_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> _CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = _CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _breakers[name]


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
):
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        cb = get_breaker(name, failure_threshold, recovery_timeout)

        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if not cb.allow_request():
                raise HTTPCircuitOpenError(f"Circuit '{name}' is OPEN")
            try:
                result = await fn(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as exc:
                cb.record_failure()
                raise
        return wrapper
    return decorator


class HTTPCircuitOpenError(Exception):
    pass
