"""
Tests for the 54agent MDM Geofence Cross-Wiring Service.
Run with: python -m pytest test_geofence_service.py -v
"""

import asyncio
import math
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geofence_service import (
    GeofenceZone,
    GeofenceValidator,
    DeviceLocation,
    HeartbeatProcessor,
    KafkaPublisher,
    haversine_meters,
)


# ── Haversine tests ───────────────────────────────────────────────────────────

def test_haversine_same_point():
    """Distance from a point to itself should be zero."""
    assert haversine_meters(6.463, 3.396, 6.463, 3.396) == pytest.approx(0.0, abs=0.1)


def test_haversine_known_distance():
    """Lagos Island to Victoria Island is approximately 4.5 km."""
    dist = haversine_meters(6.4541, 3.3947, 6.4281, 3.4219)
    assert 3_500 < dist < 5_500, f"Expected ~4500m, got {dist:.0f}m"


def test_haversine_1km_north():
    """Moving 0.009 degrees north from Lagos Island should be ~1km."""
    dist = haversine_meters(6.463, 3.396, 6.472, 3.396)
    assert 900 < dist < 1100, f"Expected ~1000m, got {dist:.0f}m"


# ── GeofenceValidator tests ───────────────────────────────────────────────────

class MockPool:
    """Mock asyncpg pool that returns pre-configured zone rows."""

    def __init__(self, zones: list[dict]):
        self._zones = zones

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def fetch(self, query: str) -> list[dict]:
        return self._zones


def make_zone(id: str, name: str, lat: float, lng: float, radius_m: float) -> dict:
    return {
        "id": id, "name": name,
        "center_lat": lat, "center_lng": lng,
        "radius_m": radius_m, "active": True,
        "created_at": datetime.now(timezone.utc),
    }


def make_location(lat: float, lng: float, device_id: str = "dev-001") -> DeviceLocation:
    return DeviceLocation(
        device_id=device_id,
        serial_number="SN-001",
        agent_code="AGT001",
        lat=lat,
        lng=lng,
        accuracy_m=5.0,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_validator_no_violations_within_zone():
    """Device inside the geofence should produce no violations."""
    pool = MockPool([make_zone("z1", "Lagos HQ", 6.463, 3.396, 1000)])
    validator = GeofenceValidator(pool)
    await validator.refresh_zones()
    # Device at exactly the center
    loc = make_location(6.463, 3.396)
    violations = await validator.validate(loc)
    assert violations == []


@pytest.mark.asyncio
async def test_validator_violation_outside_zone():
    """Device 5km outside the zone should produce a violation."""
    pool = MockPool([make_zone("z1", "Lagos HQ", 6.463, 3.396, 500)])
    validator = GeofenceValidator(pool)
    await validator.refresh_zones()
    # Device ~5km north
    loc = make_location(6.508, 3.396)
    violations = await validator.validate(loc)
    assert len(violations) == 1
    assert violations[0].zone_id == "z1"
    assert violations[0].overshoot_m > 0


@pytest.mark.asyncio
async def test_validator_multiple_zones():
    """Device should be checked against all active zones."""
    pool = MockPool([
        make_zone("z1", "Zone A", 6.463, 3.396, 500),
        make_zone("z2", "Zone B", 6.600, 3.500, 500),
    ])
    validator = GeofenceValidator(pool)
    await validator.refresh_zones()
    # Device far from both zones
    loc = make_location(6.800, 3.700)
    violations = await validator.validate(loc)
    assert len(violations) == 2


@pytest.mark.asyncio
async def test_validator_no_location_skipped():
    """Heartbeat with zero lat/lon should be skipped."""
    pool = MockPool([make_zone("z1", "Lagos HQ", 6.463, 3.396, 500)])
    validator = GeofenceValidator(pool)
    await validator.refresh_zones()
    loc = make_location(0.0, 0.0)
    violations = await validator.validate(loc)
    assert violations == []


# ── HeartbeatProcessor tests ─────────────────────────────────────────────────

class MockValidator:
    def __init__(self, violations):
        self._violations = violations

    async def ensure_fresh(self):
        pass

    async def validate(self, location):
        return self._violations


class MockPublisher:
    def __init__(self):
        self.published = []

    def publish(self, topic, key, value):
        self.published.append({"topic": topic, "key": key, "value": value})


@pytest.mark.asyncio
async def test_processor_publishes_violations():
    """Processor should publish to both violation and alert topics."""
    from geofence_service import GeofenceViolation
    v = GeofenceViolation(
        id="v-001", device_id="dev-001", serial_number="SN-001",
        zone_id="z1", zone_name="Lagos HQ",
        device_lat=6.508, device_lng=3.396,
        center_lat=6.463, center_lng=3.396,
        radius_m=500, distance_m=5000, overshoot_m=4500,
    )
    validator = MockValidator([v])
    publisher = MockPublisher()
    processor = HeartbeatProcessor(validator, publisher)

    heartbeat = {
        "deviceId": "dev-001", "serialNumber": "SN-001", "agentCode": "AGT001",
        "lat": 6.508, "lng": 3.396,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    violations = await processor.process(heartbeat)
    assert len(violations) == 1
    topics = {m["topic"] for m in publisher.published}
    assert "mdm.geofence.violations" in topics
    assert "mdm.compliance.alerts" in topics


@pytest.mark.asyncio
async def test_processor_handles_late6_lon6_format():
    """Processor should accept latE6/lonE6 integer format from FreeRTOS devices."""
    validator = MockValidator([])
    publisher = MockPublisher()
    processor = HeartbeatProcessor(validator, publisher)

    heartbeat = {
        "deviceId": "dev-freertos-001",
        "latE6": 6463000,
        "lonE6": 3396000,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    violations = await processor.process(heartbeat)
    assert violations == []


@pytest.mark.asyncio
async def test_processor_skips_missing_location():
    """Processor should skip heartbeats with no location data."""
    validator = MockValidator([])
    publisher = MockPublisher()
    processor = HeartbeatProcessor(validator, publisher)

    heartbeat = {"deviceId": "dev-001", "serialNumber": "SN-001"}
    violations = await processor.process(heartbeat)
    assert violations == []
    assert publisher.published == []
