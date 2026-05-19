"""
54Link MDM Geofence Cross-Wiring Service
=========================================
Consumes MDM device heartbeat events from Kafka, validates device locations
against registered geofence zones stored in PostgreSQL, and publishes
geofence violation events back to Kafka for the MDM server to process.

Architecture:
  Kafka (mdm.device.heartbeats) → GeofenceValidator → PostgreSQL (geofence_zones)
                                                     → Kafka (mdm.geofence.violations)
                                                     → Kafka (mdm.compliance.alerts)

Default configuration (all overridable via environment variables):
  KAFKA_BROKERS       = localhost:9092
  POSTGRES_URL        = postgresql://54link:54link@localhost:5432/54link_pos
  HTTP_PORT           = 8096
  HEARTBEAT_TOPIC     = mdm.device.heartbeats
  VIOLATION_TOPIC     = mdm.geofence.violations
  ALERT_TOPIC         = mdm.compliance.alerts
  CONSUMER_GROUP_ID   = mdm-geofence-service
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("geofence-service")

# ── Configuration ─────────────────────────────────────────────────────────────

KAFKA_BROKERS       = os.getenv("KAFKA_BROKERS", "localhost:9092")
POSTGRES_URL        = os.getenv("POSTGRES_URL", "postgresql://54link:54link@localhost:5432/54link_pos")
HTTP_PORT           = int(os.getenv("HTTP_PORT", "8096"))
HEARTBEAT_TOPIC     = os.getenv("HEARTBEAT_TOPIC", "mdm.device.heartbeats")
VIOLATION_TOPIC     = os.getenv("VIOLATION_TOPIC", "mdm.geofence.violations")
ALERT_TOPIC         = os.getenv("ALERT_TOPIC", "mdm.compliance.alerts")
CONSUMER_GROUP_ID   = os.getenv("CONSUMER_GROUP_ID", "mdm-geofence-service")

# ── Domain models ─────────────────────────────────────────────────────────────

@dataclass
class GeofenceZone:
    id: str
    name: str
    center_lat: float   # WGS-84 decimal degrees
    center_lng: float
    radius_m: float     # Radius in metres
    active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class DeviceLocation:
    device_id: str
    serial_number: str
    agent_code: str
    lat: float          # WGS-84 decimal degrees
    lng: float
    accuracy_m: float
    timestamp: datetime


@dataclass
class GeofenceViolation:
    id: str
    device_id: str
    serial_number: str
    zone_id: str
    zone_name: str
    device_lat: float
    device_lng: float
    center_lat: float
    center_lng: float
    radius_m: float
    distance_m: float
    overshoot_m: float  # How far outside the zone
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False


# ── Haversine distance ────────────────────────────────────────────────────────

def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in metres between two WGS-84 coordinates."""
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Geofence validator ────────────────────────────────────────────────────────

class GeofenceValidator:
    """Validates device locations against registered geofence zones."""

    def __init__(self, db_pool: asyncpg.Pool):
        self._pool = db_pool
        self._zones: list[GeofenceZone] = []
        self._last_refresh: float = 0.0
        self._refresh_interval_s: float = 60.0

    async def refresh_zones(self) -> None:
        """Reload geofence zones from PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, name, center_lat, center_lng, radius_m, active, created_at
                    FROM geofence_zones
                    WHERE active = true
                    ORDER BY created_at ASC
                """)
            self._zones = [
                GeofenceZone(
                    id=str(row["id"]),
                    name=row["name"],
                    center_lat=float(row["center_lat"]),
                    center_lng=float(row["center_lng"]),
                    radius_m=float(row["radius_m"]),
                    active=row["active"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
            self._last_refresh = time.monotonic()
            log.info("Loaded %d geofence zones from DB", len(self._zones))
        except Exception as exc:
            log.warning("Failed to refresh geofence zones: %s", exc)

    async def ensure_fresh(self) -> None:
        """Refresh zones if the cache is stale."""
        if time.monotonic() - self._last_refresh > self._refresh_interval_s:
            await self.refresh_zones()

    async def validate(self, location: DeviceLocation) -> list[GeofenceViolation]:
        """
        Check a device location against all active geofence zones.
        Returns a list of violations (empty if compliant).
        """
        await self.ensure_fresh()

        # Skip devices with no valid location fix (0,0 is in the Gulf of Guinea)
        if location.lat == 0.0 and location.lng == 0.0:
            return []

        violations: list[GeofenceViolation] = []

        for zone in self._zones:
            dist = haversine_meters(
                location.lat, location.lng,
                zone.center_lat, zone.center_lng,
            )
            if dist > zone.radius_m:
                overshoot = dist - zone.radius_m
                violation = GeofenceViolation(
                    id=f"{location.device_id}-{zone.id}-{int(time.time())}",
                    device_id=location.device_id,
                    serial_number=location.serial_number,
                    zone_id=zone.id,
                    zone_name=zone.name,
                    device_lat=location.lat,
                    device_lng=location.lng,
                    center_lat=zone.center_lat,
                    center_lng=zone.center_lng,
                    radius_m=zone.radius_m,
                    distance_m=round(dist, 1),
                    overshoot_m=round(overshoot, 1),
                )
                violations.append(violation)
                log.warning(
                    "Geofence violation: device=%s zone=%s dist=%.0fm overshoot=%.0fm",
                    location.device_id, zone.name, dist, overshoot,
                )

        return violations


# ── Kafka publisher (with fallback logging) ───────────────────────────────────

class KafkaPublisher:
    """Publishes messages to Kafka topics with a log fallback when unavailable."""

    def __init__(self, brokers: str):
        self._brokers = brokers
        self._producer = None
        self._try_connect()

    def _try_connect(self) -> None:
        try:
            from confluent_kafka import Producer  # type: ignore
            self._producer = Producer({"bootstrap.servers": self._brokers})
            log.info("Kafka producer connected to %s", self._brokers)
        except Exception as exc:
            log.warning("Kafka unavailable (%s) — using log fallback", exc)

    def publish(self, topic: str, key: str, value: dict) -> None:
        payload = json.dumps(value, default=str).encode()
        if self._producer:
            try:
                self._producer.produce(topic, key=key.encode(), value=payload)
                self._producer.poll(0)
                return
            except Exception as exc:
                log.warning("Kafka publish failed: %s — logging instead", exc)
        # Log fallback
        log.info("[KAFKA→%s] key=%s payload=%s", topic, key, value)


# ── Heartbeat processor ───────────────────────────────────────────────────────

class HeartbeatProcessor:
    """Processes MDM heartbeat events and checks geofence compliance."""

    def __init__(self, validator: GeofenceValidator, publisher: KafkaPublisher):
        self._validator = validator
        self._publisher = publisher

    async def process(self, raw: dict) -> list[GeofenceViolation]:
        """Process a single heartbeat dict and return any geofence violations."""
        # Extract location — heartbeat may send lat/lon as float or as latE6/lonE6 integers
        lat: Optional[float] = None
        lng: Optional[float] = None

        if "lat" in raw and "lng" in raw:
            lat = float(raw["lat"])
            lng = float(raw["lng"])
        elif "latE6" in raw and "lonE6" in raw:
            lat = int(raw["latE6"]) / 1e6
            lng = int(raw["lonE6"]) / 1e6

        if lat is None or lng is None or (lat == 0.0 and lng == 0.0):
            return []  # No location data — skip geofence check

        location = DeviceLocation(
            device_id=raw.get("deviceId", ""),
            serial_number=raw.get("serialNumber", ""),
            agent_code=raw.get("agentCode", ""),
            lat=lat,
            lng=lng,
            accuracy_m=float(raw.get("locationAccuracyM", 0)),
            timestamp=datetime.fromisoformat(raw["timestamp"])
            if "timestamp" in raw
            else datetime.now(timezone.utc),
        )

        violations = await self._validator.validate(location)

        for v in violations:
            v_dict = asdict(v)
            # Publish violation event
            self._publisher.publish(VIOLATION_TOPIC, v.device_id, v_dict)
            # Publish compliance alert
            self._publisher.publish(ALERT_TOPIC, v.device_id, {
                "type": "GEOFENCE_VIOLATION",
                "deviceId": v.device_id,
                "serialNumber": v.serial_number,
                "zoneName": v.zone_name,
                "distanceM": v.distance_m,
                "overshootM": v.overshoot_m,
                "detectedAt": v.detected_at.isoformat(),
            })

        return violations


# ── Kafka consumer loop ───────────────────────────────────────────────────────

async def run_kafka_consumer(processor: HeartbeatProcessor) -> None:
    """Consume heartbeat events from Kafka and process them."""
    try:
        from confluent_kafka import Consumer, KafkaError  # type: ignore
        consumer = Consumer({
            "bootstrap.servers": KAFKA_BROKERS,
            "group.id": CONSUMER_GROUP_ID,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        })
        consumer.subscribe([HEARTBEAT_TOPIC])
        log.info("Kafka consumer subscribed to %s", HEARTBEAT_TOPIC)

        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                await asyncio.sleep(0.1)
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log.error("Kafka error: %s", msg.error())
                continue
            try:
                data = json.loads(msg.value().decode())
                await processor.process(data)
            except Exception as exc:
                log.error("Failed to process heartbeat: %s", exc)

    except ImportError:
        log.warning("confluent_kafka not installed — Kafka consumer disabled")
        # Keep running for HTTP API
        while True:
            await asyncio.sleep(60)
    except Exception as exc:
        log.error("Kafka consumer error: %s", exc)


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(title="54Link MDM Geofence Service", version="1.0.0")

# Global instances (populated on startup)
_validator: Optional[GeofenceValidator] = None
_processor: Optional[HeartbeatProcessor] = None
_publisher: Optional[KafkaPublisher] = None


@app.on_event("startup")
async def startup() -> None:
    global _validator, _processor, _publisher

    # Connect to PostgreSQL
    try:
        pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)
        log.info("PostgreSQL pool connected")
    except Exception as exc:
        log.warning("PostgreSQL unavailable (%s) — geofence validation disabled", exc)
        pool = None

    _publisher = KafkaPublisher(KAFKA_BROKERS)
    _validator = GeofenceValidator(pool) if pool else None
    if _validator:
        await _validator.refresh_zones()
    _processor = HeartbeatProcessor(_validator, _publisher) if _validator else None

    # Start Kafka consumer in background
    if _processor:
        asyncio.create_task(run_kafka_consumer(_processor))


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mdm-geofence-service"})


@app.get("/zones")
async def list_zones() -> JSONResponse:
    if not _validator:
        raise HTTPException(503, "Database not available")
    await _validator.ensure_fresh()
    return JSONResponse([
        {
            "id": z.id,
            "name": z.name,
            "centerLat": z.center_lat,
            "centerLng": z.center_lng,
            "radiusM": z.radius_m,
            "active": z.active,
        }
        for z in _validator._zones
    ])


@app.post("/validate")
async def validate_location(body: dict) -> JSONResponse:
    """On-demand geofence validation for a device location payload."""
    if not _processor:
        raise HTTPException(503, "Service not ready")
    violations = await _processor.process(body)
    return JSONResponse({
        "violations": [asdict(v) for v in violations],
        "compliant": len(violations) == 0,
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("geofence_service:app", host="0.0.0.0", port=HTTP_PORT, reload=False)
