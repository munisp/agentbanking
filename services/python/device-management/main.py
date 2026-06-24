import os
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta
from loguru import logger

from . import models, schemas, security
from .database import SessionLocal, engine
from sqlalchemy import text
from .config import settings
from .metrics import REQUEST_COUNT, IN_PROGRESS_REQUESTS, DB_OPERATION_COUNT, generate_latest

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

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Device Management Service",
              description="API for managing devices and device owners in an Remittance Platform.",
              version="1.0.0")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

# Configure logger
logger.add("file.log", rotation="500 MB", compression="zip", level=settings.LOG_LEVEL)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Middleware for Prometheus metrics
@app.middleware("http")
async def add_prometheus_metrics(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    
    IN_PROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).inc()
    
    response = await call_next(request)
    
    IN_PROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).dec()
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=response.status_code).inc()
    
    return response

# --- Authentication Endpoints ---

@app.post("/token", response_model=security.Token, tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = security.authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    logger.info(f"User {user.username} successfully logged in.")
    return {"access_token": access_token, "token_type": "bearer"}

# --- Device Owner Endpoints ---

@app.post("/owners/", response_model=schemas.DeviceOwner, status_code=status.HTTP_201_CREATED, tags=["Device Owners"])
def create_device_owner(owner: schemas.DeviceOwnerCreate, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} creating new device owner: {owner.name}")
    db_owner = models.DeviceOwner(name=owner.name, contact_person=owner.contact_person, contact_email=owner.contact_email)
    db.add(db_owner)
    db.commit()
    db.refresh(db_owner)
    DB_OPERATION_COUNT.labels(operation='create', model='DeviceOwner', status='success').inc()
    logger.info(f"Device owner {db_owner.id} created by {current_user}.")
    return db_owner

@app.get("/owners/", response_model=List[schemas.DeviceOwner], tags=["Device Owners"])
def read_device_owners(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} fetching device owners.")
    owners = db.query(models.DeviceOwner).offset(skip).limit(limit).all()
    DB_OPERATION_COUNT.labels(operation='read', model='DeviceOwner', status='success').inc()
    return owners

@app.get("/owners/{owner_id}", response_model=schemas.DeviceOwner, tags=["Device Owners"])
def read_device_owner(owner_id: int, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} fetching device owner {owner_id}.")
    db_owner = db.query(models.DeviceOwner).filter(models.DeviceOwner.id == owner_id).first()
    if db_owner is None:
        logger.warning(f"Device owner {owner_id} not found for user {current_user}.")
        DB_OPERATION_COUNT.labels(operation='read', model='DeviceOwner', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device owner not found")
    DB_OPERATION_COUNT.labels(operation='read', model='DeviceOwner', status='success').inc()
    return db_owner

@app.put("/owners/{owner_id}", response_model=schemas.DeviceOwner, tags=["Device Owners"])
def update_device_owner(owner_id: int, owner: schemas.DeviceOwnerUpdate, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} updating device owner {owner_id}.")
    db_owner = db.query(models.DeviceOwner).filter(models.DeviceOwner.id == owner_id).first()
    if db_owner is None:
        logger.warning(f"Device owner {owner_id} not found for user {current_user} during update.")
        DB_OPERATION_COUNT.labels(operation='update', model='DeviceOwner', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device owner not found")
    
    update_data = owner.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_owner, key, value)
    
    db.add(db_owner)
    db.commit()
    db.refresh(db_owner)
    DB_OPERATION_COUNT.labels(operation='update', model='DeviceOwner', status='success').inc()
    logger.info(f"Device owner {db_owner.id} updated by {current_user}.")
    return db_owner

@app.delete("/owners/{owner_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Device Owners"])
def delete_device_owner(owner_id: int, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} deleting device owner {owner_id}.")
    db_owner = db.query(models.DeviceOwner).filter(models.DeviceOwner.id == owner_id).first()
    if db_owner is None:
        logger.warning(f"Device owner {owner_id} not found for user {current_user} during deletion.")
        DB_OPERATION_COUNT.labels(operation='delete', model='DeviceOwner', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device owner not found")
    db.delete(db_owner)
    db.commit()
    DB_OPERATION_COUNT.labels(operation='delete', model='DeviceOwner', status='success').inc()
    logger.info(f"Device owner {db_owner.id} deleted by {current_user}.")
    return {"message": "Device owner deleted successfully"}

# --- Device Endpoints ---

@app.post("/devices/", response_model=schemas.Device, status_code=status.HTTP_201_CREATED, tags=["Devices"])
def create_device(device: schemas.DeviceCreate, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} creating new device: {device.serial_number}")
    db_device = models.Device(**device.model_dump())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    DB_OPERATION_COUNT.labels(operation='create', model='Device', status='success').inc()
    logger.info(f"Device {db_device.id} created by {current_user}.")
    return db_device

@app.get("/devices/", response_model=List[schemas.Device], tags=["Devices"])
def read_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} fetching devices.")
    devices = db.query(models.Device).offset(skip).limit(limit).all()
    DB_OPERATION_COUNT.labels(operation='read', model='Device', status='success').inc()
    return devices

@app.get("/devices/{device_id}", response_model=schemas.Device, tags=["Devices"])
def read_device(device_id: int, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} fetching device {device_id}.")
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        logger.warning(f"Device {device_id} not found for user {current_user}.")
        DB_OPERATION_COUNT.labels(operation='read', model='Device', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    DB_OPERATION_COUNT.labels(operation='read', model='Device', status='success').inc()
    return db_device

@app.put("/devices/{device_id}", response_model=schemas.Device, tags=["Devices"])
def update_device(device_id: int, device: schemas.DeviceUpdate, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} updating device {device_id}.")
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        logger.warning(f"Device {device_id} not found for user {current_user} during update.")
        DB_OPERATION_COUNT.labels(operation='update', model='Device', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    update_data = device.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_device, key, value)
    
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    DB_OPERATION_COUNT.labels(operation='update', model='Device', status='success').inc()
    logger.info(f"Device {db_device.id} updated by {current_user}.")
    return db_device

@app.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Devices"])
def delete_device(device_id: int, db: Session = Depends(get_db), current_user: str = Depends(security.get_current_user)):
    logger.info(f"User {current_user} deleting device {device_id}.")
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        logger.warning(f"Device {device_id} not found for user {current_user} during deletion.")
        DB_OPERATION_COUNT.labels(operation='delete', model='Device', status='failure').inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    db.delete(db_device)
    db.commit()
    DB_OPERATION_COUNT.labels(operation='delete', model='Device', status='success').inc()
    logger.info(f"Device {db_device.id} deleted by {current_user}.")
    return {"message": "Device deleted successfully"}

# Health check endpoint
@app.get("/health", tags=["Monitoring"])
async def health_check():
    # In a real application, you would check database connection, external services, etc.
    try:
        db = SessionLocal()
        db.execute(models.text("SELECT 1"))
        db.close()
        db_status = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "failed"
    return {"status": "ok", "database": db_status}

# Metrics endpoint
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    return Response(content=generate_latest().decode("utf-8"), media_type="text/plain")

