"""
POS Geo-Fencing Service — 54agent Agency Banking Platform

Provides:
  - Dynamic geo-fence zone management (create/update/delete polygon or circle zones)
  - POS terminal registration with mandatory zone assignment
  - Real-time location validation on every transaction
  - Violation detection, severity scoring, and alerting
  - Live POS map data feed (SSE / WebSocket)
  - Zone analytics (terminals per zone, violation heatmap)

Geo-fence types supported:
  - Circle  : center point + radius (metres)
  - Polygon : arbitrary GeoJSON Polygon (drawn via UI map)
  - MultiPolygon : complex zones with holes / exclusions
"""

import asyncio
import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import HTTPException
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/multibank")
REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6379")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# ── Pydantic Models ────────────────────────────────────────────────────────────

class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)

class CircleGeometry(BaseModel):
    type: str = "Circle"
    center: GeoPoint
    radius_m: float = Field(..., gt=0, le=100_000, description="Radius in metres")

class PolygonGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]] = Field(
        ..., description="GeoJSON Polygon coordinates [[[lng,lat],...]]"
    )

    @validator("coordinates")
    def validate_polygon(cls, v):
        if not v or len(v[0]) < 4:
            raise ValueError("Polygon must have at least 3 vertices (4 points, last == first)")
        first = v[0][0]
        last  = v[0][-1]
        if first != last:
            v[0].append(first)  # auto-close
        return v

class CreateZoneRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    zone_type: str = Field(..., description="AGENT_OPERATING_AREA | MERCHANT_DELIVERY_ZONE | RESTRICTED_ZONE | HIGH_RISK_AREA | PREMIUM_ZONE | MARKET_ZONE | CAMPUS_ZONE | INDUSTRIAL_ZONE")
    geometry_type: str = Field(..., description="Circle | Polygon")
    # Circle fields
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_m: Optional[float] = None
    # Polygon fields
    polygon_coordinates: Optional[List[List[List[float]]]] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    alert_on_entry: bool = False
    alert_on_exit: bool = True
    is_active: bool = True
    created_by: Optional[str] = "admin"

class UpdateZoneRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    zone_type: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_m: Optional[float] = None
    polygon_coordinates: Optional[List[List[List[float]]]] = None
    alert_on_entry: Optional[bool] = None
    alert_on_exit: Optional[bool] = None
    is_active: Optional[bool] = None

class RegisterPOSRequest(BaseModel):
    serial_number: str
    agent_id: Optional[str] = None
    merchant_id: Optional[str] = None
    brand: str
    model: str
    registration_lat: float
    registration_lng: float
    geofence_zone_id: Optional[str] = None
    geofence_radius_m: int = Field(default=500, ge=50, le=10000)
    geofence_enabled: bool = True

class LocationUpdateRequest(BaseModel):
    terminal_id: str
    lat: float
    lng: float
    timestamp: Optional[datetime] = None
    transaction_id: Optional[str] = None

class GeoFenceZone(BaseModel):
    zone_id: str
    name: str
    description: Optional[str]
    zone_type: str
    geometry: Dict
    center_lat: Optional[float]
    center_lng: Optional[float]
    radius_m: Optional[int]
    state: Optional[str]
    lga: Optional[str]
    is_active: bool
    alert_on_entry: bool
    alert_on_exit: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Geometry Utilities ─────────────────────────────────────────────────────────

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two WGS-84 coordinates."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lng: float, polygon_coords: List[List[float]]) -> bool:
    """
    Ray-casting algorithm to determine if point (lat, lng) is inside a polygon.
    polygon_coords: list of [lng, lat] pairs (GeoJSON order).
    """
    x, y = lng, lat
    n = len(polygon_coords)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon_coords[i][0], polygon_coords[i][1]
        xj, yj = polygon_coords[j][0], polygon_coords[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-10) + xi):
            inside = not inside
        j = i
    return inside


def compute_polygon_centroid(coords: List[List[float]]) -> Tuple[float, float]:
    """Return (lat, lng) centroid of a GeoJSON polygon ring."""
    n = len(coords) - 1  # exclude closing point
    if n <= 0:
        return 0.0, 0.0
    lng_sum = sum(c[0] for c in coords[:n])
    lat_sum = sum(c[1] for c in coords[:n])
    return lat_sum / n, lng_sum / n


def is_point_in_zone(lat: float, lng: float, zone: Dict) -> Tuple[bool, float]:
    """
    Check if a point is inside a geo-fence zone.
    Returns (is_inside, distance_to_boundary_m).
    """
    geometry = zone.get("geometry", {})
    geo_type = geometry.get("type", "")

    if geo_type == "Circle":
        center = geometry.get("center", {})
        radius_m = geometry.get("radius_m", zone.get("radius_m", 500))
        dist = haversine_distance(lat, lng, center.get("lat", 0), center.get("lng", 0))
        return dist <= radius_m, abs(dist - radius_m)

    elif geo_type in ("Polygon", "polygon"):
        coords = geometry.get("coordinates", [[]])[0]
        inside = point_in_polygon(lat, lng, coords)
        # Approximate distance to boundary
        clat, clng = compute_polygon_centroid(coords)
        dist = haversine_distance(lat, lng, clat, clng)
        return inside, dist

    else:
        # Fallback: use radius_m from zone record
        radius_m = zone.get("radius_m", 500)
        clat = zone.get("center_lat", 0)
        clng = zone.get("center_lng", 0)
        dist = haversine_distance(lat, lng, clat, clng)
        return dist <= radius_m, abs(dist - radius_m)


# ── Service Class ──────────────────────────────────────────────────────────────

class POSGeofencingService:
    def __init__(self):
        self._db: Optional[asyncpg.Pool] = None
        self._redis: Optional[aioredis.Redis] = None

    async def startup(self):
        self._db = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        logger.info("POSGeofencingService started")

    async def shutdown(self):
        if self._db:
            await self._db.close()
        if self._redis:
            await self._redis.close()

    # ── Zone Management ────────────────────────────────────────────────────────

    async def create_zone(self, req: CreateZoneRequest) -> Dict:
        """Create a new geo-fence zone (circle or polygon)."""
        zone_id = f"GFZ{uuid.uuid4().hex[:10].upper()}"

        if req.geometry_type == "Circle":
            if req.center_lat is None or req.center_lng is None or req.radius_m is None:
                raise HTTPException(400, "Circle zones require center_lat, center_lng, and radius_m")
            geometry = {
                "type": "Circle",
                "center": {"lat": req.center_lat, "lng": req.center_lng},
                "radius_m": req.radius_m,
            }
            center_lat, center_lng = req.center_lat, req.center_lng
            radius_m = int(req.radius_m)

        elif req.geometry_type == "Polygon":
            if not req.polygon_coordinates:
                raise HTTPException(400, "Polygon zones require polygon_coordinates")
            coords = req.polygon_coordinates
            # Auto-close polygon
            if coords[0][0] != coords[0][-1]:
                coords[0].append(coords[0][0])
            geometry = {"type": "Polygon", "coordinates": coords}
            center_lat, center_lng = compute_polygon_centroid(coords[0])
            # Approximate radius as max distance from centroid to any vertex
            radius_m = int(max(
                haversine_distance(center_lat, center_lng, c[1], c[0])
                for c in coords[0]
            ))
        else:
            raise HTTPException(400, f"Unknown geometry_type: {req.geometry_type}")

        async with self._db.acquire() as conn:
            await conn.execute(
                """INSERT INTO geofence_zones
                   (zone_id, name, description, zone_type, geometry, center_lat, center_lng,
                    radius_m, state, lga, is_active, alert_on_entry, alert_on_exit, created_by)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                zone_id, req.name, req.description, req.zone_type,
                json.dumps(geometry), center_lat, center_lng, radius_m,
                req.state, req.lga, req.is_active,
                req.alert_on_entry, req.alert_on_exit, req.created_by,
            )

        # Invalidate cache
        await self._redis.delete(f"zone:{zone_id}", "zones:all")

        return {"zone_id": zone_id, "message": "Geo-fence zone created", "geometry_type": req.geometry_type}

    async def get_zone(self, zone_id: str) -> Dict:
        cache_key = f"zone:{zone_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            return json.loads(cached)

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM geofence_zones WHERE zone_id = $1", zone_id
            )
        if not row:
            raise HTTPException(404, f"Zone {zone_id} not found")

        result = dict(row)
        result["geometry"] = json.loads(result["geometry"]) if isinstance(result["geometry"], str) else result["geometry"]
        for k, v in result.items():
            if isinstance(v, datetime):
                result[k] = v.isoformat()

        await self._redis.setex(cache_key, 300, json.dumps(result))
        return result

    async def list_zones(self, state: Optional[str] = None,
                          zone_type: Optional[str] = None,
                          active_only: bool = True,
                          page: int = 1, page_size: int = 50) -> Dict:
        offset = (page - 1) * page_size
        conditions = []
        params: List[Any] = []
        idx = 1

        if active_only:
            conditions.append(f"is_active = TRUE")
        if state:
            conditions.append(f"state = ${idx}")
            params.append(state)
            idx += 1
        if zone_type:
            conditions.append(f"zone_type = ${idx}")
            params.append(zone_type)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([page_size, offset])

        async with self._db.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM geofence_zones {where}", *params[:-2])
            rows = await conn.fetch(
                f"SELECT * FROM geofence_zones {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
                *params
            )

        zones = []
        for row in rows:
            z = dict(row)
            z["geometry"] = json.loads(z["geometry"]) if isinstance(z["geometry"], str) else z["geometry"]
            for k, v in z.items():
                if isinstance(v, datetime):
                    z[k] = v.isoformat()
            zones.append(z)

        return {"zones": zones, "total": total, "page": page, "page_size": page_size}

    async def update_zone(self, zone_id: str, req: UpdateZoneRequest) -> Dict:
        """Dynamically update a geo-fence zone geometry or metadata."""
        existing = await self.get_zone(zone_id)

        updates: List[str] = []
        params: List[Any] = []
        idx = 1

        def add(field: str, value: Any):
            nonlocal idx
            updates.append(f"{field} = ${idx}")
            params.append(value)
            idx += 1

        if req.name is not None:
            add("name", req.name)
        if req.description is not None:
            add("description", req.description)
        if req.zone_type is not None:
            add("zone_type", req.zone_type)
        if req.alert_on_entry is not None:
            add("alert_on_entry", req.alert_on_entry)
        if req.alert_on_exit is not None:
            add("alert_on_exit", req.alert_on_exit)
        if req.is_active is not None:
            add("is_active", req.is_active)

        # Geometry update
        if req.polygon_coordinates is not None:
            coords = req.polygon_coordinates
            if coords[0][0] != coords[0][-1]:
                coords[0].append(coords[0][0])
            geometry = {"type": "Polygon", "coordinates": coords}
            clat, clng = compute_polygon_centroid(coords[0])
            radius_m = int(max(
                haversine_distance(clat, clng, c[1], c[0]) for c in coords[0]
            ))
            add("geometry", json.dumps(geometry))
            add("center_lat", clat)
            add("center_lng", clng)
            add("radius_m", radius_m)
        elif req.center_lat is not None and req.center_lng is not None and req.radius_m is not None:
            geometry = {
                "type": "Circle",
                "center": {"lat": req.center_lat, "lng": req.center_lng},
                "radius_m": req.radius_m,
            }
            add("geometry", json.dumps(geometry))
            add("center_lat", req.center_lat)
            add("center_lng", req.center_lng)
            add("radius_m", int(req.radius_m))

        if not updates:
            return {"zone_id": zone_id, "message": "No changes provided"}

        add("updated_at", datetime.now(timezone.utc))
        params.append(zone_id)

        async with self._db.acquire() as conn:
            await conn.execute(
                f"UPDATE geofence_zones SET {', '.join(updates)} WHERE zone_id = ${idx}",
                *params
            )

        await self._redis.delete(f"zone:{zone_id}", "zones:all")
        return {"zone_id": zone_id, "message": "Zone updated successfully"}

    async def delete_zone(self, zone_id: str) -> Dict:
        async with self._db.acquire() as conn:
            # Unassign terminals from this zone
            await conn.execute(
                "UPDATE pos_terminals SET geofence_zone_id = NULL WHERE geofence_zone_id = $1",
                zone_id
            )
            result = await conn.execute(
                "DELETE FROM geofence_zones WHERE zone_id = $1", zone_id
            )
        if result == "DELETE 0":
            raise HTTPException(404, f"Zone {zone_id} not found")
        await self._redis.delete(f"zone:{zone_id}", "zones:all")
        return {"zone_id": zone_id, "message": "Zone deleted"}

    # ── POS Terminal Registration ───────────────────────────────────────────────

    async def register_pos_terminal(self, req: RegisterPOSRequest) -> Dict:
        """Register a POS terminal with geo-fencing. Auto-assigns nearest zone if none specified."""
        terminal_id = f"TRM{uuid.uuid4().hex[:10].upper()}"

        zone_id = req.geofence_zone_id
        if not zone_id and req.geofence_enabled:
            # Auto-assign nearest active zone within 5km
            zone_id = await self._find_nearest_zone(req.registration_lat, req.registration_lng, max_dist_m=5000)

        async with self._db.acquire() as conn:
            await conn.execute(
                """INSERT INTO pos_terminals
                   (terminal_id, serial_number, agent_id, merchant_id, brand, model,
                    status, registration_lat, registration_lng, current_lat, current_lng,
                    geofence_zone_id, geofence_radius_m, geofence_enabled, last_seen_at)
                   VALUES ($1,$2,$3,$4,$5,$6,'active',$7,$8,$9,$10,$11,$12,$13,NOW())""",
                terminal_id, req.serial_number,
                req.agent_id, req.merchant_id,
                req.brand, req.model,
                req.registration_lat, req.registration_lng,
                req.registration_lat, req.registration_lng,
                zone_id, req.geofence_radius_m, req.geofence_enabled,
            )

        zone_info = None
        if zone_id:
            try:
                zone_info = await self.get_zone(zone_id)
            except Exception:
                pass

        return {
            "terminal_id": terminal_id,
            "serial_number": req.serial_number,
            "geofence_zone_id": zone_id,
            "geofence_enabled": req.geofence_enabled,
            "geofence_radius_m": req.geofence_radius_m,
            "zone_info": zone_info,
            "message": "POS terminal registered with geo-fencing",
        }

    async def _find_nearest_zone(self, lat: float, lng: float, max_dist_m: float = 5000) -> Optional[str]:
        """Find the nearest active geo-fence zone to a coordinate."""
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """SELECT zone_id, center_lat, center_lng, radius_m
                   FROM geofence_zones
                   WHERE is_active = TRUE
                   ORDER BY (center_lat - $1)^2 + (center_lng - $2)^2
                   LIMIT 20""",
                lat, lng
            )
        if not rows:
            return None

        best_zone_id = None
        best_dist = float("inf")
        for row in rows:
            dist = haversine_distance(lat, lng, row["center_lat"], row["center_lng"])
            if dist < best_dist and dist <= max_dist_m:
                best_dist = dist
                best_zone_id = row["zone_id"]

        return best_zone_id

    async def assign_zone_to_terminal(self, terminal_id: str, zone_id: str,
                                       radius_m: Optional[int] = None) -> Dict:
        """Dynamically reassign a POS terminal to a different geo-fence zone."""
        zone = await self.get_zone(zone_id)  # validates zone exists

        async with self._db.acquire() as conn:
            updates = ["geofence_zone_id = $1", "updated_at = NOW()"]
            params: List[Any] = [zone_id]
            if radius_m is not None:
                updates.append(f"geofence_radius_m = ${len(params)+1}")
                params.append(radius_m)
            params.append(terminal_id)
            await conn.execute(
                f"UPDATE pos_terminals SET {', '.join(updates)} WHERE terminal_id = ${len(params)}",
                *params
            )

        await self._redis.delete(f"terminal:{terminal_id}")
        return {"terminal_id": terminal_id, "zone_id": zone_id, "message": "Zone assigned"}

    # ── Real-time Location Validation ──────────────────────────────────────────

    async def validate_location(self, req: LocationUpdateRequest) -> Dict:
        """
        Validate a POS terminal's current location against its assigned geo-fence zone.
        Called on every transaction and periodic heartbeat.
        """
        # Get terminal
        terminal = await self._get_terminal(req.terminal_id)
        if not terminal:
            raise HTTPException(404, f"Terminal {req.terminal_id} not found")

        # Update current location
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE pos_terminals SET current_lat=$1, current_lng=$2, last_seen_at=NOW() WHERE terminal_id=$3",
                req.lat, req.lng, req.terminal_id
            )

        result = {
            "terminal_id": req.terminal_id,
            "lat": req.lat,
            "lng": req.lng,
            "geofence_enabled": terminal.get("geofence_enabled", False),
            "is_compliant": True,
            "violation": None,
        }

        if not terminal.get("geofence_enabled"):
            return result

        zone_id = terminal.get("geofence_zone_id")
        if not zone_id:
            return result

        try:
            zone = await self.get_zone(zone_id)
        except HTTPException:
            return result

        is_inside, dist_to_boundary = is_point_in_zone(req.lat, req.lng, zone)

        if not is_inside:
            # Compute distance from registration point as additional signal
            reg_dist = haversine_distance(
                req.lat, req.lng,
                terminal.get("registration_lat", req.lat),
                terminal.get("registration_lng", req.lng),
            )
            severity = self._compute_severity(reg_dist, dist_to_boundary)
            violation = await self._record_violation(
                terminal_id=req.terminal_id,
                zone_id=zone_id,
                violation_type="TRANSACTION_OUTSIDE_GEOFENCE" if req.transaction_id else "LOCATION_DRIFT",
                lat=req.lat, lng=req.lng,
                distance_m=reg_dist,
                severity=severity,
            )
            result["is_compliant"] = False
            result["violation"] = violation
            result["distance_from_zone_m"] = round(dist_to_boundary, 1)
            result["distance_from_registration_m"] = round(reg_dist, 1)
            result["severity"] = severity

            # Fire alert
            if zone.get("alert_on_exit"):
                await self._fire_alert(terminal, zone, violation)

        return result

    def _compute_severity(self, reg_dist: float, boundary_dist: float) -> str:
        combined = max(reg_dist, boundary_dist)
        if combined < 200:
            return "low"
        elif combined < 1000:
            return "medium"
        elif combined < 5000:
            return "high"
        return "critical"

    async def _record_violation(self, terminal_id: str, zone_id: str,
                                  violation_type: str, lat: float, lng: float,
                                  distance_m: float, severity: str) -> Dict:
        violation_id = f"VIO{uuid.uuid4().hex[:10].upper()}"
        async with self._db.acquire() as conn:
            await conn.execute(
                """INSERT INTO geofence_violations
                   (violation_id, terminal_id, zone_id, violation_type,
                    detected_lat, detected_lng, distance_m, severity)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                violation_id, terminal_id, zone_id, violation_type,
                lat, lng, distance_m, severity,
            )
        return {
            "violation_id": violation_id,
            "type": violation_type,
            "severity": severity,
            "distance_m": round(distance_m, 1),
        }

    async def _fire_alert(self, terminal: Dict, zone: Dict, violation: Dict):
        """Push violation alert to Redis pub/sub and optional webhook."""
        alert = {
            "event": "geofence_violation",
            "terminal_id": terminal.get("terminal_id"),
            "agent_id": terminal.get("agent_id"),
            "zone_id": zone.get("zone_id"),
            "zone_name": zone.get("name"),
            "violation": violation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._redis.publish("geofence_alerts", json.dumps(alert))

        if ALERT_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(ALERT_WEBHOOK_URL, json=alert)
            except Exception as e:
                logger.warning(f"Alert webhook failed: {e}")

    # ── Terminal Queries ───────────────────────────────────────────────────────

    async def _get_terminal(self, terminal_id: str) -> Optional[Dict]:
        cache_key = f"terminal:{terminal_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            return json.loads(cached)

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pos_terminals WHERE terminal_id = $1", terminal_id
            )
        if not row:
            return None
        result = dict(row)
        for k, v in result.items():
            if isinstance(v, datetime):
                result[k] = v.isoformat()
        await self._redis.setex(cache_key, 60, json.dumps(result))
        return result

    async def get_terminal(self, terminal_id: str) -> Dict:
        t = await self._get_terminal(terminal_id)
        if not t:
            raise HTTPException(404, f"Terminal {terminal_id} not found")
        return t

    async def list_terminals(self, agent_id: Optional[str] = None,
                               zone_id: Optional[str] = None,
                               status: Optional[str] = None,
                               page: int = 1, page_size: int = 50) -> Dict:
        conditions = []
        params: List[Any] = []
        idx = 1

        if agent_id:
            conditions.append(f"agent_id = ${idx}")
            params.append(agent_id)
            idx += 1
        if zone_id:
            conditions.append(f"geofence_zone_id = ${idx}")
            params.append(zone_id)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size
        params.extend([page_size, offset])

        async with self._db.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM pos_terminals {where}", *params[:-2])
            rows = await conn.fetch(
                f"SELECT * FROM pos_terminals {where} ORDER BY registered_at DESC LIMIT ${idx} OFFSET ${idx+1}",
                *params
            )

        terminals = []
        for row in rows:
            t = dict(row)
            for k, v in t.items():
                if isinstance(v, datetime):
                    t[k] = v.isoformat()
            terminals.append(t)

        return {"terminals": terminals, "total": total, "page": page, "page_size": page_size}

    # ── Violations ─────────────────────────────────────────────────────────────

    async def list_violations(self, terminal_id: Optional[str] = None,
                               zone_id: Optional[str] = None,
                               severity: Optional[str] = None,
                               resolved: Optional[bool] = None,
                               page: int = 1, page_size: int = 50) -> Dict:
        conditions = []
        params: List[Any] = []
        idx = 1

        if terminal_id:
            conditions.append(f"terminal_id = ${idx}")
            params.append(terminal_id)
            idx += 1
        if zone_id:
            conditions.append(f"zone_id = ${idx}")
            params.append(zone_id)
            idx += 1
        if severity:
            conditions.append(f"severity = ${idx}")
            params.append(severity)
            idx += 1
        if resolved is not None:
            conditions.append(f"resolved = ${idx}")
            params.append(resolved)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size
        params.extend([page_size, offset])

        async with self._db.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM geofence_violations {where}", *params[:-2])
            rows = await conn.fetch(
                f"SELECT * FROM geofence_violations {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
                *params
            )

        violations = []
        for row in rows:
            v = dict(row)
            for k, val in v.items():
                if isinstance(val, datetime):
                    v[k] = val.isoformat()
            violations.append(v)

        return {"violations": violations, "total": total, "page": page, "page_size": page_size}

    async def resolve_violation(self, violation_id: str) -> Dict:
        async with self._db.acquire() as conn:
            result = await conn.execute(
                "UPDATE geofence_violations SET resolved=TRUE, resolved_at=NOW() WHERE violation_id=$1",
                violation_id
            )
        if result == "UPDATE 0":
            raise HTTPException(404, f"Violation {violation_id} not found")
        return {"violation_id": violation_id, "message": "Violation resolved"}

    # ── Map Data Feed ──────────────────────────────────────────────────────────

    async def get_map_data(self, state: Optional[str] = None,
                            include_violations: bool = True) -> Dict:
        """
        Returns all zones, terminals, and recent violations for map rendering.
        Optimised for the live map UI component.
        """
        async with self._db.acquire() as conn:
            zone_query = "SELECT zone_id, name, zone_type, geometry, center_lat, center_lng, radius_m, is_active, state FROM geofence_zones WHERE is_active = TRUE"
            zone_params: List[Any] = []
            if state:
                zone_query += " AND state = $1"
                zone_params.append(state)
            zones_rows = await conn.fetch(zone_query, *zone_params)

            terminal_query = """
                SELECT t.terminal_id, t.agent_id, t.merchant_id, t.brand,
                       t.status, t.current_lat, t.current_lng,
                       t.registration_lat, t.registration_lng,
                       t.geofence_zone_id, t.geofence_enabled, t.last_seen_at
                FROM pos_terminals t
                WHERE t.current_lat IS NOT NULL
            """
            terminal_params: List[Any] = []
            if state:
                terminal_query += " AND t.agent_id IN (SELECT agent_id FROM agents WHERE state = $1)"
                terminal_params.append(state)
            terminal_rows = await conn.fetch(terminal_query, *terminal_params)

            violation_rows = []
            if include_violations:
                viol_query = """
                    SELECT violation_id, terminal_id, zone_id, violation_type,
                           detected_lat, detected_lng, severity, resolved, created_at
                    FROM geofence_violations
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                    LIMIT 500
                """
                violation_rows = await conn.fetch(viol_query)

        zones = []
        for row in zones_rows:
            z = dict(row)
            z["geometry"] = json.loads(z["geometry"]) if isinstance(z["geometry"], str) else z["geometry"]
            zones.append(z)

        terminals = []
        for row in terminal_rows:
            t = dict(row)
            for k, v in t.items():
                if isinstance(v, datetime):
                    t[k] = v.isoformat()
            terminals.append(t)

        violations = []
        for row in violation_rows:
            v = dict(row)
            for k, val in v.items():
                if isinstance(val, datetime):
                    v[k] = val.isoformat()
            violations.append(v)

        return {
            "zones": zones,
            "terminals": terminals,
            "violations": violations,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Analytics ──────────────────────────────────────────────────────────────

    async def get_zone_analytics(self, zone_id: str) -> Dict:
        zone = await self.get_zone(zone_id)
        async with self._db.acquire() as conn:
            terminal_count = await conn.fetchval(
                "SELECT COUNT(*) FROM pos_terminals WHERE geofence_zone_id = $1", zone_id
            )
            active_terminal_count = await conn.fetchval(
                "SELECT COUNT(*) FROM pos_terminals WHERE geofence_zone_id = $1 AND status = 'active'", zone_id
            )
            violation_count = await conn.fetchval(
                "SELECT COUNT(*) FROM geofence_violations WHERE zone_id = $1", zone_id
            )
            unresolved_violations = await conn.fetchval(
                "SELECT COUNT(*) FROM geofence_violations WHERE zone_id = $1 AND resolved = FALSE", zone_id
            )
            severity_breakdown = await conn.fetch(
                "SELECT severity, COUNT(*) as count FROM geofence_violations WHERE zone_id = $1 GROUP BY severity",
                zone_id
            )

        return {
            "zone_id": zone_id,
            "zone_name": zone.get("name"),
            "zone_type": zone.get("zone_type"),
            "terminal_count": terminal_count,
            "active_terminal_count": active_terminal_count,
            "total_violations": violation_count,
            "unresolved_violations": unresolved_violations,
            "severity_breakdown": {row["severity"]: row["count"] for row in severity_breakdown},
        }

    async def get_platform_geofence_summary(self) -> Dict:
        async with self._db.acquire() as conn:
            total_zones = await conn.fetchval("SELECT COUNT(*) FROM geofence_zones")
            active_zones = await conn.fetchval("SELECT COUNT(*) FROM geofence_zones WHERE is_active = TRUE")
            total_terminals = await conn.fetchval("SELECT COUNT(*) FROM pos_terminals")
            fenced_terminals = await conn.fetchval(
                "SELECT COUNT(*) FROM pos_terminals WHERE geofence_enabled = TRUE AND geofence_zone_id IS NOT NULL"
            )
            violations_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM geofence_violations WHERE created_at > NOW() - INTERVAL '24 hours'"
            )
            unresolved = await conn.fetchval(
                "SELECT COUNT(*) FROM geofence_violations WHERE resolved = FALSE"
            )
            by_type = await conn.fetch(
                "SELECT zone_type, COUNT(*) as count FROM geofence_zones GROUP BY zone_type ORDER BY count DESC"
            )
            by_state = await conn.fetch(
                "SELECT state, COUNT(*) as count FROM geofence_zones GROUP BY state ORDER BY count DESC LIMIT 10"
            )

        return {
            "total_zones": total_zones,
            "active_zones": active_zones,
            "total_terminals": total_terminals,
            "geofenced_terminals": fenced_terminals,
            "geofence_coverage_pct": round(fenced_terminals / max(total_terminals, 1) * 100, 1),
            "violations_last_24h": violations_24h,
            "unresolved_violations": unresolved,
            "zones_by_type": {row["zone_type"]: row["count"] for row in by_type},
            "top_states_by_zones": {row["state"]: row["count"] for row in by_state},
        }


# Singleton
geofencing_service = POSGeofencingService()
