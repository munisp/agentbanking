import uuid
import logging
import pickle
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


# --- Model artifact loading (required for scoring) ---

def _load_artifact(model_uri: str):
    """
    Load a trained model artifact from disk (joblib or pickle).
    Returns (estimator, feature_names_or_none). Raises RuntimeError on any
    failure — scoring must fail loud, never fabricate a score.
    """
    if not model_uri:
        raise RuntimeError("model has no model_uri artifact configured")
    try:
        try:
            import joblib  # type: ignore
            artifact = joblib.load(model_uri)
        except ImportError:
            with open(model_uri, "rb") as fh:
                artifact = pickle.load(fh)
    except Exception as exc:
        raise RuntimeError(f"failed to load model artifact '{model_uri}': {exc}")

    feature_names = None
    estimator = artifact
    if isinstance(artifact, dict):
        estimator = artifact.get("model")
        feature_names = artifact.get("feature_names")
    if estimator is None or not hasattr(estimator, "predict"):
        raise RuntimeError("model artifact does not provide a predict() method")
    return estimator, feature_names


def _build_feature_vector(transaction_data: dict, feature_names: Optional[List[str]]):
    """Build a numeric feature vector from the transaction payload."""
    if feature_names:
        missing = [f for f in feature_names if f not in transaction_data]
        if missing:
            raise RuntimeError(f"transaction is missing required features: {missing}")
        return [float(transaction_data[f]) for f in feature_names]
    numeric_keys = sorted(
        k for k, v in transaction_data.items() if isinstance(v, (int, float))
    )
    if not numeric_keys:
        raise RuntimeError("transaction contains no numeric features to score")
    return [float(transaction_data[k]) for k in numeric_keys]

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
    logger.info(f"Model deleted: {db_model.id}")
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
    summary="Score a transaction with the model's trained artifact"
)
def score_transaction(model_id: uuid.UUID, transaction_data: dict, db: Session = Depends(get_db)):
    """
    Scores a transaction by loading the model's trained artifact from
    `model_uri` and running real inference.

    Fail-loud contract:
      - unknown model                       -> 404
      - model not deployed / inactive       -> 400
      - artifact missing/unloadable         -> 503
      - malformed transaction features      -> 422
    A random or hardcoded score is NEVER returned.
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

    try:
        estimator, feature_names = _load_artifact(db_model.model_uri)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    try:
        vector = _build_feature_vector(transaction_data, feature_names)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    try:
        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba([vector])[0]
            score = float(max(proba))
            positive_idx = int(list(getattr(estimator, "classes_", [0, 1])).index(1)) \
                if 1 in list(getattr(estimator, "classes_", [])) else len(proba) - 1
            positive_score = float(proba[positive_idx])
        else:
            prediction_raw = estimator.predict([vector])[0]
            score = None
            positive_score = float(prediction_raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"model inference failed: {exc}",
        )

    is_fraud = positive_score > 0.5

    log_activity(db, db_model.id, LogAction.SCORE, details=f"Transaction scored. Score: {positive_score:.4f}, Fraud: {is_fraud}")

    db.commit()  # Commit the log entry

    return {
        "model_id": model_id,
        "score": positive_score,
        "confidence": score,
        "prediction": "FRAUD" if is_fraud else "NOT_FRAUD",
        "model_version": db_model.version,
        "scoring_method": "model_artifact",
        "input_data_hash": hash(str(transaction_data))  # Simple way to reference input
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
