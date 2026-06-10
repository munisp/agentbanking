from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db_session
from schemas import (
    Component,
    ComponentCreate,
    ComponentUpdate,
    Location,
    LocationCreate,
    LocationUpdate,
    Status,
    StatusCreate,
    StatusUpdate,
)
from service import infrastructure_service, NotFoundError, ConflictError

router = APIRouter(
    prefix="/infrastructure",
    tags=["infrastructure"],
    responses={404: {"description": "Not found"}},
)

# --- Exception Handlers ---

def handle_service_errors(func) -> None:
    """Decorator to handle service-layer exceptions and convert them to HTTPExceptions."""
    def wrapper(*args, **kwargs) -> None:
        try:
            return func(*args, **kwargs)
        except NotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except Exception as e:
            # Catch any unexpected errors
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")
    return wrapper

# --- Component Endpoints ---

@router.post("/components", response_model=Component, status_code=status.HTTP_201_CREATED, summary="Create a new infrastructure component")
@handle_service_errors
def create_component(component: ComponentCreate, db: Session = Depends(get_db_session)) -> None:
    """
    Create a new infrastructure component and store it in the database.
    """
    return infrastructure_service.create_component(db, component)

@router.get("/components", response_model=List[Component], summary="Retrieve a list of all infrastructure components")
@handle_service_errors
def read_components(skip: int = 0, limit: int = 100, db: Session = Depends(get_db_session)) -> None:
    """
    Retrieve a list of all infrastructure components with optional pagination.
    """
    return infrastructure_service.get_components(db, skip=skip, limit=limit)

@router.get("/components/{component_id}", response_model=Component, summary="Retrieve a single infrastructure component by ID")
@handle_service_errors
def read_component(component_id: int, db: Session = Depends(get_db_session)) -> None:
    """
    Retrieve a single infrastructure component by its unique ID.
    """
    return infrastructure_service.get_component(db, component_id)

@router.put("/components/{component_id}", response_model=Component, summary="Update an existing infrastructure component")
@handle_service_errors
def update_component(component_id: int, component: ComponentUpdate, db: Session = Depends(get_db_session)) -> None:
    """
    Update an existing infrastructure component's details.
    """
    return infrastructure_service.update_component(db, component_id, component)

@router.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an infrastructure component")
@handle_service_errors
def delete_component(component_id: int, db: Session = Depends(get_db_session)) -> None:
    """
    Delete an infrastructure component by its unique ID.
    """
    infrastructure_service.delete_component(db, component_id)
    return

# --- Location Endpoints ---

@router.post("/locations", response_model=Location, status_code=status.HTTP_201_CREATED, summary="Create a new infrastructure location")
@handle_service_errors
def create_location(location: LocationCreate, db: Session = Depends(get_db_session)) -> None:
    """
    Create a new infrastructure location (e.g., Data Center, Cloud Region).
    """
    return infrastructure_service.create_location(db, location)

@router.get("/locations", response_model=List[Location], summary="Retrieve a list of all infrastructure locations")
@handle_service_errors
def read_locations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db_session)) -> None:
    """
    Retrieve a list of all infrastructure locations with optional pagination.
    """
    return infrastructure_service.get_locations(db, skip=skip, limit=limit)

@router.get("/locations/{location_id}", response_model=Location, summary="Retrieve a single infrastructure location by ID")
@handle_service_errors
def read_location(location_id: int, db: Session = Depends(get_db_session)) -> None:
    """
    Retrieve a single infrastructure location by its unique ID.
    """
    return infrastructure_service.get_location(db, location_id)

@router.put("/locations/{location_id}", response_model=Location, summary="Update an existing infrastructure location")
@handle_service_errors
def update_location(location_id: int, location: LocationUpdate, db: Session = Depends(get_db_session)) -> None:
    """
    Update an existing infrastructure location's details.
    """
    return infrastructure_service.update_location(db, location_id, location)

@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an infrastructure location")
@handle_service_errors
def delete_location(location_id: int, db: Session = Depends(get_db_session)) -> None:
    """
    Delete an infrastructure location by its unique ID. Fails if components are linked.
    """
    infrastructure_service.delete_location(db, location_id)
    return

# --- Status Endpoints ---

@router.post("/statuses", response_model=Status, status_code=status.HTTP_201_CREATED, summary="Create a new component status")
@handle_service_errors
def create_status(status_in: StatusCreate, db: Session = Depends(get_db_session)) -> None:
    """
    Create a new component status (e.g., Operational, Maintenance).
    """
    return infrastructure_service.create_status(db, status_in)

@router.get("/statuses", response_model=List[Status], summary="Retrieve a list of all component statuses")
@handle_service_errors
def read_statuses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db_session)) -> None:
    """
    Retrieve a list of all component statuses with optional pagination.
    """
    return infrastructure_service.get_statuses(db, skip=skip, limit=limit)

@router.get("/statuses/{status_id}", response_model=Status, summary="Retrieve a single component status by ID")
@handle_service_errors
def read_status(status_id: int, db: Session = Depends(get_db_session)) -> None:
    """
    Retrieve a single component status by its unique ID.
    """
    return infrastructure_service.get_status(db, status_id)

@router.put("/statuses/{status_id}", response_model=Status, summary="Update an existing component status")
@handle_service_errors
def update_status(status_id: int, status_in: StatusUpdate, db: Session = Depends(get_db_session)) -> None:
    """
    Update an existing component status's details.
    """
    return infrastructure_service.update_status(db, status_id, status_in)

@router.delete("/statuses/{status_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a component status")
@handle_service_errors
def delete_status(status_id: int, db: Session = Depends(get_db_session)) -> None:
    """
    Delete a component status by its unique ID. Fails if components are linked.
    """
    infrastructure_service.delete_status(db, status_id)
    return