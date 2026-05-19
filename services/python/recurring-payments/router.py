"""
Recurring Payments Router
API endpoints for recurring payments
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from . import schemas, service
from .database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.RecurringPaymentsResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: schemas.RecurringPaymentsCreate,
    db = Depends(get_db)
):
    """Create new recurring payments"""
    return await service.create(db, data)

@router.get("/{id}", response_model=schemas.RecurringPaymentsResponse)
async def get_by_id(
    id: str,
    db = Depends(get_db)
):
    """Get recurring payments by ID"""
    result = await service.get_by_id(db, id)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result

@router.get("/", response_model=List[schemas.RecurringPaymentsResponse])
async def get_all(
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db)
):
    """Get all recurring payments"""
    return await service.get_all(db, skip=skip, limit=limit)

@router.put("/{id}", response_model=schemas.RecurringPaymentsResponse)
async def update(
    id: str,
    data: schemas.RecurringPaymentsUpdate,
    db = Depends(get_db)
):
    """Update recurring payments"""
    result = await service.update(db, id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    id: str,
    db = Depends(get_db)
):
    """Delete recurring payments"""
    success = await service.delete(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Not found")
    return None
