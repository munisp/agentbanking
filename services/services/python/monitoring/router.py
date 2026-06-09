from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from . import schemas, service
from .database import get_db

router = APIRouter(
    prefix="/api/v1",
    tags=["monitoring"],
    responses={404: {"description": "Not found"}},
)

# --- Dependency for simple placeholder authentication ---
# In a real application, this would validate a JWT or API key
def get_current_user() -> Dict[str, Any]:
    # Production implementation for a simple user object or ID
    # For this task, we'll assume the user is authenticated
    return {"id": 1, "username": "admin"}

# --- Service Routes ---

@router.post("/services/", response_model=schemas.Service, status_code=status.HTTP_201_CREATED)
def create_service(
    service_data: schemas.ServiceCreate, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """Create a new service to monitor."""
    try:
        return service.create_service(db=db, service=service_data)
    except service.ServiceAlreadyExists as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/services/", response_model=List[schemas.Service])
def read_services(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000), 
    db: Session = Depends(get_db)
) -> None:
    """Retrieve a list of all monitored services."""
    return service.get_all_services(db, skip=skip, limit=limit)

@router.get("/services/{service_id}", response_model=schemas.Service)
def read_service(service_id: int, db: Session = Depends(get_db)) -> None:
    """Retrieve a single service by ID."""
    try:
        return service.get_service_by_id(db, service_id=service_id)
    except service.ServiceNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/services/{service_id}", response_model=schemas.Service)
def update_service(
    service_id: int, 
    service_data: schemas.ServiceUpdate, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """Update an existing service."""
    try:
        return service.update_service(db, service_id=service_id, service_update=service_data)
    except service.ServiceNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except service.ServiceAlreadyExists as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete("/services/{service_id}", response_model=schemas.Message)
def delete_service(
    service_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """Delete a service and all its associated endpoints and records."""
    try:
        return service.delete_service(db, service_id=service_id)
    except service.ServiceNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Endpoint Routes ---

@router.post("/services/{service_id}/endpoints/", response_model=schemas.Endpoint, status_code=status.HTTP_201_CREATED)
def create_endpoint_for_service(
    service_id: int,
    endpoint_data: schemas.EndpointBase, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """Create a new endpoint to monitor for a specific service."""
    endpoint_create = schemas.EndpointCreate(service_id=service_id, **endpoint_data.model_dump())
    try:
        return service.create_endpoint(db=db, endpoint=endpoint_create)
    except service.ServiceNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except service.EndpointAlreadyExists as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/services/{service_id}/endpoints/", response_model=List[schemas.Endpoint])
def read_endpoints_for_service(
    service_id: int,
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000), 
    db: Session = Depends(get_db)
) -> None:
    """Retrieve all endpoints for a given service."""
    try:
        return service.get_endpoints_for_service(db, service_id=service_id, skip=skip, limit=limit)
    except service.ServiceNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/endpoints/{endpoint_id}", response_model=schemas.Endpoint)
def read_endpoint(endpoint_id: int, db: Session = Depends(get_db)) -> None:
    """Retrieve a single endpoint by ID."""
    try:
        return service.get_endpoint_by_id(db, endpoint_id=endpoint_id)
    except service.EndpointNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/endpoints/{endpoint_id}", response_model=schemas.Endpoint)
def update_endpoint(
    endpoint_id: int, 
    endpoint_data: schemas.EndpointUpdate, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """Update an existing endpoint."""
    try:
        return service.update_endpoint(db, endpoint_id=endpoint_id, endpoint_update=endpoint_data)
    except service.EndpointNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except service.EndpointAlreadyExists as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete("/endpoints/{endpoint_id}", response_model=schemas.Message)
def delete_endpoint(
    endpoint_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """Delete an endpoint and all its associated monitor records."""
    try:
        return service.delete_endpoint(db, endpoint_id=endpoint_id)
    except service.EndpointNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- MonitorRecord Routes ---

@router.post("/records/", response_model=schemas.MonitorRecord, status_code=status.HTTP_201_CREATED)
def create_monitor_record(
    record_data: schemas.MonitorRecordCreate, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> None:
    """
    Record a new monitoring check result. 
    This is typically called by an external monitoring worker.
    """
    try:
        return service.create_monitor_record(db=db, record=record_data)
    except service.EndpointNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException as e:
        raise e

@router.get("/endpoints/{endpoint_id}/records/", response_model=List[schemas.MonitorRecord])
def read_monitor_records_for_endpoint(
    endpoint_id: int,
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000), 
    db: Session = Depends(get_db)
) -> None:
    """Retrieve the latest monitor records for a given endpoint."""
    try:
        return service.get_monitor_records_for_endpoint(db, endpoint_id=endpoint_id, skip=skip, limit=limit)
    except service.EndpointNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)