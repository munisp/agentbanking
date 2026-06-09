from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from service import AIPlatformService
from schemas import (
    Model, ModelCreate, ModelUpdate, 
    Experiment, ExperimentCreate, ExperimentUpdate
)
from exceptions import NotFoundException, AlreadyExistsException

router = APIRouter()

# Dependency to get the service layer
def get_service(db: Session = Depends(get_db)) -> AIPlatformService:
    return AIPlatformService(db)

# --- Model Endpoints ---

@router.post("/models", response_model=Model, status_code=status.HTTP_201_CREATED, summary="Create a new AI Model")
def create_model(
    model_in: ModelCreate,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Register a new AI model with its metadata, framework, and storage path.
    """
    try:
        return service.create_model(model_in)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/models", response_model=List[Model], summary="List all AI Models")
def list_models(
    skip: int = 0, 
    limit: int = 100,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Retrieve a list of all registered AI models.
    """
    return service.get_models(skip=skip, limit=limit)

@router.get("/models/{model_id}", response_model=Model, summary="Get a specific AI Model")
def get_model(
    model_id: int,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Retrieve a single AI model by its unique ID.
    """
    try:
        return service.get_model(model_id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/models/{model_id}", response_model=Model, summary="Update an existing AI Model")
def update_model(
    model_id: int,
    model_in: ModelUpdate,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Update the metadata for an existing AI model.
    """
    try:
        return service.update_model(model_id, model_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except AlreadyExistsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an AI Model")
def delete_model(
    model_id: int,
    service: AIPlatformService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Delete an AI model by its unique ID.
    """
    try:
        service.delete_model(model_id)
        return {"ok": True}
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Experiment Endpoints ---

@router.post("/experiments", response_model=Experiment, status_code=status.HTTP_201_CREATED, summary="Create a new Experiment")
def create_experiment(
    experiment_in: ExperimentCreate,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Register a new experiment run, optionally linking it to a resulting model.
    """
    try:
        return service.create_experiment(experiment_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/experiments", response_model=List[Experiment], summary="List all Experiments")
def list_experiments(
    skip: int = 0, 
    limit: int = 100,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Retrieve a list of all recorded experiment runs.
    """
    return service.get_experiments(skip=skip, limit=limit)

@router.get("/experiments/{experiment_id}", response_model=Experiment, summary="Get a specific Experiment")
def get_experiment(
    experiment_id: int,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Retrieve a single experiment run by its unique ID.
    """
    try:
        return service.get_experiment(experiment_id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/experiments/{experiment_id}", response_model=Experiment, summary="Update an existing Experiment")
def update_experiment(
    experiment_id: int,
    experiment_in: ExperimentUpdate,
    service: AIPlatformService = Depends(get_service)
) -> None:
    """
    Update the details for an existing experiment run.
    """
    try:
        return service.update_experiment(experiment_id, experiment_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete("/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an Experiment")
def delete_experiment(
    experiment_id: int,
    service: AIPlatformService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Delete an experiment run by its unique ID.
    """
    try:
        service.delete_experiment(experiment_id)
        return {"ok": True}
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
