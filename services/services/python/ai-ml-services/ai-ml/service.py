import logging
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import MLProject, MLModel, Prediction
from schemas import (
    MLProjectCreate, MLProjectUpdate,
    MLModelCreate, MLModelUpdate,
    PredictionCreate
)

# --- Custom Exceptions ---

class NotFoundError(Exception):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, resource_id: Any):
        self.resource_name = resource_name
        self.resource_id = resource_id
        super().__init__(f"{resource_name} with ID {resource_id} not found.")

class ConflictError(Exception):
    """Raised when a resource creation or update conflicts with existing data."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

# --- Logging Configuration ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Service Class ---

class AIMLService:
    """
    Business logic layer for the AI/ML Model Serving API.
    Handles CRUD operations and business rules for ML Projects, Models, and Predictions.
    """

    # --- MLProject Operations ---

    def create_project(self, db: Session, project_data: MLProjectCreate) -> MLProject:
        logger.info(f"Attempting to create new project: {project_data.name}")
        db_project = MLProject(**project_data.model_dump())
        try:
            db.add(db_project)
            db.commit()
            db.refresh(db_project)
            logger.info(f"Project created successfully with ID: {db_project.id}")
            return db_project
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating project {project_data.name}: {e}")
            raise ConflictError(f"Project with name '{project_data.name}' already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating project: {e}")
            raise

    def get_project(self, db: Session, project_id: int) -> MLProject:
        db_project = db.query(MLProject).filter(MLProject.id == project_id).first()
        if not db_project:
            raise NotFoundError("MLProject", project_id)
        return db_project

    def get_projects(self, db: Session, skip: int = 0, limit: int = 100) -> List[MLProject]:
        return db.query(MLProject).offset(skip).limit(limit).all()

    def update_project(self, db: Session, project_id: int, project_data: MLProjectUpdate) -> MLProject:
        db_project = self.get_project(db, project_id)
        logger.info(f"Attempting to update project ID: {project_id}")
        
        update_data = project_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_project, key, value)
        
        try:
            db.commit()
            db.refresh(db_project)
            logger.info(f"Project ID {project_id} updated successfully.")
            return db_project
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error updating project {project_id}: {e}")
            raise ConflictError(f"Project name '{project_data.name}' already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error updating project {project_id}: {e}")
            raise

    def delete_project(self, db: Session, project_id: int):
        db_project = self.get_project(db, project_id)
        logger.warning(f"Attempting to delete project ID: {project_id}. This will cascade to models and predictions.")
        db.delete(db_project)
        db.commit()
        logger.info(f"Project ID {project_id} deleted successfully.")

    # --- MLModel Operations ---

    def create_model(self, db: Session, model_data: MLModelCreate) -> MLModel:
        # Check if project exists
        self.get_project(db, model_data.project_id)
        
        logger.info(f"Attempting to create new model for project {model_data.project_id}: {model_data.name} v{model_data.version}")
        
        # Business rule: If is_current is True, set all other models in the project to is_current=False
        if model_data.is_current:
            db.query(MLModel).filter(
                MLModel.project_id == model_data.project_id,
                MLModel.is_current == True
            ).update({"is_current": False})
        
        db_model = MLModel(**model_data.model_dump())
        try:
            db.add(db_model)
            db.commit()
            db.refresh(db_model)
            logger.info(f"Model created successfully with ID: {db_model.id}")
            return db_model
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating model: {e}")
            raise ConflictError(f"Model with name '{model_data.name}' and version '{model_data.version}' already exists in project {model_data.project_id}.")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating model: {e}")
            raise

    def get_model(self, db: Session, model_id: int) -> MLModel:
        db_model = db.query(MLModel).filter(MLModel.id == model_id).first()
        if not db_model:
            raise NotFoundError("MLModel", model_id)
        return db_model

    def get_models_by_project(self, db: Session, project_id: int, skip: int = 0, limit: int = 100) -> List[MLModel]:
        # Check if project exists
        self.get_project(db, project_id)
        return db.query(MLModel).filter(MLModel.project_id == project_id).offset(skip).limit(limit).all()

    def get_current_model(self, db: Session, project_id: int) -> MLModel:
        db_model = db.query(MLModel).filter(
            MLModel.project_id == project_id,
            MLModel.is_current == True
        ).first()
        if not db_model:
            raise NotFoundError("Current MLModel", f"for project {project_id}")
        return db_model

    def update_model(self, db: Session, model_id: int, model_data: MLModelUpdate) -> MLModel:
        db_model = self.get_model(db, model_id)
        logger.info(f"Attempting to update model ID: {model_id}")
        
        update_data = model_data.model_dump(exclude_unset=True)
        
        # Business rule: If is_current is being set to True, set all other models in the project to is_current=False
        if update_data.get("is_current") is True:
            db.query(MLModel).filter(
                MLModel.project_id == db_model.project_id,
                MLModel.is_current == True,
                MLModel.id != model_id
            ).update({"is_current": False})
        
        for key, value in update_data.items():
            setattr(db_model, key, value)
        
        try:
            db.commit()
            db.refresh(db_model)
            logger.info(f"Model ID {model_id} updated successfully.")
            return db_model
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error updating model {model_id}: {e}")
            raise ConflictError(f"Model name/version conflict in project {db_model.project_id}.")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error updating model {model_id}: {e}")
            raise

    def delete_model(self, db: Session, model_id: int):
        db_model = self.get_model(db, model_id)
        logger.warning(f"Attempting to delete model ID: {model_id}. This will cascade to predictions.")
        db.delete(db_model)
        db.commit()
        logger.info(f"Model ID {model_id} deleted successfully.")

    # --- Prediction Operations (Inference) ---

    def create_prediction(self, db: Session, prediction_data: PredictionCreate) -> Prediction:
        # Check if project and model exist
        self.get_project(db, prediction_data.project_id)
        self.get_model(db, prediction_data.model_id)
        
        logger.info(f"Attempting to create new prediction for project {prediction_data.project_id} and model {prediction_data.model_id}")
        
        db_prediction = Prediction(**prediction_data.model_dump())
        try:
            db.add(db_prediction)
            db.commit()
            db.refresh(db_prediction)
            logger.info(f"Prediction created successfully with ID: {db_prediction.id}")
            return db_prediction
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating prediction: {e}")
            raise

    def get_prediction(self, db: Session, prediction_id: int) -> Prediction:
        db_prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not db_prediction:
            raise NotFoundError("Prediction", prediction_id)
        return db_prediction

    def get_predictions_by_project(self, db: Session, project_id: int, skip: int = 0, limit: int = 100) -> List[Prediction]:
        # Check if project exists
        self.get_project(db, project_id)
        return db.query(Prediction).filter(Prediction.project_id == project_id).offset(skip).limit(limit).all()

    def get_predictions_by_model(self, db: Session, model_id: int, skip: int = 0, limit: int = 100) -> List[Prediction]:
        # Check if model exists
        self.get_model(db, model_id)
        return db.query(Prediction).filter(Prediction.model_id == model_id).offset(skip).limit(limit).all()

# Instantiate the service
ai_ml_service = AIMLService()
