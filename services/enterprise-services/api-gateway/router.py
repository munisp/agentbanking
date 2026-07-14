from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import schemas
import service
from database import get_db
from service import RouteService, RouteNotFound, RouteConflict, RouteException

# --- Router Initialization ---
router = APIRouter(
    prefix="/routes",
    tags=["routes"],
    responses={404: {"description": "Not found"}},
)

# --- Dependency for RouteService ---
def get_route_service(db: Session = Depends(get_db)) -> RouteService:
    """Provides a RouteService instance with a database session."""
    return RouteService(db)

# --- Exception Handler for Router ---
def handle_service_exception(e: RouteException):
    """Converts custom service exceptions into FastAPI HTTPExceptions."""
    raise HTTPException(status_code=e.status_code, detail=e.message)

# --- CRUD Operations ---

@router.post(
    "/", 
    response_model=schemas.RouteInDB, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API Gateway route configuration"
)
def create_route(
    route_data: schemas.RouteCreate, 
    route_service: RouteService = Depends(get_route_service)
):
    """
    Registers a new route configuration for a microservice.
    
    The `source_path_prefix` must be unique and will be used by the API Gateway
    to forward requests to the `target_url`.
    """
    try:
        return route_service.create_route(route_data)
    except (RouteConflict, RouteException) as e:
        handle_service_exception(e)

@router.get(
    "/", 
    response_model=List[schemas.RouteInDB],
    summary="List all API Gateway route configurations"
)
def list_routes(
    skip: int = 0, 
    limit: int = 100, 
    route_service: RouteService = Depends(get_route_service)
):
    """
    Retrieves a list of all configured routes with pagination.
    """
    return route_service.list_routes(skip=skip, limit=limit)

@router.get(
    "/{route_id}", 
    response_model=schemas.RouteInDB,
    summary="Get a specific route configuration by ID"
)
def get_route(
    route_id: int, 
    route_service: RouteService = Depends(get_route_service)
):
    """
    Retrieves a single route configuration using its unique ID.
    """
    try:
        return route_service.get_route(route_id)
    except RouteNotFound as e:
        handle_service_exception(e)

@router.put(
    "/{route_id}", 
    response_model=schemas.RouteInDB,
    summary="Update an existing route configuration"
)
def update_route(
    route_id: int, 
    route_data: schemas.RouteUpdate, 
    route_service: RouteService = Depends(get_route_service)
):
    """
    Updates the configuration for an existing route. Only fields provided in the request body will be updated.
    """
    try:
        return route_service.update_route(route_id, route_data)
    except (RouteNotFound, RouteConflict, RouteException) as e:
        handle_service_exception(e)

@router.delete(
    "/{route_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a route configuration"
)
def delete_route(
    route_id: int, 
    route_service: RouteService = Depends(get_route_service)
):
    """
    Deletes a route configuration permanently.
    """
    try:
        route_service.delete_route(route_id)
        return {"message": "Route deleted successfully"}
    except RouteNotFound as e:
        handle_service_exception(e)
    except RouteException as e:
        handle_service_exception(e)