"""
Unified Event Bus for 54Agent Banking Platform

Abstracts over Kafka (primary), Dapr pub/sub, and Fluvio streaming so that
services emit domain events through one interface.

Usage::

    from shared.event_bus import EventBus

    bus = EventBus(service="pos-integration")
    await bus.start()
    await bus.publish("transactions.created", {"txn_id": "T1", "amount": 5000})
    await bus.stop()
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timezone

logger = logging.getLogger("platform.event_bus")

try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    _HAS_KAFKA = True
except ImportError:
    _HAS_KAFKA = False

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class EventBus:
    def __init__(
        self,
        service: str = "",
        kafka_servers: Optional[str] = None,
        dapr_port: Optional[int] = None,
        fluvio_endpoint: Optional[str] = None,
    ):
        self.service = service or os.getenv("SERVICE_NAME", "unknown")
        self.kafka_servers = kafka_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-1:9092,kafka-2:9093,kafka-3:9094")
        self.dapr_port = dapr_port or int(os.getenv("DAPR_HTTP_PORT", "3500"))
        self.fluvio_endpoint = fluvio_endpoint or os.getenv("FLUVIO_ENDPOINT", "http://fluvio:9003")
        self._kafka_producer: Optional[Any] = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        if _HAS_KAFKA:
            try:
                self._kafka_producer = AIOKafkaProducer(
                    bootstrap_servers=self.kafka_servers.split(","),
                    client_id=f"{self.service}-producer",
                    compression_type="snappy",
                    acks="all",
                    value_serializer=lambda v: json.dumps(v).encode(),
                    key_serializer=lambda k: k.encode() if k else None,
                )
                await self._kafka_producer.start()
                logger.info("EventBus Kafka producer started for %s", self.service)
            except Exception as exc:
                logger.warning("Kafka unavailable, falling back to Dapr/Fluvio: %s", exc)
                self._kafka_producer = None
        self._started = True

    async def stop(self) -> None:
        if self._kafka_producer:
            await self._kafka_producer.stop()
            self._kafka_producer = None
        self._started = False

    async def publish(self, topic: str, data: Dict[str, Any], key: Optional[str] = None) -> bool:
        envelope = {
            **data,
            "_event_meta": {
                "topic": topic,
                "source": self.service,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
            },
        }
        if self._kafka_producer:
            try:
                await self._kafka_producer.send_and_wait(topic, envelope, key=key)
                return True
            except Exception as exc:
                logger.warning("Kafka publish failed, trying Dapr: %s", exc)

        if _HAS_HTTPX:
            try:
                async with _httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"http://localhost:{self.dapr_port}/v1.0/publish/pubsub/{topic}",
                        json=envelope,
                    )
                    if resp.status_code < 300:
                        return True
            except Exception as exc:
                logger.warning("Dapr publish failed, trying Fluvio: %s", exc)

            try:
                async with _httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{self.fluvio_endpoint}/produce",
                        json={"topic": topic, "value": json.dumps(envelope)},
                    )
                    if resp.status_code < 300:
                        return True
            except Exception as exc:
                logger.error("All event transports failed for topic=%s: %s", topic, exc)

        return False

    async def publish_batch(self, topic: str, events: List[Dict[str, Any]]) -> int:
        ok = 0
        for ev in events:
            if await self.publish(topic, ev):
                ok += 1
        return ok
