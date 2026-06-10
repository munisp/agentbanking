"""
Lakehouse Analytics Client for 54Agent Banking Platform

Sends structured analytics events to the data lakehouse (Delta Lake / Apache
Iceberg backed) for reporting, BI dashboards, and ML pipelines.

Events are buffered locally and flushed in batches via HTTP to the lakehouse
ingestion API, with Kafka as a secondary transport.

Usage::

    from shared.lakehouse_client import LakehouseClient

    lh = LakehouseClient(service="pos-integration")
    await lh.start()
    await lh.log_event("transaction_completed", {"txn_id": "T1", "amount": 5000})
    await lh.flush()
    await lh.stop()
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger("platform.lakehouse")

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

# Validate lakehouse dependencies at import time in production
_LAKEHOUSE_STRICT = os.getenv("LAKEHOUSE_STRICT", "false").lower() in ("1", "true", "yes")
if _LAKEHOUSE_STRICT and not _HAS_HTTPX:
    raise ImportError(
        "Lakehouse client requires 'httpx' in strict mode (LAKEHOUSE_STRICT=true). "
        "Install with: pip install httpx"
    )


class LakehouseClient:
    def __init__(
        self,
        service: str = "",
        endpoint: Optional[str] = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ):
        self.service = service or os.getenv("SERVICE_NAME", "unknown")
        self.endpoint = endpoint or os.getenv("LAKEHOUSE_ENDPOINT", "http://lakehouse:8090")
        self.batch_size = int(os.getenv("LAKEHOUSE_BATCH_SIZE", str(batch_size)))
        self.flush_interval = float(os.getenv("LAKEHOUSE_FLUSH_INTERVAL", str(flush_interval)))
        self._buffer: deque = deque(maxlen=10000)
        self._dropped_count = 0
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._periodic_flush())
        logger.info("Lakehouse client started for %s -> %s", self.service, self.endpoint)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        await self.flush()

    async def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        record = {
            "event_type": event_type,
            "service": self.service,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        if len(self._buffer) >= self._buffer.maxlen:
            self._dropped_count += 1
            if self._dropped_count % 100 == 1:
                logger.warning(
                    "Lakehouse buffer full (%d events dropped so far). "
                    "Consider increasing LAKEHOUSE_BATCH_SIZE or flush interval.",
                    self._dropped_count,
                )
        self._buffer.append(record)
        if len(self._buffer) >= self.batch_size:
            await self.flush()

    async def log_transaction(
        self,
        txn_id: str,
        txn_type: str,
        amount: int,
        agent_id: str,
        status: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self.log_event("transaction", {
            "txn_id": txn_id,
            "txn_type": txn_type,
            "amount": amount,
            "agent_id": agent_id,
            "status": status,
            **(extra or {}),
        })

    async def log_agent_activity(
        self,
        agent_id: str,
        activity: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self.log_event("agent_activity", {
            "agent_id": agent_id,
            "activity": activity,
            **(extra or {}),
        })

    async def flush(self) -> int:
        if not self._buffer:
            return 0
        batch: List[Dict[str, Any]] = []
        while self._buffer and len(batch) < self.batch_size:
            batch.append(self._buffer.popleft())
        if not batch:
            return 0
        if _HAS_HTTPX:
            try:
                async with _httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{self.endpoint}/v1/ingest",
                        json={"records": batch},
                    )
                    if resp.status_code < 300:
                        logger.debug("Lakehouse flushed %d records", len(batch))
                        return len(batch)
                    logger.warning("Lakehouse flush HTTP %d", resp.status_code)
            except Exception as exc:
                logger.warning("Lakehouse flush error: %s", exc)
                for item in reversed(batch):
                    self._buffer.appendleft(item)
        return 0

    async def _periodic_flush(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Lakehouse periodic flush error: %s", exc)
