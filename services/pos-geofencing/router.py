"""
POS Geo-Fencing Router — FastAPI endpoints
"""

import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .service import (
    geofencing_service,
    CreateZoneRequest,
    UpdateZoneRequest,
    RegisterPOSRequest,
    LocationUpdateRequest,
)

router = APIRouter(prefix="/api/v1/geofencing", tags=["POS Geo-Fencing"])


# ── Zone Management ────────────────────────────────────────────────────────────

@router.post("/zones", summary="Create a new geo-fence zone (circle or polygon)")
async def create_zone(req: CreateZoneRequest):
    """
    Create a dynamic geo-fence zone.

    - **Circle**: provide `center_lat`, `center_lng`, `radius_m`
    - **Polygon**: provide `polygon_coordinates` as GeoJSON `[[[lng,lat],...]]`

    Zone types: AGENT_OPERATING_AREA | MERCHANT_DELIVERY_ZONE | RESTRICTED_ZONE |
    HIGH_RISK_AREA | PREMIUM_ZONE | MARKET_ZONE | CAMPUS_ZONE | INDUSTRIAL_ZONE
    """
    return await geofencing_service.create_zone(req)


@router.get("/zones", summary="List all geo-fence zones with optional filters")
async def list_zones(
    state: Optional[str] = Query(None, description="Filter by Nigerian state"),
    zone_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return await geofencing_service.list_zones(state, zone_type, active_only, page, page_size)


@router.get("/zones/{zone_id}", summary="Get a specific geo-fence zone")
async def get_zone(zone_id: str):
    return await geofencing_service.get_zone(zone_id)


@router.put("/zones/{zone_id}", summary="Update a geo-fence zone geometry or metadata")
async def update_zone(zone_id: str, req: UpdateZoneRequest):
    """
    Dynamically update a zone. You can reshape a polygon, move a circle,
    change the zone type, or toggle alerts — all without re-registering terminals.
    """
    return await geofencing_service.update_zone(zone_id, req)


@router.delete("/zones/{zone_id}", summary="Delete a geo-fence zone")
async def delete_zone(zone_id: str):
    return await geofencing_service.delete_zone(zone_id)


@router.get("/zones/{zone_id}/analytics", summary="Get analytics for a specific zone")
async def get_zone_analytics(zone_id: str):
    return await geofencing_service.get_zone_analytics(zone_id)


# ── POS Terminal Management ────────────────────────────────────────────────────

@router.post("/terminals/register", summary="Register a POS terminal with geo-fencing")
async def register_terminal(req: RegisterPOSRequest):
    """
    Register a new POS terminal. If `geofence_zone_id` is not provided and
    `geofence_enabled` is True, the nearest active zone within 5km is
    automatically assigned.
    """
    return await geofencing_service.register_pos_terminal(req)


@router.get("/terminals", summary="List POS terminals with optional filters")
async def list_terminals(
    agent_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return await geofencing_service.list_terminals(agent_id, zone_id, status, page, page_size)


@router.get("/terminals/{terminal_id}", summary="Get a specific POS terminal")
async def get_terminal(terminal_id: str):
    return await geofencing_service.get_terminal(terminal_id)


@router.post("/terminals/{terminal_id}/assign-zone", summary="Assign or reassign a terminal to a zone")
async def assign_zone(
    terminal_id: str,
    zone_id: str = Query(..., description="Zone ID to assign"),
    radius_m: Optional[int] = Query(None, description="Override geo-fence radius in metres"),
):
    return await geofencing_service.assign_zone_to_terminal(terminal_id, zone_id, radius_m)


# ── Location Validation ────────────────────────────────────────────────────────

@router.post("/validate-location", summary="Validate a POS terminal's current location")
async def validate_location(req: LocationUpdateRequest):
    """
    Called on every transaction or periodic heartbeat.
    Returns compliance status, violation details (if any), and distance metrics.
    """
    return await geofencing_service.validate_location(req)


# ── Violations ─────────────────────────────────────────────────────────────────

@router.get("/violations", summary="List geo-fence violations")
async def list_violations(
    terminal_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, description="low | medium | high | critical"),
    resolved: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return await geofencing_service.list_violations(terminal_id, zone_id, severity, resolved, page, page_size)


@router.post("/violations/{violation_id}/resolve", summary="Mark a violation as resolved")
async def resolve_violation(violation_id: str):
    return await geofencing_service.resolve_violation(violation_id)


# ── Map Data ───────────────────────────────────────────────────────────────────

@router.get("/map-data", summary="Get all zones, terminals, and recent violations for map rendering")
async def get_map_data(
    state: Optional[str] = Query(None, description="Filter by Nigerian state"),
    include_violations: bool = Query(True),
):
    """
    Returns a single payload with all active zones (with GeoJSON geometry),
    all POS terminal positions, and the last 24h of violations.
    Used by the interactive map UI.
    """
    return await geofencing_service.get_map_data(state, include_violations)


@router.get("/map-data/stream", summary="Server-Sent Events stream for live map updates")
async def stream_map_updates(state: Optional[str] = Query(None)):
    """
    SSE endpoint — pushes geo-fence alert events to the live map UI in real time.
    """
    async def event_generator():
        redis = geofencing_service._redis
        pubsub = redis.pubsub()
        await pubsub.subscribe("geofence_alerts")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                if message:
                    yield f"data: {message['data']}\n\n"
                else:
                    yield "data: {\"heartbeat\": true}\n\n"
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe("geofence_alerts")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Summary / Dashboard ────────────────────────────────────────────────────────

@router.get("/summary", summary="Platform-wide geo-fencing summary")
async def get_summary():
    return await geofencing_service.get_platform_geofence_summary()
