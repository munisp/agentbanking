"""
POS Shell Configuration Router
FastAPI endpoints for tile layout management.
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from service import POSShellConfigService

router = APIRouter(prefix="/api/v1/pos-shell", tags=["POS Shell Config"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class SaveLayoutRequest(BaseModel):
    agent_id: str = Field(..., description="Agent identifier")
    device_id: str = Field(..., description="POS device identifier")
    pinned_tile_ids: List[str] = Field(..., max_items=12, description="Ordered list of pinned tile IDs")
    usage_counts: Optional[Dict[str, int]] = Field(None, description="Tile usage counts to merge")


class RecordUsageRequest(BaseModel):
    agent_id: str
    device_id: str
    tile_id: str
    count: int = Field(1, ge=1, le=100)


class PushLayoutRequest(BaseModel):
    agent_id: str
    pinned_tile_ids: List[str] = Field(..., max_items=12)


# ── Dependency ─────────────────────────────────────────────────────────────────

def get_service() -> POSShellConfigService:
    from main import pos_shell_service
    return pos_shell_service


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/layout")
async def get_layout(
    agent_id: str = Query(...),
    device_id: str = Query(...),
    svc: POSShellConfigService = Depends(get_service),
):
    """Get the tile layout for an agent/device pair."""
    return await svc.get_layout(agent_id, device_id)


@router.put("/layout")
async def save_layout(
    request: SaveLayoutRequest,
    svc: POSShellConfigService = Depends(get_service),
):
    """Save (create or update) the tile layout for an agent/device pair."""
    return await svc.save_layout(
        agent_id=request.agent_id,
        device_id=request.device_id,
        pinned_tile_ids=request.pinned_tile_ids,
        usage_counts=request.usage_counts,
    )


@router.delete("/layout")
async def reset_layout(
    agent_id: str = Query(...),
    device_id: str = Query(...),
    svc: POSShellConfigService = Depends(get_service),
):
    """Reset layout to platform defaults for an agent/device pair."""
    return await svc.reset_layout(agent_id, device_id)


@router.post("/layout/push-all")
async def push_layout_to_all_devices(
    request: PushLayoutRequest,
    svc: POSShellConfigService = Depends(get_service),
):
    """Admin: push a tile layout to all registered devices of an agent."""
    return await svc.push_layout_to_all_devices(
        agent_id=request.agent_id,
        pinned_tile_ids=request.pinned_tile_ids,
    )


@router.post("/usage")
async def record_usage(
    request: RecordUsageRequest,
    svc: POSShellConfigService = Depends(get_service),
):
    """Record a tile tap event for usage tracking."""
    await svc.record_usage(request.agent_id, request.tile_id, request.count)
    return {"status": "recorded"}


@router.get("/usage")
async def get_usage(
    agent_id: str = Query(...),
    svc: POSShellConfigService = Depends(get_service),
):
    """Get all tile usage counts for an agent."""
    return await svc.get_usage(agent_id)


@router.get("/analytics/top-tiles")
async def get_global_top_tiles(
    limit: int = Query(10, ge=1, le=50),
    svc: POSShellConfigService = Depends(get_service),
):
    """Admin: get the most-used tiles across all agents."""
    return await svc.get_global_top_tiles(limit)


@router.get("/devices")
async def get_agent_devices(
    agent_id: str = Query(...),
    svc: POSShellConfigService = Depends(get_service),
):
    """Get all registered device IDs for an agent."""
    return {"agent_id": agent_id, "devices": await svc.get_agent_devices(agent_id)}


@router.delete("/devices/{device_id}")
async def deregister_device(
    device_id: str,
    agent_id: str = Query(...),
    svc: POSShellConfigService = Depends(get_service),
):
    """Deregister a device from an agent's device registry."""
    await svc.deregister_device(agent_id, device_id)
    return {"status": "deregistered", "device_id": device_id}
