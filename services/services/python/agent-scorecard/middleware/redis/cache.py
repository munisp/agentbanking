"""
Agent Scorecard — Redis Cache Layer
Direct Redis Cluster client with connection pooling, serialization,
and cache-aside pattern implementation.
Used for:
  - Latest scorecard per agent (TTL: 1 hour)
  - Leaderboard snapshots (TTL: 5 minutes)
  - Benchmark statistics (TTL: 1 hour)
  - Recompute queue deduplication (TTL: 10 minutes)
"""
import json
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib

import redis
from redis.cluster import RedisCluster
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redis.exceptions import RedisError, ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
REDIS_CLUSTER_NODES = os.getenv(
    "REDIS_CLUSTER_NODES",
    "redis-node-1:6379,redis-node-2:6379,redis-node-3:6379"
)
REDIS_PASSWORD      = os.getenv("REDIS_PASSWORD", "")
REDIS_SSL           = os.getenv("REDIS_SSL", "true").lower() == "true"
REDIS_SOCKET_TIMEOUT     = float(os.getenv("REDIS_SOCKET_TIMEOUT", "2.0"))
REDIS_CONNECT_TIMEOUT    = float(os.getenv("REDIS_CONNECT_TIMEOUT", "2.0"))
REDIS_MAX_CONNECTIONS    = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

# Key prefixes
PREFIX_SCORECARD   = "sc:agent"       # sc:agent:{tenant_id}:{agent_id}
PREFIX_LEADERBOARD = "sc:leaderboard" # sc:leaderboard:{tenant_id}
PREFIX_BENCHMARK   = "sc:benchmark"   # sc:benchmark:{tenant_id}
PREFIX_DEDUP       = "sc:dedup"       # sc:dedup:{agent_id}:{tenant_id}

# TTLs (seconds)
TTL_SCORECARD   = 3600   # 1 hour
TTL_LEADERBOARD = 300    # 5 minutes
TTL_BENCHMARK   = 3600   # 1 hour
TTL_DEDUP       = 600    # 10 minutes


def _parse_cluster_nodes(nodes_str: str) -> List[Dict[str, Any]]:
    nodes = []
    for node in nodes_str.split(","):
        host, port = node.strip().split(":")
        nodes.append({"host": host, "port": int(port)})
    return nodes


class ScorecardRedisCache:
    """
    Redis Cluster cache for Agent Scorecard service.
    Implements cache-aside pattern with graceful degradation on cache miss/error.
    """

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
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
                max_connections=REDIS_MAX_CONNECTIONS,
                retry=retry,
                retry_on_error=[ConnectionError, TimeoutError],
                decode_responses=True,
                skip_full_coverage_check=True,  # Allow partial cluster operation
            )
            logger.info("ScorecardRedisCache connected to Redis Cluster")
        return self._client

    def _key_scorecard(self, tenant_id: str, agent_id: str) -> str:
        return f"{PREFIX_SCORECARD}:{tenant_id}:{agent_id}"

    def _key_leaderboard(self, tenant_id: str) -> str:
        return f"{PREFIX_LEADERBOARD}:{tenant_id}"

    def _key_benchmark(self, tenant_id: str) -> str:
        return f"{PREFIX_BENCHMARK}:{tenant_id}"

    def _key_dedup(self, agent_id: str, tenant_id: str) -> str:
        return f"{PREFIX_DEDUP}:{tenant_id}:{agent_id}"

    # ── Scorecard Cache ────────────────────────────────────────────────────────

    def set_scorecard(self, tenant_id: str, agent_id: str,
                      scorecard: Dict[str, Any]) -> bool:
        """Cache a computed scorecard with 1-hour TTL."""
        try:
            client = self._get_client()
            key = self._key_scorecard(tenant_id, agent_id)
            value = json.dumps({
                **scorecard,
                "_cached_at": datetime.utcnow().isoformat(),
            })
            client.setex(key, TTL_SCORECARD, value)
            return True
        except RedisError as e:
            logger.warning("Redis set_scorecard failed for agent=%s: %s", agent_id, e)
            return False

    def get_scorecard(self, tenant_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached scorecard. Returns None on cache miss or error."""
        try:
            client = self._get_client()
            key = self._key_scorecard(tenant_id, agent_id)
            value = client.get(key)
            if value:
                return json.loads(value)
            return None
        except RedisError as e:
            logger.warning("Redis get_scorecard failed for agent=%s: %s", agent_id, e)
            return None

    def invalidate_scorecard(self, tenant_id: str, agent_id: str) -> bool:
        """Invalidate a cached scorecard (e.g., when recompute is triggered)."""
        try:
            client = self._get_client()
            key = self._key_scorecard(tenant_id, agent_id)
            client.delete(key)
            return True
        except RedisError as e:
            logger.warning("Redis invalidate_scorecard failed for agent=%s: %s", agent_id, e)
            return False

    # ── Leaderboard Cache ──────────────────────────────────────────────────────

    def set_leaderboard(self, tenant_id: str, leaderboard: List[Dict[str, Any]]) -> bool:
        """Cache leaderboard snapshot with 5-minute TTL."""
        try:
            client = self._get_client()
            key = self._key_leaderboard(tenant_id)
            value = json.dumps({
                "data": leaderboard,
                "cached_at": datetime.utcnow().isoformat(),
                "count": len(leaderboard),
            })
            client.setex(key, TTL_LEADERBOARD, value)
            return True
        except RedisError as e:
            logger.warning("Redis set_leaderboard failed for tenant=%s: %s", tenant_id, e)
            return False

    def get_leaderboard(self, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached leaderboard."""
        try:
            client = self._get_client()
            key = self._key_leaderboard(tenant_id)
            value = client.get(key)
            if value:
                cached = json.loads(value)
                return cached.get("data")
            return None
        except RedisError as e:
            logger.warning("Redis get_leaderboard failed for tenant=%s: %s", tenant_id, e)
            return None

    # ── Benchmark Cache ────────────────────────────────────────────────────────

    def set_benchmark(self, tenant_id: str, benchmark: Dict[str, Any]) -> bool:
        """Cache benchmark statistics with 1-hour TTL."""
        try:
            client = self._get_client()
            key = self._key_benchmark(tenant_id)
            client.setex(key, TTL_BENCHMARK, json.dumps(benchmark))
            return True
        except RedisError as e:
            logger.warning("Redis set_benchmark failed: %s", e)
            return False

    def get_benchmark(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached benchmark data."""
        try:
            client = self._get_client()
            key = self._key_benchmark(tenant_id)
            value = client.get(key)
            return json.loads(value) if value else None
        except RedisError as e:
            logger.warning("Redis get_benchmark failed: %s", e)
            return None

    # ── Deduplication ──────────────────────────────────────────────────────────

    def is_recompute_in_progress(self, agent_id: str, tenant_id: str) -> bool:
        """Check if a recompute is already in progress for this agent (dedup)."""
        try:
            client = self._get_client()
            key = self._key_dedup(agent_id, tenant_id)
            return client.exists(key) > 0
        except RedisError:
            return False  # Fail open — allow recompute on Redis error

    def mark_recompute_in_progress(self, agent_id: str, tenant_id: str) -> bool:
        """Mark a recompute as in progress (10-minute TTL)."""
        try:
            client = self._get_client()
            key = self._key_dedup(agent_id, tenant_id)
            # SET NX (only if not exists) — prevents duplicate recomputes
            return client.set(key, "1", ex=TTL_DEDUP, nx=True) is not None
        except RedisError as e:
            logger.warning("Redis mark_recompute failed: %s", e)
            return True  # Fail open

    def clear_recompute_lock(self, agent_id: str, tenant_id: str) -> bool:
        """Clear the recompute lock after completion."""
        try:
            client = self._get_client()
            key = self._key_dedup(agent_id, tenant_id)
            client.delete(key)
            return True
        except RedisError:
            return False

    # ── Health Check ───────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Check Redis Cluster connectivity."""
        try:
            return self._get_client().ping()
        except Exception:
            return False


# ── Singleton ──────────────────────────────────────────────────────────────────
_cache_instance: Optional[ScorecardRedisCache] = None


def get_scorecard_cache() -> ScorecardRedisCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ScorecardRedisCache()
    return _cache_instance
