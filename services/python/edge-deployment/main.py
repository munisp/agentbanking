import os
from fastapi import FastAPI, Depends, HTTPException, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import datetime
import uuid
import logging

from . import models, schemas, auth
from .models import SessionLocal, engine

# Configure logging
from .config import settings

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

logging.basicConfig(level=settings.log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Edge Deployment Service",
    description="API for managing edge device deployments in the Remittance Platform.",
    version="1.0.0",
)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

# Instrument the app with Prometheus metrics
Instrumentator().instrument(app).expose(app, include_in_schema=True, tags=["Metrics"])

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health", tags=["Health Check"], summary="Perform a health check")
async def health_check():
    """Perform a health check to ensure the service is running."""
    logger.info("Health check requested.")
    return {"status": "healthy", "service": "edge-deployment-service"}

# User Authentication Endpoints
@app.post("/token", response_model=schemas.Token, tags=["Authentication"], summary="Authenticate user and get access token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth.get_user(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"User {user.username} logged in successfully.")
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED, tags=["Authentication"], summary="Create a new user")
async def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = auth.get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(id=str(uuid.uuid4()), username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"User {user.username} created successfully.")
    return db_user

@app.get("/users/me/", response_model=schemas.User, tags=["Authentication"], summary="Get current user information")
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

# Edge Device Endpoints - Secured
@app.post("/devices/", response_model=schemas.EdgeDevice, status_code=status.HTTP_201_CREATED, tags=["Edge Devices"], summary="Register a new edge device")
async def create_edge_device(device: schemas.EdgeDeviceCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    db_device = models.EdgeDevice(**device.dict())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    logger.info(f"Device {device.id} created by user {current_user.username}.")
    return db_device

@app.get("/devices/", response_model=List[schemas.EdgeDevice], tags=["Edge Devices"], summary="Retrieve all edge devices")
async def read_edge_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    devices = db.query(models.EdgeDevice).offset(skip).limit(limit).all()
    return devices

@app.get("/devices/{device_id}", response_model=schemas.EdgeDevice, tags=["Edge Devices"], summary="Retrieve a specific edge device by ID")
async def read_edge_device(device_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    device = db.query(models.EdgeDevice).filter(models.EdgeDevice.id == device_id).first()
    if device is None:
        logger.warning(f"Attempted to access non-existent device {device_id} by user {current_user.username}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge device not found")
    return device

@app.put("/devices/{device_id}", response_model=schemas.EdgeDevice, tags=["Edge Devices"], summary="Update an existing edge device")
async def update_edge_device(device_id: str, device: schemas.EdgeDeviceUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    db_device = db.query(models.EdgeDevice).filter(models.EdgeDevice.id == device_id).first()
    if db_device is None:
        logger.warning(f"Attempted to update non-existent device {device_id} by user {current_user.username}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge device not found")
    for key, value in device.dict(exclude_unset=True).items():
        setattr(db_device, key, value)
    db_device.last_seen = datetime.datetime.utcnow() # Update last_seen on any update
    db.commit()
    db.refresh(db_device)
    logger.info(f"Device {device_id} updated by user {current_user.username}.")
    return db_device

@app.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Edge Devices"], summary="Delete an edge device")
async def delete_edge_device(device_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin_user)):
    db_device = db.query(models.EdgeDevice).filter(models.EdgeDevice.id == device_id).first()
    if db_device is None:
        logger.warning(f"Attempted to delete non-existent device {device_id} by admin {current_user.username}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge device not found")
    db.delete(db_device)
    db.commit()
    logger.info(f"Device {device_id} deleted by admin {current_user.username}.")
    return

# Deployment Endpoints - Secured
@app.post("/deployments/", response_model=schemas.Deployment, status_code=status.HTTP_201_CREATED, tags=["Deployments"], summary="Initiate a new deployment")
async def create_deployment(deployment: schemas.DeploymentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    db_deployment = models.Deployment(**deployment.dict())
    db.add(db_deployment)
    db.commit()
    db.refresh(db_deployment)
    logger.info(f"Deployment {deployment.id} initiated for device {deployment.device_id} by user {current_user.username}.")
    return db_deployment

@app.get("/deployments/", response_model=List[schemas.Deployment], tags=["Deployments"], summary="Retrieve all deployments")
async def read_deployments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    deployments = db.query(models.Deployment).offset(skip).limit(limit).all()
    return deployments

@app.get("/deployments/{deployment_id}", response_model=schemas.Deployment, tags=["Deployments"], summary="Retrieve a specific deployment by ID")
async def read_deployment(deployment_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    deployment = db.query(models.Deployment).filter(models.Deployment.id == deployment_id).first()
    if deployment is None:
        logger.warning(f"Attempted to access non-existent deployment {deployment_id} by user {current_user.username}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return deployment

@app.put("/deployments/{deployment_id}", response_model=schemas.Deployment, tags=["Deployments"], summary="Update an existing deployment")
async def update_deployment(deployment_id: str, deployment: schemas.DeploymentUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    db_deployment = db.query(models.Deployment).filter(models.Deployment.id == deployment_id).first()
    if db_deployment is None:
        logger.warning(f"Attempted to update non-existent deployment {deployment_id} by user {current_user.username}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    for key, value in deployment.dict(exclude_unset=True).items():
        setattr(db_deployment, key, value)
    if deployment.status == "completed" or deployment.status == "failed":
        db_deployment.completed_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_deployment)
    logger.info(f"Deployment {deployment_id} updated by user {current_user.username}.")
    return db_deployment

@app.delete("/deployments/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Deployments"], summary="Delete a deployment")
async def delete_deployment(deployment_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_admin_user)):
    db_deployment = db.query(models.Deployment).filter(models.Deployment.id == deployment_id).first()
    if db_deployment is None:
        logger.warning(f"Attempted to delete non-existent deployment {deployment_id} by admin {current_user.username}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    db.delete(db_deployment)
    db.commit()
    logger.info(f"Deployment {deployment_id} deleted by admin {current_user.username}.")
    return

