import os
import sys
import uuid
import logging
from os.path import abspath, dirname, join
from typing import List, Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import schemas, service
from .database import get_db
from .models import User as DBUser # Alias to avoid conflict with schemas.User

# Ensure the repo-level shared/ package (services/shared) is importable no
# matter which directory layout the service is deployed with.
for _p in (join(dirname(abspath(__file__)), ".."),
           join(dirname(abspath(__file__)), "..", "..")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

log = logging.getLogger(__name__)

# --- Security Dependencies (fail-closed) ---
#
# Every request must carry a valid Keycloak-issued RS256 JWT bearer token,
# validated against the realm JWKS via services/shared/keycloak_auth.py (the
# repo-standard module — same Keycloak pattern as goaml-integration-go).
#   - missing / malformed / expired / invalid token        -> 401
#   - valid token whose identity is not a provisioned user -> 401
#   - auth subsystem misconfigured (module/settings)       -> 503
# The previous placeholder (returning the FIRST user in the database as the
# "current user" on every request) has been removed — no request is ever
# silently authenticated as an arbitrary account.
#
# DEV-ONLY override: AI_ML_PLATFORM_DEV_AUTH_BYPASS=true skips JWT validation
# and authenticates as AI_ML_PLATFORM_DEV_USER_EMAIL (must exist in the DB).
# Honoured ONLY outside production; setting it in production hard-fails at
# startup.

ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
IS_PRODUCTION = ENVIRONMENT in ("production", "prod")
DEV_AUTH_BYPASS = os.getenv("AI_ML_PLATFORM_DEV_AUTH_BYPASS", "").lower() == "true"

if DEV_AUTH_BYPASS and IS_PRODUCTION:
    raise RuntimeError(
        "AI_ML_PLATFORM_DEV_AUTH_BYPASS=true is forbidden in production: "
        "authentication must never be bypassed on live traffic."
    )

_bearer_scheme = HTTPBearer(auto_error=False)
_keycloak_auth = None


def _get_keycloak_auth():
    """Lazy-load the repo-standard Keycloak RS256/JWKS token validator."""
    global _keycloak_auth
    if _keycloak_auth is not None:
        return _keycloak_auth
    try:
        from shared.keycloak_auth import KeycloakAuth
    except ImportError as exc:
        raise RuntimeError(
            f"keycloak auth module unavailable ({exc}); authentication is misconfigured"
        )
    _keycloak_auth = KeycloakAuth(verify_audience=False)
    return _keycloak_auth


def _lookup_user_by_email(email: str, db: Session) -> DBUser:
    user = db.query(DBUser).filter(DBUser.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token identity '{email}' is not a provisioned user.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    db: Session = Depends(get_db),
) -> DBUser:
    """
    Authenticate the caller via a Keycloak RS256 JWT bearer token and return
    the matching provisioned user. Fails CLOSED on every error path — a caller
    is never silently mapped to an arbitrary account.
    """
    # DEV-only bypass (import-time guard above already forbids it in production).
    if DEV_AUTH_BYPASS:
        dev_email = os.getenv("AI_ML_PLATFORM_DEV_USER_EMAIL", "dev@example.com")
        log.warning(f"DEV AUTH BYPASS active: authenticating as {dev_email} (non-production)")
        return _lookup_user_by_email(dev_email, db)

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        auth = _get_keycloak_auth()
    except RuntimeError as exc:
        log.error(str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    try:
        claims = auth.decode_token(credentials.credentials)
    except Exception as exc:
        # Expired token, bad signature, wrong issuer/audience — all fail closed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = claims.get("email") or claims.get("preferred_username")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing an email/preferred_username identity claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _lookup_user_by_email(email, db)

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
