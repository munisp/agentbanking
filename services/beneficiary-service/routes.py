"""
API routes for beneficiary-service
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from .models import BeneficiaryServiceModel
from .service import BeneficiaryServiceService

router = APIRouter(prefix="/api/v1/beneficiary-service", tags=["beneficiary-service"])

@router.post("/", response_model=BeneficiaryServiceModel)
async def create(data: dict):
    service = BeneficiaryServiceService()
    return await service.create(data)

@router.get("/{id}", response_model=BeneficiaryServiceModel)
async def get(id: str):
    service = BeneficiaryServiceService()
    return await service.get(id)

@router.get("/", response_model=List[BeneficiaryServiceModel])
async def list_all(skip: int = 0, limit: int = 100):
    service = BeneficiaryServiceService()
    return await service.list(skip, limit)

@router.put("/{id}", response_model=BeneficiaryServiceModel)
async def update(id: str, data: dict):
    service = BeneficiaryServiceService()
    return await service.update(id, data)

@router.delete("/{id}")
async def delete(id: str):
    service = BeneficiaryServiceService()
    await service.delete(id)
    return {"message": "Deleted successfully"}
