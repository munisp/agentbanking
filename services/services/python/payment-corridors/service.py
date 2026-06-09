import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from . import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class NotFoundError(Exception):
    """Raised when a requested resource is not found."""
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(self.detail)

class ConflictError(Exception):
    """Raised when a resource creation or update conflicts with existing data (e.g., unique constraint violation)."""
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(self.detail)

# --- Helper Functions for Nested Entities ---

def _create_nested_fees(db: Session, corridor_id: int, fees: List[schemas.CorridorFeeCreate]) -> None:
    """Creates CorridorFee objects for a given corridor."""
    fee_models = []
    for fee_data in fees:
        fee_model = models.CorridorFee(**fee_data.model_dump(), corridor_id=corridor_id)
        fee_models.append(fee_model)
        db.add(fee_model)
    return fee_models

def _create_nested_limits(db: Session, corridor_id: int, limits: List[schemas.CorridorLimitCreate]) -> None:
    """Creates CorridorLimit objects for a given corridor."""
    limit_models = []
    for limit_data in limits:
        limit_model = models.CorridorLimit(**limit_data.model_dump(), corridor_id=corridor_id)
        limit_models.append(limit_model)
        db.add(limit_model)
    return limit_models

def _replace_nested_entities(db: Session, corridor_model: models.PaymentCorridor, data: schemas.PaymentCorridorUpdate) -> None:
    """Replaces nested fees and limits if provided in the update data."""
    
    # Replace Fees
    if data.fees is not None:
        # Delete existing fees
        for fee in corridor_model.fees:
            db.delete(fee)
        
        # Create new fees
        _create_nested_fees(db, corridor_model.id, data.fees)
        logger.info(f"Replaced fees for corridor ID {corridor_model.id}")

    # Replace Limits
    if data.limits is not None:
        # Delete existing limits
        for limit in corridor_model.limits:
            db.delete(limit)
        
        # Create new limits
        _create_nested_limits(db, corridor_model.id, data.limits)
        logger.info(f"Replaced limits for corridor ID {corridor_model.id}")


# --- Service Class ---

class PaymentCorridorService:
    """
    Business logic layer for managing PaymentCorridor entities.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_corridor(self, corridor_data: schemas.PaymentCorridorCreate) -> models.PaymentCorridor:
        """
        Creates a new PaymentCorridor along with its nested fees and limits.
        """
        logger.info(f"Attempting to create new corridor: {corridor_data.source_country_iso} to {corridor_data.destination_country_iso}")
        
        try:
            # 1. Create the main corridor model
            corridor_dict = corridor_data.model_dump(exclude={'fees', 'limits'})
            corridor_model = models.PaymentCorridor(**corridor_dict)
            self.db.add(corridor_model)
            self.db.flush() # Flush to get the ID for nested entities

            # 2. Create nested entities
            _create_nested_fees(self.db, corridor_model.id, corridor_data.fees)
            _create_nested_limits(self.db, corridor_model.id, corridor_data.limits)

            # 3. Commit transaction
            self.db.commit()
            self.db.refresh(corridor_model)
            logger.info(f"Successfully created corridor with ID: {corridor_model.id}")
            return corridor_model
        
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during corridor creation: {e}")
            # Check for unique constraint violation specifically
            if "uq_corridor_route" in str(e.orig):
                raise ConflictError(
                    f"A corridor already exists for the route: {corridor_data.source_country_iso}/{corridor_data.source_currency_iso} to {corridor_data.destination_country_iso}/{corridor_data.destination_currency_iso}"
                )
            elif "uq_corridor_limit_type" in str(e.orig):
                 raise ConflictError(
                    "Duplicate limit type found for the corridor. Each corridor can only have one of each limit type (TRANSACTION, DAILY, MONTHLY)."
                )
            raise ConflictError("Database integrity error occurred.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during corridor creation: {e}")
            raise

    def get_corridor(self, corridor_id: int) -> models.PaymentCorridor:
        """
        Retrieves a single PaymentCorridor by ID, eagerly loading fees and limits.
        """
        corridor = self.db.query(models.PaymentCorridor).options(
            joinedload(models.PaymentCorridor.fees),
            joinedload(models.PaymentCorridor.limits)
        ).filter(models.PaymentCorridor.id == corridor_id).first()
        
        if not corridor:
            logger.warning(f"Corridor with ID {corridor_id} not found.")
            raise NotFoundError(f"PaymentCorridor with ID {corridor_id} not found.")
        
        return corridor

    def get_all_corridors(self, skip: int = 0, limit: int = 100) -> List[models.PaymentCorridor]:
        """
        Retrieves a list of PaymentCorridors with pagination.
        """
        corridors = self.db.query(models.PaymentCorridor).options(
            joinedload(models.PaymentCorridor.fees),
            joinedload(models.PaymentCorridor.limits)
        ).offset(skip).limit(limit).all()
        
        return corridors

    def update_corridor(self, corridor_id: int, corridor_data: schemas.PaymentCorridorUpdate) -> models.PaymentCorridor:
        """
        Updates an existing PaymentCorridor. Handles nested fee/limit replacement if provided.
        """
        corridor_model = self.get_corridor(corridor_id) # Uses get_corridor for existence check and eager loading

        logger.info(f"Attempting to update corridor ID: {corridor_id}")

        try:
            # 1. Handle nested entity replacement (if provided)
            _replace_nested_entities(self.db, corridor_model, corridor_data)

            # 2. Update main corridor fields
            update_data = corridor_data.model_dump(exclude_unset=True, exclude={'fees', 'limits'})
            for key, value in update_data.items():
                setattr(corridor_model, key, value)

            # 3. Commit transaction
            self.db.add(corridor_model)
            self.db.commit()
            self.db.refresh(corridor_model)
            logger.info(f"Successfully updated corridor ID: {corridor_id}")
            return corridor_model
        
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during corridor update: {e}")
            # Check for unique constraint violation
            if "uq_corridor_route" in str(e.orig):
                raise ConflictError(
                    "Update failed: The new route configuration conflicts with an existing corridor."
                )
            elif "uq_corridor_limit_type" in str(e.orig):
                 raise ConflictError(
                    "Update failed: Duplicate limit type found in the new limits list."
                )
            raise ConflictError("Database integrity error occurred.")
        except NotFoundError:
            # Re-raise NotFoundError from get_corridor
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during corridor update: {e}")
            raise

    def delete_corridor(self, corridor_id: int) -> None:
        """
        Deletes a PaymentCorridor by ID. Nested entities are deleted via cascade.
        """
        corridor_model = self.get_corridor(corridor_id) # Uses get_corridor for existence check

        logger.info(f"Attempting to delete corridor ID: {corridor_id}")
        
        try:
            self.db.delete(corridor_model)
            self.db.commit()
            logger.info(f"Successfully deleted corridor ID: {corridor_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during corridor deletion: {e}")
            raise
