from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from . import schemas, service
from .database import get_db
from .service import NotFoundError, ConflictError

router = APIRouter(
    prefix="/corridors",
    tags=["Payment Corridors"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the service layer
def get_corridor_service(db: Session = Depends(get_db)) -> service.PaymentCorridorService:
    return service.PaymentCorridorService(db)

@router.post(
    "/", 
    response_model=schemas.PaymentCorridor, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Payment Corridor",
    description="Creates a new payment corridor with associated fees and limits. The combination of source/destination country/currency must be unique."
)
def create_corridor(
    corridor: schemas.PaymentCorridorCreate,
    corridor_service: service.PaymentCorridorService = Depends(get_corridor_service)
) -> None:
    try:
        return corridor_service.create_corridor(corridor)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

@router.get(
    "/", 
    response_model=List[schemas.PaymentCorridor],
    summary="List all Payment Corridors",
    description="Retrieves a paginated list of all configured payment corridors."
)
def list_corridors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    corridor_service: service.PaymentCorridorService = Depends(get_corridor_service)
) -> None:
    return corridor_service.get_all_corridors(skip=skip, limit=limit)

@router.get(
    "/{corridor_id}", 
    response_model=schemas.PaymentCorridor,
    summary="Get a Payment Corridor by ID",
    description="Retrieves a specific payment corridor by its unique ID."
)
def get_corridor(
    corridor_id: int,
    corridor_service: service.PaymentCorridorService = Depends(get_corridor_service)
) -> None:
    try:
        return corridor_service.get_corridor(corridor_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.put(
    "/{corridor_id}", 
    response_model=schemas.PaymentCorridor,
    summary="Update an existing Payment Corridor",
    description="Updates an existing payment corridor. Nested fees and limits can be fully replaced if provided in the request body."
)
def update_corridor(
    corridor_id: int,
    corridor: schemas.PaymentCorridorUpdate,
    corridor_service: service.PaymentCorridorService = Depends(get_corridor_service)
) -> None:
    try:
        return corridor_service.update_corridor(corridor_id, corridor)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

@router.delete(
    "/{corridor_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Payment Corridor",
    description="Deletes a specific payment corridor by its unique ID, including all associated fees and limits."
)
def delete_corridor(
    corridor_id: int,
    corridor_service: service.PaymentCorridorService = Depends(get_corridor_service)
) -> None:
    try:
        corridor_service.delete_corridor(corridor_id)
        return status.HTTP_204_NO_CONTENT
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
