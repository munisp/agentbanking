import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field

from . import models
from .config import get_db

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router Initialization ---
router = APIRouter(
    prefix="/models",
    tags=["Neural Network Models"],
    responses={404: {"description": "Not found"}},
)

# --- Business-Specific Schema for Inference ---
class InferenceRequest(BaseModel):
    """Schema for the data payload sent for model inference."""
    input_data: Dict[str, Any] = Field(..., description="Input features for the neural network model.")
    tenant_id: str = Field(..., description="The tenant ID for which the inference is being performed.")

class InferenceResponse(BaseModel):
    """Schema for the response returned after model inference."""
    model_id: int = Field(..., description="The ID of the model used for inference.")
    prediction: Any = Field(..., description="The prediction result from the model.")
    log_id: int = Field(..., description="The ID of the activity log entry created for this inference.")


# --- Helper Functions (Inference Logic) ---

def _production_inference(model_path: str, input_data: Dict[str, Any]) -> Any:
    """
    Loads the model and performs inference.
    In a real application, this would involve loading the model artifact
    from `model_path` and running the prediction.
    """
    logger.info(f"Mock inference on model at {model_path} with data: {input_data}")
    # Simple production logic: return a fixed result or a result based on input
    if "feature_a" in input_data and input_data["feature_a"] > 10:
        return {"score": 0.95, "class": "fraud"}
    return {"score": 0.05, "class": "safe"}


def _log_activity(db: Session, model_id: int, activity_type: str, details: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None) -> models.ActivityLog:
    """Creates an activity log entry."""
    log_entry = models.ActivityLog(
        model_id=model_id,
        activity_type=activity_type,
        details=str(details) if details else None,
        user_id=user_id,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.NeuralNetworkModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Neural Network Model entry",
    description="Registers a new neural network model artifact and its configuration in the database.",
)
def create_model(
    model_in: models.NeuralNetworkModelCreate, db: Session = Depends(get_db)
):
    """
    Creates a new Neural Network Model entry in the database.

    Raises:
        HTTPException 409: If a model with the same tenant_id and name already exists.
    """
    logger.info(f"Attempting to create new model: {model_in.name} for tenant {model_in.tenant_id}")
    try:
        db_model = models.NeuralNetworkModel(**model_in.model_dump())
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        _log_activity(db, db_model.id, "CREATE", {"name": db_model.name})
        logger.info(f"Successfully created model with ID: {db_model.id}")
        return db_model
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model with name '{model_in.name}' already exists for tenant '{model_in.tenant_id}'.",
        )
    except Exception as e:
        logger.error(f"Error creating model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during model creation.",
        )


@router.get(
    "/{model_id}",
    response_model=models.NeuralNetworkModelResponse,
    summary="Retrieve a Neural Network Model by ID",
    description="Fetches the details and activity logs for a specific model.",
)
def read_model(model_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a Neural Network Model by its ID.

    Raises:
        HTTPException 404: If the model is not found.
    """
    db_model = (
        db.query(models.NeuralNetworkModel)
        .filter(models.NeuralNetworkModel.id == model_id)
        .first()
    )
    if db_model is None:
        logger.warning(f"Model with ID {model_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
        )
    return db_model


@router.get(
    "/",
    response_model=List[models.NeuralNetworkModelResponse],
    summary="List all Neural Network Models",
    description="Retrieves a list of all registered models, with optional filtering by tenant ID and pagination.",
)
def list_models(
    tenant_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Lists Neural Network Models, optionally filtered by tenant_id.
    """
    query = db.query(models.NeuralNetworkModel)
    if tenant_id:
        query = query.filter(models.NeuralNetworkModel.tenant_id == tenant_id)

    models_list = query.offset(skip).limit(limit).all()
    return models_list


@router.patch(
    "/{model_id}",
    response_model=models.NeuralNetworkModelResponse,
    summary="Update an existing Neural Network Model",
    description="Updates one or more fields of an existing model entry.",
)
def update_model(
    model_id: int,
    model_in: models.NeuralNetworkModelUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing Neural Network Model.

    Raises:
        HTTPException 404: If the model is not found.
    """
    db_model = read_model(model_id, db)  # Reuses read_model for existence check
    update_data = model_in.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_model, key, value)

    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    _log_activity(db, db_model.id, "UPDATE", update_data)
    logger.info(f"Successfully updated model with ID: {model_id}")
    return db_model


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Neural Network Model",
    description="Deletes a model entry and its associated activity logs.",
)
def delete_model(model_id: int, db: Session = Depends(get_db)):
    """
    Deletes a Neural Network Model and its associated activity logs.

    Raises:
        HTTPException 404: If the model is not found.
    """
    db_model = read_model(model_id, db)  # Reuses read_model for existence check

    # Delete associated activity logs first
    db.query(models.ActivityLog).filter(
        models.ActivityLog.model_id == model_id
    ).delete()

    # Delete the model
    db.delete(db_model)
    db.commit()
    logger.info(f"Successfully deleted model and logs for ID: {model_id}")
    return {"ok": True}


# --- Business-Specific Endpoint ---

@router.post(
    "/{model_id}/infer",
    response_model=InferenceResponse,
    summary="Perform inference using a deployed model",
    description="Submits input data to the specified model for prediction and logs the activity.",
)
def perform_inference(
    model_id: int,
    request: InferenceRequest,
    db: Session = Depends(get_db),
):
    """
    Performs a prediction using the specified model.

    The model is identified by `model_id`. The actual inference logic is productioned
    but demonstrates the flow: retrieve model, check status, perform inference,
    and log the activity.

    Raises:
        HTTPException 404: If the model is not found.
        HTTPException 400: If the model is not active.
    """
    db_model = read_model(model_id, db)  # Check if model exists

    if not db_model.is_active:
        logger.warning(f"Inference requested for inactive model ID: {model_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model ID {model_id} is not currently active for inference.",
        )

    # 1. Perform the actual inference (productioned)
    prediction = _production_inference(db_model.model_path, request.input_data)

    # 2. Log the inference activity
    log_details = {
        "input_summary": list(request.input_data.keys()),
        "prediction": prediction,
        "tenant_id": request.tenant_id,
    }
    log_entry = _log_activity(
        db,
        model_id,
        "INFERENCE",
        log_details,
        user_id=f"tenant:{request.tenant_id}" # Example user/system ID
    )

    logger.info(f"Inference successful for model ID {model_id}. Prediction: {prediction}")

    return InferenceResponse(
        model_id=model_id,
        prediction=prediction,
        log_id=log_entry.id
    )
