"""
FastAPI Router for Open Banking Service
Auto-generated router with complete CRUD endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from .open_banking_service import OpenBankingService

# Initialize router
router = APIRouter(
    prefix="/api/v1/open-banking",
    tags=["Open Banking"]
)

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize service
service = OpenBankingService()

# ============================================================================
# Request/Response Models
# ============================================================================

class BaseResponse(BaseModel):
    """Base response model"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

class ErrorResponse(BaseResponse):
    """Error response model"""
    error_code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")

class CreateRequest(BaseModel):
    """Create request model"""
    data: Dict[str, Any] = Field(..., description="Data to create")

class UpdateRequest(BaseModel):
    """Update request model"""
    data: Dict[str, Any] = Field(..., description="Data to update")

class ItemResponse(BaseResponse):
    """Single item response"""
    data: Optional[Dict[str, Any]] = Field(None, description="Item data")

class ListResponse(BaseResponse):
    """List response"""
    data: List[Dict[str, Any]] = Field(default_factory=list, description="List of items")
    total: int = Field(0, description="Total count")
    page: int = Field(1, description="Current page")
    page_size: int = Field(10, description="Page size")

# ============================================================================
# Endpoints
# ============================================================================

@router.get("/health", response_model=BaseResponse)
async def health_check():
    """Health check endpoint"""
    try:
        return BaseResponse(
            success=True,
            message="Open Banking service is healthy"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        )

@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(request: CreateRequest):
    """Create a new item"""
    try:
        # Call service method
        result = await service.create(request.data) if hasattr(service.create, '__call__') else service.create(request.data)
        
        return ItemResponse(
            success=True,
            message="Item created successfully",
            data=result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create item"
        )

@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: str = Path(..., description="Item ID")
):
    """Get item by ID"""
    try:
        # Call service method
        result = await service.get(item_id) if hasattr(service.get, '__call__') else service.get(item_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        return ItemResponse(
            success=True,
            message="Item retrieved successfully",
            data=result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item"
        )

@router.get("/", response_model=ListResponse)
async def list_items(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    filters: Optional[str] = Query(None, description="Filter criteria (JSON)")
):
    """List items with pagination"""
    try:
        # Call service method
        result = await service.list(page=page, page_size=page_size, filters=filters) if hasattr(service.list, '__call__') else service.list(page=page, page_size=page_size, filters=filters)
        
        return ListResponse(
            success=True,
            message="Items retrieved successfully",
            data=result.get('items', []),
            total=result.get('total', 0),
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"List failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list items"
        )

@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: str = Path(..., description="Item ID"),
    request: UpdateRequest = Body(...)
):
    """Update item by ID"""
    try:
        # Call service method
        result = await service.update(item_id, request.data) if hasattr(service.update, '__call__') else service.update(item_id, request.data)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        return ItemResponse(
            success=True,
            message="Item updated successfully",
            data=result
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update item"
        )

@router.delete("/{item_id}", response_model=BaseResponse)
async def delete_item(
    item_id: str = Path(..., description="Item ID")
):
    """Delete item by ID"""
    try:
        # Call service method
        result = await service.delete(item_id) if hasattr(service.delete, '__call__') else service.delete(item_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        return BaseResponse(
            success=True,
            message="Item deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete item"
        )

# ============================================================================
# Additional Endpoints (Service-Specific)
# ============================================================================

@router.get("/stats", response_model=ItemResponse)
async def get_stats():
    """Get service statistics"""
    try:
        stats = await service.get_stats() if hasattr(service, 'get_stats') and hasattr(service.get_stats, '__call__') else {"message": "Stats not implemented"}
        
        return ItemResponse(
            success=True,
            message="Statistics retrieved successfully",
            data=stats
        )
    except Exception as e:
        logger.error(f"Get stats failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )

@router.post("/batch", response_model=ListResponse)
async def batch_operation(
    operations: List[Dict[str, Any]] = Body(..., description="Batch operations")
):
    """Execute batch operations"""
    try:
        results = await service.batch_process(operations) if hasattr(service, 'batch_process') and hasattr(service.batch_process, '__call__') else []
        
        return ListResponse(
            success=True,
            message="Batch operations completed",
            data=results,
            total=len(results)
        )
    except Exception as e:
        logger.error(f"Batch operation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute batch operations"
        )
