
import logging
from logging.config import dictConfig

from fastapi import FastAPI, Depends, HTTPException, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List

from . import models, schemas, security
from .database import SessionLocal, engine
from .config import settings

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

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
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "sqlalchemy": {
            "handlers": ["default"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "analytics-dashboard"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")

app = FastAPI(
    title="Analytics Dashboard Service",
    description="API for managing and retrieving analytics data for the Remittance Platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
apply_middleware(app, enable_auth=True)
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: Session = Depends(get_db)):
    logger.info("Health check requested.")
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Analytics Dashboard Service is healthy"}
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database connection failed")

# Authentication endpoint (for JWT token generation)
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: security.OAuth2PasswordRequestForm = Depends()):
    user = security.get_user(form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# User Activity Endpoints
@app.post("/user-activities/", response_model=schemas.UserActivity, status_code=status.HTTP_201_CREATED)
def create_user_activity(
    activity: schemas.UserActivityCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["write"])),
):
    logger.info(f"User {current_user.username} creating user activity.")
    db_activity = models.UserActivity(**activity.dict())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity

@app.get("/user-activities/", response_model=List[schemas.UserActivity])
def read_user_activities(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading user activities.")
    activities = db.query(models.UserActivity).offset(skip).limit(limit).all()
    return activities

@app.get("/user-activities/{activity_id}", response_model=schemas.UserActivity)
def read_user_activity(
    activity_id: int, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading user activity {activity_id}.")
    activity = db.query(models.UserActivity).filter(models.UserActivity.id == activity_id).first()
    if activity is None:
        logger.warning(f"User activity {activity_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User activity not found")
    return activity

# Transaction Endpoints
@app.post("/transactions/", response_model=schemas.Transaction, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: schemas.TransactionCreate, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["write"])),
):
    logger.info(f"User {current_user.username} creating transaction.")
    db_transaction = models.Transaction(**transaction.dict())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.get("/transactions/", response_model=List[schemas.Transaction])
def read_transactions(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading transactions.")
    transactions = db.query(models.Transaction).offset(skip).limit(limit).all()
    return transactions

@app.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
def read_transaction(
    transaction_id: int, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading transaction {transaction_id}.")
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if transaction is None:
        logger.warning(f"Transaction {transaction_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction

# Metric Endpoints
@app.post("/metrics/", response_model=schemas.Metric, status_code=status.HTTP_201_CREATED)
def create_metric(
    metric: schemas.MetricCreate, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["write"])),
):
    logger.info(f"User {current_user.username} creating metric.")
    db_metric = models.Metric(**metric.dict())
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

@app.get("/metrics/", response_model=List[schemas.Metric])
def read_metrics(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading metrics.")
    metrics = db.query(models.Metric).offset(skip).limit(limit).all()
    return metrics

@app.get("/metrics/{metric_id}", response_model=schemas.Metric)
def read_metric(
    metric_id: int, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading metric {metric_id}.")
    metric = db.query(models.Metric).filter(models.Metric.id == metric_id).first()
    if metric is None:
        logger.warning(f"Metric {metric_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return metric

# Alert Endpoints
@app.post("/alerts/", response_model=schemas.Alert, status_code=status.HTTP_201_CREATED)
def create_alert(
    alert: schemas.AlertCreate, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["write"])),
):
    logger.info(f"User {current_user.username} creating alert.")
    db_alert = models.Alert(**alert.dict())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert

@app.get("/alerts/", response_model=List[schemas.Alert])
def read_alerts(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading alerts.")
    alerts = db.query(models.Alert).offset(skip).limit(limit).all()
    return alerts

@app.get("/alerts/{alert_id}", response_model=schemas.Alert)
def read_alert(
    alert_id: int, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
    api_key: str = Depends(lambda k=Depends(security.get_api_key_with_scopes): k(["read"])),
):
    logger.info(f"User {current_user.username} reading alert {alert_id}.")
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if alert is None:
        logger.warning(f"Alert {alert_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert

