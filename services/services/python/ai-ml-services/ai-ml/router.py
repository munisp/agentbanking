from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import DB_DEPENDENCY
from service import ai_ml_service, NotFoundError, ConflictError
from schemas import (
    MLProject, MLProjectCreate, MLProjectUpdate,
    MLModel, MLModelCreate, MLModelUpdate,
    Prediction, PredictionCreate
)

router = APIRouter(
    prefix="/api/v1",
    tags=["ai-ml"],
)

# --- Exception Handlers ---

def handle_service_errors(e: Exception):
    if isinstance(e, NotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    elif isinstance(e, ConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    else:
        # Re-raise unexpected exceptions
        raise e

# --- MLProject Endpoints ---

@router.post("/projects", response_model=MLProject, status_code=status.HTTP_201_CREATED, summary="Create a new ML Project")
def create_project(project: MLProjectCreate, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.create_project(db, project)
    except Exception as e:
        handle_service_errors(e)

@router.get("/projects", response_model=List[MLProject], summary="List all ML Projects")
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(DB_DEPENDENCY)):
    return ai_ml_service.get_projects(db, skip=skip, limit=limit)

@router.get("/projects/{project_id}", response_model=MLProject, summary="Get a specific ML Project")
def get_project(project_id: int, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_project(db, project_id)
    except Exception as e:
        handle_service_errors(e)

@router.put("/projects/{project_id}", response_model=MLProject, summary="Update an ML Project")
def update_project(project_id: int, project: MLProjectUpdate, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.update_project(db, project_id, project)
    except Exception as e:
        handle_service_errors(e)

@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an ML Project")
def delete_project(project_id: int, db: Session = Depends(DB_DEPENDENCY)):
    try:
        ai_ml_service.delete_project(db, project_id)
        return {"ok": True}
    except Exception as e:
        handle_service_errors(e)

# --- MLModel Endpoints ---

@router.post("/models", response_model=MLModel, status_code=status.HTTP_201_CREATED, summary="Register a new ML Model")
def create_model(model: MLModelCreate, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.create_model(db, model)
    except Exception as e:
        handle_service_errors(e)

@router.get("/models/{model_id}", response_model=MLModel, summary="Get a specific ML Model")
def get_model(model_id: int, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_model(db, model_id)
    except Exception as e:
        handle_service_errors(e)

@router.get("/projects/{project_id}/models", response_model=List[MLModel], summary="List models for a project")
def list_models_for_project(project_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_models_by_project(db, project_id, skip=skip, limit=limit)
    except Exception as e:
        handle_service_errors(e)

@router.get("/projects/{project_id}/models/current", response_model=MLModel, summary="Get the current active model for a project")
def get_current_model(project_id: int, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_current_model(db, project_id)
    except Exception as e:
        handle_service_errors(e)

@router.put("/models/{model_id}", response_model=MLModel, summary="Update an ML Model")
def update_model(model_id: int, model: MLModelUpdate, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.update_model(db, model_id, model)
    except Exception as e:
        handle_service_errors(e)

@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an ML Model")
def delete_model(model_id: int, db: Session = Depends(DB_DEPENDENCY)):
    try:
        ai_ml_service.delete_model(db, model_id)
        return {"ok": True}
    except Exception as e:
        handle_service_errors(e)

# --- Prediction Endpoints (Inference) ---

@router.post("/predictions", response_model=Prediction, status_code=status.HTTP_201_CREATED, summary="Record a new Prediction (Inference Result)")
def create_prediction(prediction: PredictionCreate, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.create_prediction(db, prediction)
    except Exception as e:
        handle_service_errors(e)

@router.get("/predictions/{prediction_id}", response_model=Prediction, summary="Get a specific Prediction record")
def get_prediction(prediction_id: int, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_prediction(db, prediction_id)
    except Exception as e:
        handle_service_errors(e)

@router.get("/projects/{project_id}/predictions", response_model=List[Prediction], summary="List predictions for a project")
def list_predictions_for_project(project_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_predictions_by_project(db, project_id, skip=skip, limit=limit)
    except Exception as e:
        handle_service_errors(e)

@router.get("/models/{model_id}/predictions", response_model=List[Prediction], summary="List predictions made by a specific model")
def list_predictions_for_model(model_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(DB_DEPENDENCY)):
    try:
        return ai_ml_service.get_predictions_by_model(db, model_id, skip=skip, limit=limit)
    except Exception as e:
        handle_service_errors(e)
