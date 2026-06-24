import os
import logging
import time
from fastapi import FastAPI, Depends, HTTPException, Security, Request
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from sqlalchemy.orm import Session
from typing import List
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from . import models, schemas, database, security, metrics
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

# Configure logging
logging.basicConfig(level=settings.log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="ML Engine Service", description="Machine Learning Engine for Remittance Platform")
apply_middleware(app, enable_auth=True)

# Dependency to get the database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

@app.on_event("startup")
def on_startup():
    database.create_db_and_tables()
    logger.info("Database tables created/checked.")

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    metrics.REQUEST_LATENCY.labels(request.method, request.url.path).observe(process_time)
    metrics.REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    return response

@app.get("/health", tags=["Health Check"])
async def health_check():
    logger.info("Health check requested.")
    return {"status": "healthy"}

@app.get("/metrics", tags=["Monitoring"])
async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ML Model Endpoints - protected by API key
@app.post("/models/", response_model=schemas.MLModel, status_code=201, tags=["ML Models"])
def create_ml_model(model: schemas.MLModelCreate, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("create_ml_model_" + str(int(_time.time() * 1000)), _json.dumps({"action": "create_ml_model", "timestamp": _time.time()}), "ml-engine")

    logger.info(f"Creating ML model: {model.name}")
    try:
        db_model = models.MLModel(**model.dict())
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model
    except Exception as e:
        logger.error(f"Error creating ML model: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@app.get("/models/", response_model=List[schemas.MLModel], tags=["ML Models"])
def read_ml_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_ml_models", "ml-engine")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    logger.info(f"Reading ML models (skip={skip}, limit={limit}).")
    models_list = db.query(models.MLModel).offset(skip).limit(limit).all()
    return models_list

@app.get("/models/{model_id}", response_model=schemas.MLModel, tags=["ML Models"])
def read_ml_model(model_id: int, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_ml_model", "ml-engine")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    logger.info(f"Reading ML model with ID: {model_id}")
    db_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if db_model is None:
        logger.warning(f"ML Model with ID {model_id} not found.")
        raise HTTPException(status_code=404, detail="ML Model not found")
    return db_model

@app.put("/models/{model_id}", response_model=schemas.MLModel, tags=["ML Models"])
def update_ml_model(model_id: int, model: schemas.MLModelUpdate, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("update_ml_model_" + str(int(_time.time() * 1000)), _json.dumps({"action": "update_ml_model", "timestamp": _time.time()}), "ml-engine")

    logger.info(f"Updating ML model with ID: {model_id}")
    db_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if db_model is None:
        logger.warning(f"ML Model with ID {model_id} not found for update.")
        raise HTTPException(status_code=404, detail="ML Model not found")
    try:
        for key, value in model.dict(exclude_unset=True).items():
            setattr(db_model, key, value)
        db.commit()
        db.refresh(db_model)
        return db_model
    except Exception as e:
        logger.error(f"Error updating ML model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@app.delete("/models/{model_id}", status_code=204, tags=["ML Models"])
def delete_ml_model(model_id: int, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("delete_ml_model_" + str(int(_time.time() * 1000)), _json.dumps({"action": "delete_ml_model", "timestamp": _time.time()}), "ml-engine")

    logger.info(f"Deleting ML model with ID: {model_id}")
    db_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if db_model is None:
        logger.warning(f"ML Model with ID {model_id} not found for deletion.")
        raise HTTPException(status_code=404, detail="ML Model not found")
    try:
        db.delete(db_model)
        db.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error deleting ML model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

# Prediction Endpoints - protected by API key
@app.post("/predictions/", response_model=schemas.Prediction, status_code=201, tags=["Predictions"])
def create_prediction(prediction: schemas.PredictionCreate, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("create_prediction_" + str(int(_time.time() * 1000)), _json.dumps({"action": "create_prediction", "timestamp": _time.time()}), "ml-engine")

    logger.info(f"Creating prediction for model ID: {prediction.model_id}")
    # In a real scenario, this would trigger an actual ML prediction
    # For now, we'll just store the request and a dummy result
    try:
        db_prediction = models.Prediction(
            model_id=prediction.model_id,
            request_data=prediction.request_data,
            prediction_result={"result": "pending_inference"}
        )
        db.add(db_prediction)
        db.commit()
        db.refresh(db_prediction)
        return db_prediction
    except Exception as e:
        logger.error(f"Error creating prediction for model {prediction.model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@app.get("/predictions/", response_model=List[schemas.Prediction], tags=["Predictions"])
def read_predictions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_predictions", "ml-engine")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    logger.info(f"Reading predictions (skip={skip}, limit={limit}).")
    predictions_list = db.query(models.Prediction).offset(skip).limit(limit).all()
    return predictions_list

@app.get("/predictions/{prediction_id}", response_model=schemas.Prediction, tags=["Predictions"])
def read_prediction(prediction_id: int, db: Session = Depends(get_db), api_key: str = Security(security.get_api_key)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_prediction", "ml-engine")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    logger.info(f"Reading prediction with ID: {prediction_id}")
    db_prediction = db.query(models.Prediction).filter(models.Prediction.id == prediction_id).first()
    if db_prediction is None:
        logger.warning(f"Prediction with ID {prediction_id} not found.")
        raise HTTPException(status_code=404, detail="Prediction not found")
    return db_prediction

