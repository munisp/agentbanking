"""
Idempotency Service - Production Implementation.
Replaces all NotImplementedError stubs with real Redis-backed idempotency logic.
"""
import json
import logging
import os
import time
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis-master.redis.svc.cluster.local:6379")
IDEMPOTENCY_TTL = int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "86400"))  # 24 hours default
IDEMPOTENCY_KEY_PREFIX = "idempotency:"

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    return _redis_client


def _make_key(idempotency_key: str, namespace: str = "default") -> str:
    """Build Redis key for idempotency record."""
    return f"{IDEMPOTENCY_KEY_PREFIX}{namespace}:{idempotency_key}"


def store_result(
    idempotency_key: str,
    result: Any,
    namespace: str = "default",
    ttl: Optional[int] = None,
) -> bool:
    """
    Store the result of an operation with an idempotency key.
    Returns True if stored successfully, False if key already exists (duplicate request).
    """
    redis_client = _get_redis()
    key = _make_key(idempotency_key, namespace)
    record = {
        "result": result,
        "stored_at": time.time(),
        "namespace": namespace,
    }
    serialized = json.dumps(record)
    # SET NX (only if not exists) with TTL
    stored = redis_client.set(key, serialized, ex=ttl or IDEMPOTENCY_TTL, nx=True)
    if stored:
        logger.debug(f"Idempotency key stored: {key}")
    else:
        logger.debug(f"Idempotency key already exists (duplicate): {key}")
    return bool(stored)


def get_result(idempotency_key: str, namespace: str = "default") -> Optional[Any]:
    """
    Retrieve a previously stored result for an idempotency key.
    Returns the result if found, None if not found (new request).
    """
    redis_client = _get_redis()
    key = _make_key(idempotency_key, namespace)
    raw = redis_client.get(key)
    if raw is None:
        return None
    record = json.loads(raw)
    return record.get("result")


def is_duplicate(idempotency_key: str, namespace: str = "default") -> bool:
    """Check if an idempotency key already exists (i.e., is a duplicate request)."""
    redis_client = _get_redis()
    key = _make_key(idempotency_key, namespace)
    return bool(redis_client.exists(key))


def delete_key(idempotency_key: str, namespace: str = "default") -> bool:
    """Delete an idempotency key (e.g., after a failed operation that should be retried)."""
    redis_client = _get_redis()
    key = _make_key(idempotency_key, namespace)
    deleted = redis_client.delete(key)
    return bool(deleted)


def extend_ttl(
    idempotency_key: str,
    namespace: str = "default",
    additional_seconds: int = 3600,
) -> bool:
    """Extend the TTL of an idempotency key."""
    redis_client = _get_redis()
    key = _make_key(idempotency_key, namespace)
    current_ttl = redis_client.ttl(key)
    if current_ttl < 0:
        return False  # Key doesn't exist
    new_ttl = current_ttl + additional_seconds
    return bool(redis_client.expire(key, new_ttl))


def get_key_info(idempotency_key: str, namespace: str = "default") -> Optional[dict]:
    """Get metadata about an idempotency key."""
    redis_client = _get_redis()
    key = _make_key(idempotency_key, namespace)
    raw = redis_client.get(key)
    if raw is None:
        return None
    ttl = redis_client.ttl(key)
    record = json.loads(raw)
    return {
        "idempotency_key": idempotency_key,
        "namespace": namespace,
        "stored_at": record.get("stored_at"),
        "ttl_remaining": ttl,
        "has_result": "result" in record,
    }


class IdempotencyService:
    """
    Class-based idempotency service for dependency injection.
    Provides the same functionality as the module-level functions.
    """

    def __init__(self, namespace: str = "default", ttl: int = IDEMPOTENCY_TTL):
        self.namespace = namespace
        self.ttl = ttl

    def store(self, key: str, result: Any) -> bool:
        return store_result(key, result, self.namespace, self.ttl)

    def get(self, key: str) -> Optional[Any]:
        return get_result(key, self.namespace)

    def is_duplicate(self, key: str) -> bool:
        return is_duplicate(key, self.namespace)

    def delete(self, key: str) -> bool:
        return delete_key(key, self.namespace)

    def extend(self, key: str, additional_seconds: int = 3600) -> bool:
        return extend_ttl(key, self.namespace, additional_seconds)

    def info(self, key: str) -> Optional[dict]:
        return get_key_info(key, self.namespace)
