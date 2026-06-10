"""
Fluvio Streaming Client for 54Agent Banking Platform

Provides real-time event streaming via Fluvio for high-throughput,
low-latency data pipelines (POS transactions, telemetry, audit logs).

Usage::

    from shared.fluvio_streaming import FluvioClient

    fc = FluvioClient()
    await fc.produce("pos-transactions", {"txn_id": "T1", "amount": 5000})
    records = await fc.consume("pos-transactions", offset=0, count=10)
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("platform.fluvio")

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class FluvioClient:
    def __init__(
        self,
        endpoint: Optional[str] = None,
    ):
        self.endpoint = endpoint or os.getenv("FLUVIO_ENDPOINT", "http://fluvio:9003")

    async def produce(self, topic: str, data: Dict[str, Any], key: Optional[str] = None) -> bool:
        if not _HAS_HTTPX:
            return False
        payload: Dict[str, Any] = {"topic": topic, "value": json.dumps(data)}
        if key:
            payload["key"] = key
        try:
            async with _httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(f"{self.endpoint}/produce", json=payload)
                return resp.status_code < 300
        except Exception as exc:
            logger.warning("Fluvio produce error: %s", exc)
            return False

    async def produce_batch(self, topic: str, records: List[Dict[str, Any]]) -> int:
        ok = 0
        for rec in records:
            if await self.produce(topic, rec):
                ok += 1
        return ok

    async def consume(
        self,
        topic: str,
        offset: int = 0,
        count: int = 100,
        partition: int = 0,
    ) -> List[Dict[str, Any]]:
        if not _HAS_HTTPX:
            return []
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.endpoint}/consume",
                    params={"topic": topic, "offset": offset, "count": count, "partition": partition},
                )
                if resp.status_code < 300:
                    data = resp.json()
                    records = data if isinstance(data, list) else data.get("records", [])
                    result = []
                    for r in records:
                        if isinstance(r, dict):
                            result.append(r)
                        elif isinstance(r, str):
                            try:
                                result.append(json.loads(r))
                            except (json.JSONDecodeError, TypeError):
                                result.append({"raw": r})
                    return result
        except Exception as exc:
            logger.warning("Fluvio consume error: %s", exc)
        return []

    async def create_topic(self, topic: str, partitions: int = 1, replicas: int = 1) -> bool:
        if not _HAS_HTTPX:
            return False
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.endpoint}/topics",
                    json={"name": topic, "partitions": partitions, "replicas": replicas},
                )
                return resp.status_code < 300
        except Exception as exc:
            logger.warning("Fluvio create_topic error: %s", exc)
            return False
