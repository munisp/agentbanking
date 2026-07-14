"""
Rewards Service Router
API endpoints for rewards service
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from . import schemas, service
from .database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.RewardsServiceResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: schemas.RewardsServiceCreate,
    db = Depends(get_db)
):
    """Create new rewards service"""
    return await service.create(db, data)

@router.get("/{id}", response_model=schemas.RewardsServiceResponse)
async def get_by_id(
    id: str,
    db = Depends(get_db)
):
    """Get rewards service by ID"""
    result = await service.get_by_id(db, id)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result

@router.get("/", response_model=List[schemas.RewardsServiceResponse])
async def get_all(
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db)
):
    """Get all rewards service"""
    return await service.get_all(db, skip=skip, limit=limit)

@router.put("/{id}", response_model=schemas.RewardsServiceResponse)
async def update(
    id: str,
    data: schemas.RewardsServiceUpdate,
    db = Depends(get_db)
):
    """Update rewards service"""
    result = await service.update(db, id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    id: str,
    db = Depends(get_db)
):
    """Delete rewards service"""
    success = await service.delete(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Not found")
    return None
