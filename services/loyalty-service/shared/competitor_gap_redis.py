"""
Shared Redis Cluster caching layer for all 8 competitor-gap services.
Uses redis-py with cluster mode and connection pooling.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from redis.asyncio.cluster import RedisCluster

logger = logging.getLogger(__name__)

REDIS_CLUSTER_NODES = os.getenv("REDIS_CLUSTER_NODES",
                                 "redis-cluster-0:6379,redis-cluster-1:6379,redis-cluster-2:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_TLS = os.getenv("REDIS_TLS", "true").lower() == "true"

_cluster: Optional[RedisCluster] = None


async def get_redis() -> RedisCluster:
    global _cluster
    if _cluster is None:
        nodes = [
            {"host": n.split(":")[0], "port": int(n.split(":")[1])}
            for n in REDIS_CLUSTER_NODES.split(",")
        ]
        _cluster = RedisCluster(
            startup_nodes=nodes,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            ssl=REDIS_TLS,
            decode_responses=True,
            skip_full_coverage_check=True,
            max_connections=50,
        )
    return _cluster


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    try:
        r = await get_redis()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await r.setex(key, ttl_seconds, serialized)
        return True
    except Exception as exc:
        logger.error("[redis] cache_set error key=%s: %s", key, exc)
        return False


async def cache_get(key: str) -> Optional[Any]:
    try:
        r = await get_redis()
        val = await r.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    except Exception as exc:
        logger.error("[redis] cache_get error key=%s: %s", key, exc)
        return None


async def cache_delete(key: str) -> bool:
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except Exception as exc:
        logger.error("[redis] cache_delete error key=%s: %s", key, exc)
        return False


async def cache_increment(key: str, amount: int = 1, ttl_seconds: int = 3600) -> int:
    try:
        r = await get_redis()
        pipe = r.pipeline()
        await pipe.incr(key, amount)
        await pipe.expire(key, ttl_seconds)
        results = await pipe.execute()
        return results[0]
    except Exception as exc:
        logger.error("[redis] cache_increment error key=%s: %s", key, exc)
        return 0


async def cache_list_push(key: str, value: Any, max_length: int = 100) -> bool:
    try:
        r = await get_redis()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        pipe = r.pipeline()
        await pipe.lpush(key, serialized)
        await pipe.ltrim(key, 0, max_length - 1)
        await pipe.execute()
        return True
    except Exception as exc:
        logger.error("[redis] cache_list_push error key=%s: %s", key, exc)
        return False


async def cache_list_get(key: str, start: int = 0, end: int = -1) -> List[Any]:
    try:
        r = await get_redis()
        items = await r.lrange(key, start, end)
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                result.append(item)
        return result
    except Exception as exc:
        logger.error("[redis] cache_list_get error key=%s: %s", key, exc)
        return []


# ─── Service-specific cache helpers ──────────────────────────────────────────

class MultiSimCache:
    PREFIX = "msf"

    @staticmethod
    async def set_connectivity(terminal_id: str, profile: Dict) -> bool:
        return await cache_set(f"{MultiSimCache.PREFIX}:conn:{terminal_id}", profile, 300)

    @staticmethod
    async def get_connectivity(terminal_id: str) -> Optional[Dict]:
        return await cache_get(f"{MultiSimCache.PREFIX}:conn:{terminal_id}")

    @staticmethod
    async def set_failover_count(terminal_id: str, count: int) -> bool:
        return await cache_set(f"{MultiSimCache.PREFIX}:failovers:{terminal_id}", count, 86400)

    @staticmethod
    async def get_failover_count(terminal_id: str) -> int:
        val = await cache_get(f"{MultiSimCache.PREFIX}:failovers:{terminal_id}")
        return int(val) if val is not None else 0

    @staticmethod
    async def increment_failover_count(terminal_id: str) -> int:
        return await cache_increment(f"{MultiSimCache.PREFIX}:failovers:{terminal_id}",
                                     ttl_seconds=86400)


class ReversalCache:
    PREFIX = "rev"

    @staticmethod
    async def set_reversal_status(reversal_id: str, status: Dict) -> bool:
        return await cache_set(f"{ReversalCache.PREFIX}:status:{reversal_id}", status, 3600)

    @staticmethod
    async def get_reversal_status(reversal_id: str) -> Optional[Dict]:
        return await cache_get(f"{ReversalCache.PREFIX}:status:{reversal_id}")

    @staticmethod
    async def set_pending_reversal(transaction_id: str, reversal_id: str) -> bool:
        return await cache_set(f"{ReversalCache.PREFIX}:pending:{transaction_id}",
                               reversal_id, 3600)

    @staticmethod
    async def get_pending_reversal(transaction_id: str) -> Optional[str]:
        return await cache_get(f"{ReversalCache.PREFIX}:pending:{transaction_id}")

    @staticmethod
    async def clear_pending_reversal(transaction_id: str) -> bool:
        return await cache_delete(f"{ReversalCache.PREFIX}:pending:{transaction_id}")


class WalletCache:
    PREFIX = "wal"

    @staticmethod
    async def set_balance(agent_id: str, tenant_id: str, balance: float) -> bool:
        return await cache_set(f"{WalletCache.PREFIX}:bal:{tenant_id}:{agent_id}",
                               {"balance": balance}, 60)

    @staticmethod
    async def get_balance(agent_id: str, tenant_id: str) -> Optional[float]:
        data = await cache_get(f"{WalletCache.PREFIX}:bal:{tenant_id}:{agent_id}")
        return data.get("balance") if data else None

    @staticmethod
    async def invalidate_balance(agent_id: str, tenant_id: str) -> bool:
        return await cache_delete(f"{WalletCache.PREFIX}:bal:{tenant_id}:{agent_id}")

    @staticmethod
    async def set_statement(agent_id: str, period: str, statement: Dict) -> bool:
        return await cache_set(f"{WalletCache.PREFIX}:stmt:{agent_id}:{period}",
                               statement, 3600)

    @staticmethod
    async def get_statement(agent_id: str, period: str) -> Optional[Dict]:
        return await cache_get(f"{WalletCache.PREFIX}:stmt:{agent_id}:{period}")


class CBNReportCache:
    PREFIX = "cbn"

    @staticmethod
    async def set_report(report_id: str, report_data: Dict) -> bool:
        return await cache_set(f"{CBNReportCache.PREFIX}:report:{report_id}",
                               report_data, 86400)

    @staticmethod
    async def get_report(report_id: str) -> Optional[Dict]:
        return await cache_get(f"{CBNReportCache.PREFIX}:report:{report_id}")

    @staticmethod
    async def set_monthly_summary(tenant_id: str, period: str, summary: Dict) -> bool:
        return await cache_set(f"{CBNReportCache.PREFIX}:summary:{tenant_id}:{period}",
                               summary, 3600)

    @staticmethod
    async def get_monthly_summary(tenant_id: str, period: str) -> Optional[Dict]:
        return await cache_get(f"{CBNReportCache.PREFIX}:summary:{tenant_id}:{period}")


class NFCQRCache:
    PREFIX = "qr"

    @staticmethod
    async def set_qr(qr_id: str, qr_data: Dict, ttl: int = 300) -> bool:
        return await cache_set(f"{NFCQRCache.PREFIX}:code:{qr_id}", qr_data, ttl)

    @staticmethod
    async def get_qr(qr_id: str) -> Optional[Dict]:
        return await cache_get(f"{NFCQRCache.PREFIX}:code:{qr_id}")

    @staticmethod
    async def invalidate_qr(qr_id: str) -> bool:
        return await cache_delete(f"{NFCQRCache.PREFIX}:code:{qr_id}")

    @staticmethod
    async def set_agent_qr_list(agent_id: str, qr_ids: List[str]) -> bool:
        return await cache_set(f"{NFCQRCache.PREFIX}:agent:{agent_id}", qr_ids, 300)

    @staticmethod
    async def get_agent_qr_list(agent_id: str) -> Optional[List[str]]:
        return await cache_get(f"{NFCQRCache.PREFIX}:agent:{agent_id}")


class ReceiptCache:
    PREFIX = "rct"

    @staticmethod
    async def set_receipt(receipt_id: str, receipt_data: Dict) -> bool:
        return await cache_set(f"{ReceiptCache.PREFIX}:{receipt_id}", receipt_data, 86400)

    @staticmethod
    async def get_receipt(receipt_id: str) -> Optional[Dict]:
        return await cache_get(f"{ReceiptCache.PREFIX}:{receipt_id}")

    @staticmethod
    async def set_txn_receipt_id(transaction_id: str, receipt_id: str) -> bool:
        return await cache_set(f"{ReceiptCache.PREFIX}:txn:{transaction_id}",
                               receipt_id, 86400)

    @staticmethod
    async def get_txn_receipt_id(transaction_id: str) -> Optional[str]:
        return await cache_get(f"{ReceiptCache.PREFIX}:txn:{transaction_id}")


class TrainingCache:
    PREFIX = "trn"

    @staticmethod
    async def set_course_list(tenant_id: str, courses: List[Dict]) -> bool:
        return await cache_set(f"{TrainingCache.PREFIX}:courses:{tenant_id}", courses, 3600)

    @staticmethod
    async def get_course_list(tenant_id: str) -> Optional[List[Dict]]:
        return await cache_get(f"{TrainingCache.PREFIX}:courses:{tenant_id}")

    @staticmethod
    async def set_agent_progress(agent_id: str, course_id: str, progress: Dict) -> bool:
        return await cache_set(f"{TrainingCache.PREFIX}:progress:{agent_id}:{course_id}",
                               progress, 3600)

    @staticmethod
    async def get_agent_progress(agent_id: str, course_id: str) -> Optional[Dict]:
        return await cache_get(f"{TrainingCache.PREFIX}:progress:{agent_id}:{course_id}")

    @staticmethod
    async def set_compliance_status(agent_id: str, status: Dict) -> bool:
        return await cache_set(f"{TrainingCache.PREFIX}:compliance:{agent_id}", status, 1800)

    @staticmethod
    async def get_compliance_status(agent_id: str) -> Optional[Dict]:
        return await cache_get(f"{TrainingCache.PREFIX}:compliance:{agent_id}")


class LiquidityCache:
    PREFIX = "liq"

    @staticmethod
    async def set_profile(agent_id: str, profile: Dict) -> bool:
        return await cache_set(f"{LiquidityCache.PREFIX}:profile:{agent_id}", profile, 300)

    @staticmethod
    async def get_profile(agent_id: str) -> Optional[Dict]:
        return await cache_get(f"{LiquidityCache.PREFIX}:profile:{agent_id}")

    @staticmethod
    async def set_available_providers(tenant_id: str, providers: List[Dict]) -> bool:
        return await cache_set(f"{LiquidityCache.PREFIX}:providers:{tenant_id}",
                               providers, 120)

    @staticmethod
    async def get_available_providers(tenant_id: str) -> Optional[List[Dict]]:
        return await cache_get(f"{LiquidityCache.PREFIX}:providers:{tenant_id}")

    @staticmethod
    async def invalidate_providers(tenant_id: str) -> bool:
        return await cache_delete(f"{LiquidityCache.PREFIX}:providers:{tenant_id}")

    @staticmethod
    async def set_match(match_id: str, match_data: Dict) -> bool:
        return await cache_set(f"{LiquidityCache.PREFIX}:match:{match_id}", match_data, 3600)

    @staticmethod
    async def get_match(match_id: str) -> Optional[Dict]:
        return await cache_get(f"{LiquidityCache.PREFIX}:match:{match_id}")
