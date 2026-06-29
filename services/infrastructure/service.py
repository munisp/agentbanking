import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import ComponentModel, LocationModel, StatusModel
from schemas import (
    ComponentCreate,
    ComponentUpdate,
    LocationCreate,
    LocationUpdate,
    StatusCreate,
    StatusUpdate,
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Custom Exceptions ---

class NotFoundError(Exception):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, resource_id: int) -> None:
        self.resource_name = resource_name
        self.resource_id = resource_id
        super().__init__(f"{resource_name} with ID {resource_id} not found.")

class ConflictError(Exception):
    """Raised when a resource creation or update violates a unique constraint."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

# --- Infrastructure Service ---

class InfrastructureService:
    """
    Business logic layer for managing infrastructure components, locations, and statuses.
    """

    # --- Location Operations ---

    def create_location(self, db: Session, location_in: LocationCreate) -> LocationModel:
        logger.info(f"Attempting to create new location: {location_in.name}")
        try:
            db_location = LocationModel(**location_in.model_dump())
            db.add(db_location)
            db.commit()
            db.refresh(db_location)
            logger.info(f"Successfully created location with ID: {db_location.id}")
            return db_location
        except IntegrityError:
            db.rollback()
            raise ConflictError(f"Location with name '{location_in.name}' already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating location: {e}")
            raise

    def get_location(self, db: Session, location_id: int) -> LocationModel:
        db_location = db.query(LocationModel).filter(LocationModel.id == location_id).first()
        if not db_location:
            raise NotFoundError("Location", location_id)
        return db_location

    def get_locations(self, db: Session, skip: int = 0, limit: int = 100) -> List[LocationModel]:
        return db.query(LocationModel).offset(skip).limit(limit).all()

    def update_location(self, db: Session, location_id: int, location_in: LocationUpdate) -> LocationModel:
        db_location = self.get_location(db, location_id)
        logger.info(f"Attempting to update location ID {location_id}")
        
        update_data = location_in.model_dump(exclude_unset=True)
        
        # Check for name conflict if name is being updated
        if 'name' in update_data and update_data['name'] != db_location.name:
            existing_location = db.query(LocationModel).filter(LocationModel.name == update_data['name']).first()
            if existing_location and existing_location.id != location_id:
                raise ConflictError(f"Location with name '{update_data['name']}' already exists.")

        for key, value in update_data.items():
            setattr(db_location, key, value)
        
        try:
            db.add(db_location)
            db.commit()
            db.refresh(db_location)
            logger.info(f"Successfully updated location ID {location_id}")
            return db_location
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating location ID {location_id}: {e}")
            raise

    def delete_location(self, db: Session, location_id: int) -> Dict[str, Any]:
        db_location = self.get_location(db, location_id)
        
        # Check if any components are linked to this location
        if db.query(ComponentModel).filter(ComponentModel.location_id == location_id).first():
            raise ConflictError(f"Location ID {location_id} cannot be deleted because it is linked to one or more components.")

        logger.info(f"Attempting to delete location ID {location_id}")
        db.delete(db_location)
        db.commit()
        logger.info(f"Successfully deleted location ID {location_id}")
        return {"message": f"Location ID {location_id} deleted successfully."}

    # --- Status Operations ---

    def create_status(self, db: Session, status_in: StatusCreate) -> StatusModel:
        logger.info(f"Attempting to create new status: {status_in.name}")
        try:
            db_status = StatusModel(**status_in.model_dump())
            db.add(db_status)
            db.commit()
            db.refresh(db_status)
            logger.info(f"Successfully created status with ID: {db_status.id}")
            return db_status
        except IntegrityError:
            db.rollback()
            raise ConflictError(f"Status with name '{status_in.name}' already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating status: {e}")
            raise

    def get_status(self, db: Session, status_id: int) -> StatusModel:
        db_status = db.query(StatusModel).filter(StatusModel.id == status_id).first()
        if not db_status:
            raise NotFoundError("Status", status_id)
        return db_status

    def get_statuses(self, db: Session, skip: int = 0, limit: int = 100) -> List[StatusModel]:
        return db.query(StatusModel).offset(skip).limit(limit).all()

    def update_status(self, db: Session, status_id: int, status_in: StatusUpdate) -> StatusModel:
        db_status = self.get_status(db, status_id)
        logger.info(f"Attempting to update status ID {status_id}")
        
        update_data = status_in.model_dump(exclude_unset=True)
        
        # Check for name conflict if name is being updated
        if 'name' in update_data and update_data['name'] != db_status.name:
            existing_status = db.query(StatusModel).filter(StatusModel.name == update_data['name']).first()
            if existing_status and existing_status.id != status_id:
                raise ConflictError(f"Status with name '{update_data['name']}' already exists.")

        for key, value in update_data.items():
            setattr(db_status, key, value)
        
        try:
            db.add(db_status)
            db.commit()
            db.refresh(db_status)
            logger.info(f"Successfully updated status ID {status_id}")
            return db_status
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating status ID {status_id}: {e}")
            raise

    def delete_status(self, db: Session, status_id: int) -> Dict[str, Any]:
        db_status = self.get_status(db, status_id)
        
        # Check if any components are linked to this status
        if db.query(ComponentModel).filter(ComponentModel.status_id == status_id).first():
            raise ConflictError(f"Status ID {status_id} cannot be deleted because it is linked to one or more components.")

        logger.info(f"Attempting to delete status ID {status_id}")
        db.delete(db_status)
        db.commit()
        logger.info(f"Successfully deleted status ID {status_id}")
        return {"message": f"Status ID {status_id} deleted successfully."}

    # --- Component Operations ---

    def create_component(self, db: Session, component_in: ComponentCreate) -> ComponentModel:
        logger.info(f"Attempting to create new component: {component_in.name}")
        
        # Pre-check existence of foreign keys
        self.get_location(db, component_in.location_id)
        self.get_status(db, component_in.status_id)

        try:
            db_component = ComponentModel(**component_in.model_dump())
            db.add(db_component)
            db.commit()
            db.refresh(db_component)
            logger.info(f"Successfully created component with ID: {db_component.id}")
            return db_component
        except IntegrityError as e:
            db.rollback()
            # Handle the specific unique constraint for component name + location_id
            if "uq_component_name_location" in str(e):
                raise ConflictError(f"Component with name '{component_in.name}' already exists in location ID {component_in.location_id}.")
            # Handle unique constraint for serial_number
            elif "serial_number" in str(e):
                raise ConflictError(f"Component with serial number '{component_in.serial_number}' already exists.")
            else:
                raise ConflictError(f"A database integrity error occurred: {e}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating component: {e}")
            raise

    def get_component(self, db: Session, component_id: int) -> ComponentModel:
        db_component = db.query(ComponentModel).filter(ComponentModel.id == component_id).first()
        if not db_component:
            raise NotFoundError("Component", component_id)
        return db_component

    def get_components(self, db: Session, skip: int = 0, limit: int = 100) -> List[ComponentModel]:
        return db.query(ComponentModel).offset(skip).limit(limit).all()

    def update_component(self, db: Session, component_id: int, component_in: ComponentUpdate) -> ComponentModel:
        db_component = self.get_component(db, component_id)
        logger.info(f"Attempting to update component ID {component_id}")
        
        update_data = component_in.model_dump(exclude_unset=True)
        
        # Pre-check existence of foreign keys if they are being updated
        if 'location_id' in update_data:
            self.get_location(db, update_data['location_id'])
        if 'status_id' in update_data:
            self.get_status(db, update_data['status_id'])

        for key, value in update_data.items():
            setattr(db_component, key, value)
        
        try:
            db.add(db_component)
            db.commit()
            db.refresh(db_component)
            logger.info(f"Successfully updated component ID {component_id}")
            return db_component
        except IntegrityError as e:
            db.rollback()
            # Handle the specific unique constraint for component name + location_id
            if "uq_component_name_location" in str(e):
                name = update_data.get('name', db_component.name)
                location_id = update_data.get('location_id', db_component.location_id)
                raise ConflictError(f"Component with name '{name}' already exists in location ID {location_id}.")
            # Handle unique constraint for serial_number
            elif "serial_number" in str(e):
                raise ConflictError(f"Component with serial number '{update_data.get('serial_number')}' already exists.")
            else:
                raise ConflictError(f"A database integrity error occurred: {e}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating component ID {component_id}: {e}")
            raise

    def delete_component(self, db: Session, component_id: int) -> Dict[str, Any]:
        db_component = self.get_component(db, component_id)
        logger.info(f"Attempting to delete component ID {component_id}")
        db.delete(db_component)
        db.commit()
        logger.info(f"Successfully deleted component ID {component_id}")
        return {"message": f"Component ID {component_id} deleted successfully."}

# Instantiate the service
infrastructure_service = InfrastructureService()