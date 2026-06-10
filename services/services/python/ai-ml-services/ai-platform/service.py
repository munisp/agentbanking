from fastapi import HTTPException, status

class NotFoundException(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class AlreadyExistsException(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class ServiceException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> None:
        super().__init__(status_code=status_code, detail=detail)

# --- End of exceptions.py content ---

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from models import Model, Experiment
from schemas import ModelCreate, ModelUpdate, ExperimentCreate, ExperimentUpdate
# from exceptions import NotFoundException, AlreadyExistsException # Already defined above
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AIPlatformService:
    """
    Business logic layer for the AI Platform service.
    Handles CRUD operations for Models and Experiments with proper error handling and transaction management.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Model Operations ---

    def create_model(self, model_in: ModelCreate) -> Model:
        """Creates a new Model."""
        logger.info(f"Attempting to create model: {model_in.name} v{model_in.version}")
        
        # Check for existing model with same name and version
        existing_model = self.db.query(Model).filter(
            Model.name == model_in.name,
            Model.version == model_in.version
        ).first()

        if existing_model:
            raise AlreadyExistsException(
                detail=f"Model with name '{model_in.name}' and version '{model_in.version}' already exists."
            )

        db_model = Model(**model_in.model_dump())
        
        try:
            self.db.add(db_model)
            self.db.commit()
            self.db.refresh(db_model)
            logger.info(f"Successfully created model: {db_model.id}")
            return db_model
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during model creation: {e}")
            raise AlreadyExistsException(
                detail=f"Model with name '{model_in.name}' and version '{model_in.version}' already exists (Integrity Error)."
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during model creation: {e}")
            raise

    def get_model(self, model_id: int) -> Model:
        """Retrieves a Model by ID."""
        model = self.db.query(Model).filter(Model.id == model_id).first()
        if not model:
            raise NotFoundException(detail=f"Model with ID {model_id} not found.")
        return model

    def get_models(self, skip: int = 0, limit: int = 100) -> List[Model]:
        """Retrieves a list of Models."""
        return self.db.query(Model).offset(skip).limit(limit).all()

    def update_model(self, model_id: int, model_in: ModelUpdate) -> Model:
        """Updates an existing Model."""
        db_model = self.get_model(model_id) # Uses get_model to check for existence
        
        update_data = model_in.model_dump(exclude_unset=True)
        
        # Check for unique constraint violation if name or version is being updated
        if 'name' in update_data or 'version' in update_data:
            new_name = update_data.get('name', db_model.name)
            new_version = update_data.get('version', db_model.version)
            
            existing_model = self.db.query(Model).filter(
                Model.name == new_name,
                Model.version == new_version,
                Model.id != model_id
            ).first()
            
            if existing_model:
                raise AlreadyExistsException(
                    detail=f"Another model with name '{new_name}' and version '{new_version}' already exists."
                )

        for key, value in update_data.items():
            setattr(db_model, key, value)
        
        try:
            self.db.add(db_model)
            self.db.commit()
            self.db.refresh(db_model)
            logger.info(f"Successfully updated model: {model_id}")
            return db_model
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during model update: {e}")
            raise

    def delete_model(self, model_id: int) -> Model:
        """Deletes a Model by ID."""
        db_model = self.get_model(model_id) # Uses get_model to check for existence
        
        try:
            self.db.delete(db_model)
            self.db.commit()
            logger.info(f"Successfully deleted model: {model_id}")
            return db_model
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during model deletion: {e}")
            raise

    # --- Experiment Operations ---

    def create_experiment(self, experiment_in: ExperimentCreate) -> Experiment:
        """Creates a new Experiment."""
        logger.info(f"Attempting to create experiment: {experiment_in.name}")
        
        if experiment_in.model_id:
            # Check if the linked model exists
            model = self.db.query(Model).filter(Model.id == experiment_in.model_id).first()
            if not model:
                raise NotFoundException(detail=f"Model with ID {experiment_in.model_id} not found. Cannot link experiment.")

        db_experiment = Experiment(**experiment_in.model_dump())
        
        try:
            self.db.add(db_experiment)
            self.db.commit()
            self.db.refresh(db_experiment)
            logger.info(f"Successfully created experiment: {db_experiment.id}")
            return db_experiment
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during experiment creation: {e}")
            raise

    def get_experiment(self, experiment_id: int) -> Experiment:
        """Retrieves an Experiment by ID."""
        experiment = self.db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            raise NotFoundException(detail=f"Experiment with ID {experiment_id} not found.")
        return experiment

    def get_experiments(self, skip: int = 0, limit: int = 100) -> List[Experiment]:
        """Retrieves a list of Experiments."""
        return self.db.query(Experiment).offset(skip).limit(limit).all()

    def update_experiment(self, experiment_id: int, experiment_in: ExperimentUpdate) -> Experiment:
        """Updates an existing Experiment."""
        db_experiment = self.get_experiment(experiment_id) # Uses get_experiment to check for existence
        
        update_data = experiment_in.model_dump(exclude_unset=True)
        
        if 'model_id' in update_data and update_data['model_id'] is not None:
            # Check if the linked model exists
            model = self.db.query(Model).filter(Model.id == update_data['model_id']).first()
            if not model:
                raise NotFoundException(detail=f"Model with ID {update_data['model_id']} not found. Cannot link experiment.")

        for key, value in update_data.items():
            setattr(db_experiment, key, value)
        
        try:
            self.db.add(db_experiment)
            self.db.commit()
            self.db.refresh(db_experiment)
            logger.info(f"Successfully updated experiment: {experiment_id}")
            return db_experiment
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during experiment update: {e}")
            raise

    def delete_experiment(self, experiment_id: int) -> Experiment:
        """Deletes an Experiment by ID."""
        db_experiment = self.get_experiment(experiment_id) # Uses get_experiment to check for existence
        
        try:
            self.db.delete(db_experiment)
            self.db.commit()
            logger.info(f"Successfully deleted experiment: {experiment_id}")
            return db_experiment
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during experiment deletion: {e}")
            raise
