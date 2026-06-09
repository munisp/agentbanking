import uuid
from typing import List, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import schemas, service
from .database import get_db
from .models import User as DBUser # Alias to avoid conflict with schemas.User

# --- Security Dependencies (Placeholders) ---

# NOTE: In a real application, this would involve JWT decoding and database lookup
def get_current_user(db: Session = Depends(get_db)) -> DBUser:
    """
    Placeholder dependency to simulate getting the current authenticated user.
    For simplicity, it currently returns the first user found in the database.
    In a real app, this would decode a JWT token and fetch the user.
    """
    # For demonstration, let's assume a user is always authenticated if one exists
    user = db.query(DBUser).first()
    if not user:
        # If no user exists, we can't authenticate, but we need a user for CRUD.
        # This is a simplification. In a real app, unauthenticated users get 401.
        # For now, we'll allow unauthenticated access to user creation/login.
        # For other routes, we'll raise an exception if no user is found.
        raise service.AuthenticationException(detail="Not authenticated")
    return user

# --- Routers ---

router = APIRouter(prefix="/api/v1", tags=["root"])
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
user_router = APIRouter(prefix="/users", tags=["Users"])
dataset_router = APIRouter(prefix="/datasets", tags=["Datasets"])
experiment_router = APIRouter(prefix="/experiments", tags=["Experiments"])
model_router = APIRouter(prefix="/models", tags=["Models"])

# --- Authentication Endpoints ---

@auth_router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    return service.user_service.create_user(db=db, user_in=user_in)

@auth_router.post("/login", response_model=dict)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Authenticate and get an access token."""
    user = service.auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise service.AuthenticationException(detail="Incorrect username or password")

    access_token = service.auth_service.create_token_for_user(user)
    return {"access_token": access_token, "token_type": "bearer"}

# --- User Endpoints ---

@user_router.get("/", response_model=List[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a list of users."""
    return service.user_service.get_multi(db, skip=skip, limit=limit)

@user_router.get("/{user_id}", response_model=schemas.User)
def read_user(user_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a single user by ID."""
    return service.user_service.get(db, user_id)

# --- Dataset Endpoints ---

@dataset_router.post("/", response_model=schemas.Dataset, status_code=status.HTTP_201_CREATED)
def create_dataset(dataset_in: schemas.DatasetCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Create a new dataset."""
    return service.dataset_service.create(db=db, obj_in=dataset_in, owner_id=current_user.id)

@dataset_router.get("/", response_model=List[schemas.Dataset])
def read_datasets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a list of datasets."""
    return service.dataset_service.get_multi(db, skip=skip, limit=limit)

@dataset_router.get("/{dataset_id}", response_model=schemas.Dataset)
def read_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a single dataset by ID."""
    return service.dataset_service.get(db, dataset_id)

@dataset_router.put("/{dataset_id}", response_model=schemas.Dataset)
def update_dataset(dataset_id: uuid.UUID, dataset_in: schemas.DatasetUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Update an existing dataset."""
    db_dataset = service.dataset_service.get(db, dataset_id)
    if db_dataset.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this dataset")
    return service.dataset_service.update(db, db_dataset, dataset_in)

@dataset_router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Delete a dataset."""
    db_dataset = service.dataset_service.get(db, dataset_id)
    if db_dataset.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this dataset")
    service.dataset_service.remove(db, dataset_id)
    return

# --- Experiment Endpoints (Similar CRUD) ---

@experiment_router.post("/", response_model=schemas.Experiment, status_code=status.HTTP_201_CREATED)
def create_experiment(experiment_in: schemas.ExperimentCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Create a new experiment."""
    return service.experiment_service.create(db=db, obj_in=experiment_in, owner_id=current_user.id)

@experiment_router.get("/", response_model=List[schemas.Experiment])
def read_experiments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a list of experiments."""
    return service.experiment_service.get_multi(db, skip=skip, limit=limit)

@experiment_router.get("/{experiment_id}", response_model=schemas.Experiment)
def read_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a single experiment by ID."""
    return service.experiment_service.get(db, experiment_id)

@experiment_router.put("/{experiment_id}", response_model=schemas.Experiment)
def update_experiment(experiment_id: uuid.UUID, experiment_in: schemas.ExperimentUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Update an existing experiment."""
    db_experiment = service.experiment_service.get(db, experiment_id)
    if db_experiment.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this experiment")
    return service.experiment_service.update(db, db_experiment, experiment_in)

@experiment_router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Delete an experiment."""
    db_experiment = service.experiment_service.get(db, experiment_id)
    if db_experiment.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this experiment")
    service.experiment_service.remove(db, experiment_id)
    return

# --- Model Endpoints (Similar CRUD) ---

@model_router.post("/", response_model=schemas.Model, status_code=status.HTTP_201_CREATED)
def create_model(model_in: schemas.ModelCreate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Create a new model."""
    return service.model_service.create(db=db, obj_in=model_in, owner_id=current_user.id)

@model_router.get("/", response_model=List[schemas.Model])
def read_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a list of models."""
    return service.model_service.get_multi(db, skip=skip, limit=limit)

@model_router.get("/{model_id}", response_model=schemas.Model)
def read_model(model_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Retrieve a single model by ID."""
    return service.model_service.get(db, model_id)

@model_router.put("/{model_id}", response_model=schemas.Model)
def update_model(model_id: uuid.UUID, model_in: schemas.ModelUpdate, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Update an existing model."""
    db_model = service.model_service.get(db, model_id)
    if db_model.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this model")
    return service.model_service.update(db, db_model, model_in)

@model_router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: uuid.UUID, db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    """Delete a model."""
    db_model = service.model_service.get(db, model_id)
    if db_model.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this model")
    service.model_service.remove(db, model_id)
    return

# --- Main Router Inclusion ---

all_routers = [
    auth_router,
    user_router,
    dataset_router,
    experiment_router,
    model_router,
]