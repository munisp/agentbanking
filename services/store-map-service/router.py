"""Interactive Visual Map of Stores — API Router"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from service import (
    StoreMapService,
    StoreLocationCreate,
    NearbySearchRequest,
    StoreReviewCreate,
    StoreStatus,
    StoreType,
)
from config import get_db

router = APIRouter(prefix="/store-map", tags=["Store Map"])


def get_svc(db: Session = Depends(get_db)) -> StoreMapService:
    return StoreMapService(db)


@router.post("/stores")
def register_store(
    payload: StoreLocationCreate, svc: StoreMapService = Depends(get_svc)
):
    """Register or update a store/agent location on the map."""
    store = svc.register_store(payload)
    return {
        "id": store.id,
        "entity_id": store.entity_id,
        "entity_name": store.entity_name,
        "latitude": float(store.latitude),
        "longitude": float(store.longitude),
        "state": store.state,
        "lga": store.lga,
        "status": store.status.value,
    }


@router.post("/stores/nearby")
def find_nearby_stores(
    payload: NearbySearchRequest, svc: StoreMapService = Depends(get_svc)
):
    """Find stores within a given radius using Haversine distance calculation."""
    return svc.find_nearby_stores(payload)


@router.get("/stores/{entity_id}")
def get_store(entity_id: str, svc: StoreMapService = Depends(get_svc)):
    """Get full details for a specific store."""
    store = svc.get_store(entity_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {entity_id} not found")
    return store


@router.get("/stores")
def get_all_stores(
    state: Optional[str] = Query(None),
    store_type: Optional[StoreType] = Query(None),
    status: Optional[StoreStatus] = Query(None),
    limit: Optional[int] = Query(None),
    svc: StoreMapService = Depends(get_svc),
):
    """Get all stores with optional filters."""
    return svc.get_all_stores(
        state=state, store_type=store_type, status=status, limit=limit
    )


@router.patch("/stores/{entity_id}/status")
def update_store_status(
    entity_id: str,
    status: StoreStatus = Query(...),
    svc: StoreMapService = Depends(get_svc),
):
    """Update a store's open/closed status."""
    svc.update_store_status(entity_id, status)
    return {"entity_id": entity_id, "status": status.value}


@router.get("/clusters")
def get_map_clusters(
    zoom_level: int = Query(..., ge=1, le=20),
    state: Optional[str] = Query(None),
    svc: StoreMapService = Depends(get_svc),
):
    """Get store clusters for map rendering at a given zoom level."""
    return svc.get_map_clusters(zoom_level, state)


@router.get("/coverage")
def get_coverage_stats(svc: StoreMapService = Depends(get_svc)):
    """Get platform-wide store coverage statistics across Nigeria."""
    return svc.get_coverage_stats()


@router.post("/stores/{store_id}/reviews")
def add_review(
    store_id: str, payload: StoreReviewCreate, svc: StoreMapService = Depends(get_svc)
):
    """Add a customer review and rating for a store."""
    payload.store_id = store_id
    review = svc.add_review(payload)
    return {
        "id": review.id,
        "store_id": review.store_id,
        "rating": review.rating,
        "is_verified_purchase": review.is_verified_purchase,
        "created_at": str(review.created_at),
    }


@router.get("/health")
def health():
    return {"status": "ok", "service": "store-map-service"}
