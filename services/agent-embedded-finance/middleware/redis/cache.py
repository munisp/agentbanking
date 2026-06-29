"""
Agent Embedded Finance — Redis Cache Layer
Redis Cluster client for caching:
  - Credit profiles (TTL: 30 minutes)
  - Active loan summaries (TTL: 15 minutes)
  - BNPL order status (TTL: 15 minutes)
  - Portfolio summaries (TTL: 10 minutes)
  - Idempotency keys for loan/repayment operations (TTL: 24 hours)
"""
import json
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from redis.cluster import RedisCluster
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redis.exceptions import RedisError, ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

REDIS_CLUSTER_NODES  = os.getenv("REDIS_CLUSTER_NODES",
                                  "redis-node-1:6379,redis-node-2:6379,redis-node-3:6379")
REDIS_PASSWORD       = os.getenv("REDIS_PASSWORD", "")
REDIS_SSL            = os.getenv("REDIS_SSL", "true").lower() == "true"
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "2.0"))
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

PREFIX_CREDIT_PROFILE = "fin:credit"      # fin:credit:{tenant_id}:{agent_id}
PREFIX_LOAN_SUMMARY   = "fin:loans"       # fin:loans:{tenant_id}:{agent_id}
PREFIX_BNPL_STATUS    = "fin:bnpl"        # fin:bnpl:{tenant_id}:{order_id}
PREFIX_PORTFOLIO      = "fin:portfolio"   # fin:portfolio:{tenant_id}:{agent_id}
PREFIX_IDEMPOTENCY    = "fin:idempotent"  # fin:idempotent:{key}

TTL_CREDIT_PROFILE = 1800   # 30 minutes
TTL_LOAN_SUMMARY   = 900    # 15 minutes
TTL_BNPL_STATUS    = 900    # 15 minutes
TTL_PORTFOLIO      = 600    # 10 minutes
TTL_IDEMPOTENCY    = 86400  # 24 hours


def _parse_cluster_nodes(nodes_str: str) -> List[Dict[str, Any]]:
    nodes = []
    for node in nodes_str.split(","):
        host, port = node.strip().split(":")
        nodes.append({"host": host, "port": int(port)})
    return nodes


class FinanceRedisCache:
    """Redis Cluster cache for Agent Embedded Finance service."""

    def __init__(self):
        self._client: Optional[RedisCluster] = None

    def _get_client(self) -> RedisCluster:
        if self._client is None:
            startup_nodes = _parse_cluster_nodes(REDIS_CLUSTER_NODES)
            retry = Retry(ExponentialBackoff(cap=2.0, base=0.1), 3)
            self._client = RedisCluster(
                startup_nodes=startup_nodes,
                password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                ssl=REDIS_SSL,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                max_connections=REDIS_MAX_CONNECTIONS,
                retry=retry,
                retry_on_error=[ConnectionError, TimeoutError],
                decode_responses=True,
                skip_full_coverage_check=True,
            )
        return self._client

    # ── Credit Profile Cache ───────────────────────────────────────────────────

    def set_credit_profile(self, tenant_id: str, agent_id: str,
                            profile: Dict[str, Any]) -> bool:
        try:
            key = f"{PREFIX_CREDIT_PROFILE}:{tenant_id}:{agent_id}"
            self._get_client().setex(key, TTL_CREDIT_PROFILE, json.dumps({
                **profile, "_cached_at": datetime.utcnow().isoformat()
            }))
            return True
        except RedisError as e:
            logger.warning("Redis set_credit_profile failed: %s", e)
            return False

    def get_credit_profile(self, tenant_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = f"{PREFIX_CREDIT_PROFILE}:{tenant_id}:{agent_id}"
            value = self._get_client().get(key)
            return json.loads(value) if value else None
        except RedisError as e:
            logger.warning("Redis get_credit_profile failed: %s", e)
            return None

    def invalidate_credit_profile(self, tenant_id: str, agent_id: str) -> bool:
        try:
            key = f"{PREFIX_CREDIT_PROFILE}:{tenant_id}:{agent_id}"
            self._get_client().delete(key)
            return True
        except RedisError:
            return False

    # ── Loan Summary Cache ─────────────────────────────────────────────────────

    def set_loan_summary(self, tenant_id: str, agent_id: str,
                          loans: List[Dict[str, Any]]) -> bool:
        try:
            key = f"{PREFIX_LOAN_SUMMARY}:{tenant_id}:{agent_id}"
            self._get_client().setex(key, TTL_LOAN_SUMMARY, json.dumps({
                "loans": loans,
                "count": len(loans),
                "_cached_at": datetime.utcnow().isoformat(),
            }))
            return True
        except RedisError as e:
            logger.warning("Redis set_loan_summary failed: %s", e)
            return False

    def get_loan_summary(self, tenant_id: str, agent_id: str) -> Optional[List[Dict[str, Any]]]:
        try:
            key = f"{PREFIX_LOAN_SUMMARY}:{tenant_id}:{agent_id}"
            value = self._get_client().get(key)
            if value:
                return json.loads(value).get("loans")
            return None
        except RedisError:
            return None

    def invalidate_loans(self, tenant_id: str, agent_id: str) -> bool:
        try:
            key = f"{PREFIX_LOAN_SUMMARY}:{tenant_id}:{agent_id}"
            self._get_client().delete(key)
            return True
        except RedisError:
            return False

    # ── Portfolio Cache ────────────────────────────────────────────────────────

    def set_portfolio(self, tenant_id: str, agent_id: str,
                       portfolio: Dict[str, Any]) -> bool:
        try:
            key = f"{PREFIX_PORTFOLIO}:{tenant_id}:{agent_id}"
            self._get_client().setex(key, TTL_PORTFOLIO, json.dumps({
                **portfolio, "_cached_at": datetime.utcnow().isoformat()
            }))
            return True
        except RedisError as e:
            logger.warning("Redis set_portfolio failed: %s", e)
            return False

    def get_portfolio(self, tenant_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = f"{PREFIX_PORTFOLIO}:{tenant_id}:{agent_id}"
            value = self._get_client().get(key)
            return json.loads(value) if value else None
        except RedisError:
            return None

    # ── Idempotency Keys ───────────────────────────────────────────────────────

    def set_idempotency_result(self, idempotency_key: str,
                                result: Dict[str, Any]) -> bool:
        """Store the result of an idempotent operation (24-hour TTL)."""
        try:
            key = f"{PREFIX_IDEMPOTENCY}:{idempotency_key}"
            self._get_client().setex(key, TTL_IDEMPOTENCY, json.dumps(result))
            return True
        except RedisError as e:
            logger.warning("Redis set_idempotency_result failed: %s", e)
            return False

    def get_idempotency_result(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored idempotency result."""
        try:
            key = f"{PREFIX_IDEMPOTENCY}:{idempotency_key}"
            value = self._get_client().get(key)
            return json.loads(value) if value else None
        except RedisError:
            return None

    def check_and_set_idempotency(self, idempotency_key: str) -> bool:
        """
        Atomically check and set an idempotency key.
        Returns True if key was newly set (operation is new).
        Returns False if key already exists (duplicate operation).
        """
        try:
            key = f"{PREFIX_IDEMPOTENCY}:{idempotency_key}:lock"
            # SET NX — only set if not exists
            result = self._get_client().set(key, "processing", ex=300, nx=True)
            return result is not None  # True = new operation, False = duplicate
        except RedisError:
            return True  # Fail open — allow operation on Redis error

    # ── Health Check ───────────────────────────────────────────────────────────

    def ping(self) -> bool:
        try:
            return self._get_client().ping()
        except Exception:
            return False


_cache_instance: Optional[FinanceRedisCache] = None


def get_finance_cache() -> FinanceRedisCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = FinanceRedisCache()
    return _cache_instance
