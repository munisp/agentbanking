import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
import schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class RouteException(Exception):
    """Base exception for route service errors."""
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class RouteNotFound(RouteException):
    """Raised when a route is not found."""
    def __init__(self, route_id: Optional[int] = None, service_name: Optional[str] = None) -> None:
        if route_id:
            message = f"Route with ID '{route_id}' not found."
        elif service_name:
            message = f"Route for service '{service_name}' not found."
        else:
            message = "Route not found."
        super().__init__(message, status_code=404)

class RouteConflict(RouteException):
    """Raised when a route creation or update conflicts with an existing route."""
    def __init__(self, field: str, value: str) -> None:
        message = f"Route conflict: A route with {field} '{value}' already exists."
        super().__init__(message, status_code=409)

# --- Service Layer ---
class RouteService:
    """
    Handles all business logic for API Gateway Route configuration.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_route(self, route_data: schemas.RouteCreate) -> models.Route:
        """
        Creates a new route configuration.
        """
        logger.info(f"Attempting to create new route for service: {route_data.service_name}")
        
        # Check for existing service_name or source_path_prefix
        if self.get_route_by_service_name(route_data.service_name):
            raise RouteConflict("service_name", route_data.service_name)
        if self.get_route_by_path_prefix(route_data.source_path_prefix):
            raise RouteConflict("source_path_prefix", route_data.source_path_prefix)

        db_route = models.Route(**route_data.model_dump())
        
        try:
            self.db.add(db_route)
            self.db.commit()
            self.db.refresh(db_route)
            logger.info(f"Successfully created route with ID: {db_route.id}")
            return db_route
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error during route creation: {e}")
            # This should be caught by the pre-checks, but serves as a fallback
            raise RouteConflict("unique constraint", "service_name or source_path_prefix")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during route creation: {e}")
            raise RouteException(f"Failed to create route: {e}")

    def get_route(self, route_id: int) -> models.Route:
        """
        Retrieves a single route by its ID.
        """
        db_route = self.db.query(models.Route).filter(models.Route.id == route_id).first()
        if not db_route:
            raise RouteNotFound(route_id=route_id)
        return db_route

    def get_route_by_service_name(self, service_name: str) -> Optional[models.Route]:
        """
        Retrieves a single route by its service name.
        """
        return self.db.query(models.Route).filter(models.Route.service_name == service_name).first()

    def get_route_by_path_prefix(self, path_prefix: str) -> Optional[models.Route]:
        """
        Retrieves a single route by its source path prefix.
        """
        return self.db.query(models.Route).filter(models.Route.source_path_prefix == path_prefix).first()

    def list_routes(self, skip: int = 0, limit: int = 100) -> List[models.Route]:
        """
        Lists all route configurations with pagination.
        """
        return self.db.query(models.Route).offset(skip).limit(limit).all()

    def update_route(self, route_id: int, route_data: schemas.RouteUpdate) -> models.Route:
        """
        Updates an existing route configuration.
        """
        logger.info(f"Attempting to update route with ID: {route_id}")
        db_route = self.get_route(route_id) # Will raise RouteNotFound if not found

        update_data = route_data.model_dump(exclude_unset=True)
        
        # Check for unique conflicts on service_name and source_path_prefix
        if 'service_name' in update_data and update_data['service_name'] != db_route.service_name:
            if self.get_route_by_service_name(update_data['service_name']):
                raise RouteConflict("service_name", update_data['service_name'])
        
        if 'source_path_prefix' in update_data and update_data['source_path_prefix'] != db_route.source_path_prefix:
            if self.get_route_by_path_prefix(update_data['source_path_prefix']):
                raise RouteConflict("source_path_prefix", update_data['source_path_prefix'])

        for key, value in update_data.items():
            setattr(db_route, key, value)

        try:
            self.db.add(db_route)
            self.db.commit()
            self.db.refresh(db_route)
            logger.info(f"Successfully updated route with ID: {route_id}")
            return db_route
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error during route update: {e}")
            raise RouteConflict("unique constraint", "service_name or source_path_prefix")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during route update: {e}")
            raise RouteException(f"Failed to update route: {e}")

    def delete_route(self, route_id: int) -> None:
        """
        Deletes a route configuration by its ID.
        """
        logger.info(f"Attempting to delete route with ID: {route_id}")
        db_route = self.get_route(route_id) # Will raise RouteNotFound if not found

        try:
            self.db.delete(db_route)
            self.db.commit()
            logger.info(f"Successfully deleted route with ID: {route_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during route deletion: {e}")
            raise RouteException(f"Failed to delete route: {e}")