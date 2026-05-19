import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from config import get_db
from models import (
    MLModel, MLModelActivityLog, MLModelCreate, MLModelUpdate, 
    MLModelResponse, MLModelActivityLogResponse, ModelStatus, LogAction
)

# --- Configuration and Logging ---

# In a real application, logging would be configured more globally
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router Initialization ---

router = APIRouter(
    prefix="/ai-ml-services/models",
    tags=["AI/ML Models"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def log_activity(db: Session, model_id: uuid.UUID, action: LogAction, user_id: Optional[uuid.UUID] = None, details: Optional[str] = None):
    """Creates an activity log entry for a model action."""
    log_entry = MLModelActivityLog(
        model_id=model_id,
        action=action,
        user_id=user_id,
        details=details
    )
    db.add(log_entry)
    # Note: The log entry is committed with the main transaction in the endpoint, 
    # or separately if needed. Here, we rely on the endpoint's commit.

# --- CRUD Endpoints for MLModel ---

@router.post(
    "/", 
    response_model=MLModelResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Machine Learning Model"
)
def create_model(model_in: MLModelCreate, db: Session = Depends(get_db)):
    """
    Registers a new Machine Learning Model in the system.
    
    The model is initially set to 'Training' status. A unique constraint 
    is enforced on the combination of `tenant_id`, `name`, and `version`.
    """
    try:
        db_model = MLModel(**model_in.model_dump())
        db.add(db_model)
        
        # Log the creation activity
        log_activity(db, db_model.id, LogAction.CREATE, details=f"Model created with initial status: {db_model.status.value}")
        
        db.commit()
        db.refresh(db_model)
        logger.info(f"Model created: {db_model.id} for tenant {db_model.tenant_id}")
        return db_model
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A model with this tenant_id, name, and version already exists."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during model creation."
        )

@router.get(
    "/{model_id}", 
    response_model=MLModelResponse,
    summary="Retrieve a Machine Learning Model by ID"
)
def read_model(model_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves the details of a specific Machine Learning Model using its unique ID.
    """
    db_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if db_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"MLModel with ID {model_id} not found"
        )
    return db_model

@router.get(
    "/", 
    response_model=List[MLModelResponse],
    summary="List all Machine Learning Models with filtering"
)
def list_models(
    tenant_id: Optional[uuid.UUID] = Query(None, description="Filter by tenant ID"),
    status: Optional[ModelStatus] = Query(None, description="Filter by model status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of Machine Learning Models, with optional filtering 
    by tenant ID, status, and active flag. Supports pagination.
    """
    query = db.query(MLModel)
    
    if tenant_id:
        query = query.filter(MLModel.tenant_id == tenant_id)
    if status:
        query = query.filter(MLModel.status == status)
    if is_active is not None:
        query = query.filter(MLModel.is_active == is_active)
        
    models = query.offset(skip).limit(limit).all()
    return models

@router.patch(
    "/{model_id}", 
    response_model=MLModelResponse,
    summary="Update an existing Machine Learning Model"
)
def update_model(model_id: uuid.UUID, model_in: MLModelUpdate, db: Session = Depends(get_db)):
    """
    Updates the details of an existing Machine Learning Model.
    Only provided fields will be updated.
    """
    db_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if db_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"MLModel with ID {model_id} not found"
        )

    update_data = model_in.model_dump(exclude_unset=True)
    
    # Check for integrity violation before applying changes
    if 'name' in update_data or 'version' in update_data:
        # Check if the new combination of tenant_id, name, and version already exists for another model
        existing_model = db.query(MLModel).filter(
            MLModel.tenant_id == db_model.tenant_id,
            MLModel.name == update_data.get('name', db_model.name),
            MLModel.version == update_data.get('version', db_model.version),
            MLModel.id != model_id
        ).first()
        if existing_model:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The updated combination of name and version already exists for this tenant."
            )

    for key, value in update_data.items():
        setattr(db_model, key, value)

    try:
        # Log the update activity
        log_activity(db, db_model.id, LogAction.UPDATE, details=f"Model updated with fields: {list(update_data.keys())}")
        
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        logger.info(f"Model updated: {db_model.id}")
        return db_model
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integrity error during update (e.g., unique constraint violation)."
        )

@router.delete(
    "/{model_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Machine Learning Model"
)
def delete_model(model_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes a Machine Learning Model and all associated activity logs.
    """
    db_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if db_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"MLModel with ID {model_id} not found"
        )

    # Activity logs are set to cascade delete, but we can log the deletion itself
    log_activity(db, model_id, LogAction.ARCHIVE, details="Model marked for deletion.")
    
    db.delete(db_model)
    db.commit()
    logger.info(f"Model deleted: {model_id}")
    return 

# --- Business-Specific Endpoints ---

@router.post(
    "/{model_id}/deploy",
    response_model=MLModelResponse,
    summary="Deploy a Machine Learning Model"
)
def deploy_model(model_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Marks a model as 'Deployed' and computes the deployment process.
    This is a critical business operation.
    """
    db_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if db_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"MLModel with ID {model_id} not found"
        )
        
    if db_model.status == ModelStatus.DEPLOYED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model is already deployed."
        )

    # Simulate deployment logic (e.g., calling an external deployment service)
    # For this implementation, we just update the status
    db_model.status = ModelStatus.DEPLOYED
    db_model.is_active = True
    
    log_activity(db, db_model.id, LogAction.DEPLOY, details="Model deployment initiated and status updated to DEPLOYED.")
    
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    logger.info(f"Model deployed: {db_model.id}")
    return db_model

@router.post(
    "/{model_id}/score",
    summary="Simulate scoring a transaction with the model"
)
def score_transaction(model_id: uuid.UUID, transaction_data: dict, db: Session = Depends(get_db)):
    """
    Executes using the deployed model to score a transaction.
    The actual scoring logic would be complex, involving model loading and inference.
    """
    db_model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if db_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"MLModel with ID {model_id} not found"
        )
        
    if db_model.status != ModelStatus.DEPLOYED or not db_model.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model is not deployed or is inactive and cannot be used for scoring."
        )

    # --- Simulated Scoring Logic ---
    # In a real system, this would involve:
    # 1. Loading the model artifact from `db_model.model_uri`.
    # 2. Preprocessing `transaction_data`.
    # 3. Running inference.
    
    # Simple simulation:
    import random
    score = random.uniform(0.0, 1.0)
    is_fraud = score > 0.85
    
    log_activity(db, db_model.id, LogAction.SCORE, details=f"Transaction scored. Score: {score:.4f}, Fraud: {is_fraud}")
    
    db.commit() # Commit the log entry
    
    return {
        "model_id": model_id,
        "score": score,
        "prediction": "FRAUD" if is_fraud else "NOT_FRAUD",
        "model_version": db_model.version,
        "input_data_hash": hash(str(transaction_data)) # Simple way to reference input
    }

# --- Activity Log Endpoints ---

@router.get(
    "/{model_id}/logs",
    response_model=List[MLModelActivityLogResponse],
    summary="Retrieve activity logs for a specific model"
)
def get_model_logs(
    model_id: uuid.UUID, 
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieves the chronological activity log for a given Machine Learning Model.
    """
    # Check if model exists first
    if not db.query(MLModel).filter(MLModel.id == model_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"MLModel with ID {model_id} not found"
        )
        
    logs = db.query(MLModelActivityLog).filter(MLModelActivityLog.model_id == model_id)\
               .order_by(MLModelActivityLog.timestamp.desc())\
               .offset(skip).limit(limit).all()
               
    return logs
