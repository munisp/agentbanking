"""
POS Shell Configuration Service
Persists and manages tile layout configurations per agent and device.

Responsibilities:
  - Store pinned tile IDs and order per (agent_id, device_id) pair
  - Track usage counts per tile per agent
  - Compute and return top-used tile suggestions
  - Broadcast layout changes via Kafka so other devices sync immediately
  - Support bulk reset to defaults
  - Admin endpoint to push a layout to all devices of an agent
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

# Redis key patterns
LAYOUT_KEY = "pos_shell:layout:{agent_id}:{device_id}"
USAGE_KEY = "pos_shell:usage:{agent_id}"
DEVICES_KEY = "pos_shell:devices:{agent_id}"
GLOBAL_USAGE_KEY = "pos_shell:global_usage"

# Default pinned tile IDs (matches TileRegistry.ts DEFAULT_PINNED_TILES)
DEFAULT_PINNED_IDS = [
    "cash_in", "cash_out", "transfer", "pos_payment", "qr_payment",
    "airtime", "bill_payment", "transactions_history", "new_customer",
    "customer_lookup", "wallet_balance", "float_request", "notifications",
]

TOP_USED_COUNT = 4


class POSShellConfigService:
    def __init__(self, redis_client: redis.Redis, kafka_producer: Optional[AIOKafkaProducer] = None):
        self.redis = redis_client
        self.kafka = kafka_producer

    # ── Layout CRUD ────────────────────────────────────────────────────────────

    async def get_layout(self, agent_id: str, device_id: str) -> Dict[str, Any]:
        """Return the saved layout for an agent/device pair."""
        key = LAYOUT_KEY.format(agent_id=agent_id, device_id=device_id)
        raw = await self.redis.get(key)
        if raw:
            layout = json.loads(raw)
        else:
            # Return defaults on first call
            layout = {
                "pinned_tile_ids": DEFAULT_PINNED_IDS,
                "usage_counts": {},
                "last_updated": None,
                "is_default": True,
            }

        # Merge in server-side usage counts
        usage = await self.get_usage(agent_id)
        layout["usage_counts"] = usage
        layout["top_used_ids"] = self._compute_top_used(
            usage, layout["pinned_tile_ids"]
        )

        # Register this device
        await self.redis.sadd(DEVICES_KEY.format(agent_id=agent_id), device_id)

        return layout

    async def save_layout(
        self,
        agent_id: str,
        device_id: str,
        pinned_tile_ids: List[str],
        usage_counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Save a tile layout for an agent/device pair."""
        # Validate tile IDs (only allow known tile IDs)
        valid_ids = [tid for tid in pinned_tile_ids if self._is_valid_tile_id(tid)]
        if len(valid_ids) > 12:
            valid_ids = valid_ids[:12]

        layout = {
            "pinned_tile_ids": valid_ids,
            "last_updated": datetime.utcnow().isoformat(),
            "is_default": False,
        }

        key = LAYOUT_KEY.format(agent_id=agent_id, device_id=device_id)
        await self.redis.setex(key, 86400 * 90, json.dumps(layout))  # 90-day TTL

        # Merge usage counts
        if usage_counts:
            await self.merge_usage(agent_id, usage_counts)

        # Register device
        await self.redis.sadd(DEVICES_KEY.format(agent_id=agent_id), device_id)

        # Broadcast change to other devices via Kafka
        if self.kafka:
            await self._broadcast_layout_change(agent_id, device_id, valid_ids)

        logger.info(f"Layout saved for agent={agent_id} device={device_id} tiles={len(valid_ids)}")
        return {**layout, "agent_id": agent_id, "device_id": device_id}

    async def reset_layout(self, agent_id: str, device_id: str) -> Dict[str, Any]:
        """Reset layout to platform defaults."""
        key = LAYOUT_KEY.format(agent_id=agent_id, device_id=device_id)
        await self.redis.delete(key)
        if self.kafka:
            await self._broadcast_layout_change(agent_id, device_id, DEFAULT_PINNED_IDS)
        return {
            "pinned_tile_ids": DEFAULT_PINNED_IDS,
            "is_default": True,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def push_layout_to_all_devices(
        self, agent_id: str, pinned_tile_ids: List[str]
    ) -> Dict[str, Any]:
        """Admin: push a layout to all registered devices of an agent."""
        devices_key = DEVICES_KEY.format(agent_id=agent_id)
        device_ids = await self.redis.smembers(devices_key)
        updated = []
        for device_id_bytes in device_ids:
            device_id = device_id_bytes.decode()
            await self.save_layout(agent_id, device_id, pinned_tile_ids)
            updated.append(device_id)
        return {"agent_id": agent_id, "devices_updated": updated, "tile_count": len(pinned_tile_ids)}

    # ── Usage tracking ─────────────────────────────────────────────────────────

    async def record_usage(self, agent_id: str, tile_id: str, count: int = 1) -> None:
        """Increment usage count for a tile."""
        if not self._is_valid_tile_id(tile_id):
            return
        usage_key = USAGE_KEY.format(agent_id=agent_id)
        await self.redis.hincrby(usage_key, tile_id, count)
        await self.redis.expire(usage_key, 86400 * 365)  # 1-year TTL
        # Also track global usage
        await self.redis.zincrby(GLOBAL_USAGE_KEY, count, tile_id)

    async def merge_usage(self, agent_id: str, usage_counts: Dict[str, int]) -> None:
        """Merge a batch of usage counts from client."""
        usage_key = USAGE_KEY.format(agent_id=agent_id)
        pipe = self.redis.pipeline()
        for tile_id, count in usage_counts.items():
            if self._is_valid_tile_id(tile_id) and count > 0:
                pipe.hincrby(usage_key, tile_id, count)
                pipe.zincrby(GLOBAL_USAGE_KEY, count, tile_id)
        pipe.expire(usage_key, 86400 * 365)
        await pipe.execute()

    async def get_usage(self, agent_id: str) -> Dict[str, int]:
        """Return all usage counts for an agent."""
        usage_key = USAGE_KEY.format(agent_id=agent_id)
        raw = await self.redis.hgetall(usage_key)
        return {k.decode(): int(v) for k, v in raw.items()}

    async def get_global_top_tiles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most-used tiles across all agents (admin analytics)."""
        results = await self.redis.zrevrange(GLOBAL_USAGE_KEY, 0, limit - 1, withscores=True)
        return [
            {"tile_id": tile_id.decode(), "total_taps": int(score)}
            for tile_id, score in results
        ]

    # ── Device registry ────────────────────────────────────────────────────────

    async def get_agent_devices(self, agent_id: str) -> List[str]:
        """Return all device IDs registered for an agent."""
        devices_key = DEVICES_KEY.format(agent_id=agent_id)
        raw = await self.redis.smembers(devices_key)
        return [d.decode() for d in raw]

    async def deregister_device(self, agent_id: str, device_id: str) -> None:
        """Remove a device from an agent's device registry."""
        devices_key = DEVICES_KEY.format(agent_id=agent_id)
        layout_key = LAYOUT_KEY.format(agent_id=agent_id, device_id=device_id)
        await self.redis.srem(devices_key, device_id)
        await self.redis.delete(layout_key)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _compute_top_used(
        self, usage: Dict[str, int], pinned_ids: List[str]
    ) -> List[str]:
        """Return top-used tile IDs not already pinned."""
        unpinned_usage = {
            tid: count
            for tid, count in usage.items()
            if tid not in pinned_ids and count > 0
        }
        sorted_tiles = sorted(unpinned_usage.items(), key=lambda x: x[1], reverse=True)
        return [tid for tid, _ in sorted_tiles[:TOP_USED_COUNT]]

    def _is_valid_tile_id(self, tile_id: str) -> bool:
        """Validate tile ID against the known registry."""
        KNOWN_TILE_IDS = {
            "cash_in", "cash_out", "transfer", "pos_payment", "qr_payment",
            "airtime", "data_bundle", "bill_payment", "ussd", "transactions_history",
            "new_customer", "customer_lookup", "kyc", "wallet_balance",
            "float_request", "commission", "scorecard", "erp_accounting",
            "inventory", "add_product_photo", "storefront", "messages",
            "notifications", "cbn_reports", "vat", "geofencing", "reports",
            "receipt_history", "profile", "settings", "training", "offline_mode",
        }
        return tile_id in KNOWN_TILE_IDS

    async def _broadcast_layout_change(
        self, agent_id: str, source_device_id: str, pinned_tile_ids: List[str]
    ) -> None:
        """Publish layout change event to Kafka for real-time sync."""
        if not self.kafka:
            return
        try:
            event = {
                "event": "pos_shell.layout_changed",
                "agent_id": agent_id,
                "source_device_id": source_device_id,
                "pinned_tile_ids": pinned_tile_ids,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.kafka.send_and_wait(
                "pos-shell-events",
                value=json.dumps(event).encode(),
                key=agent_id.encode(),
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast layout change: {e}")
