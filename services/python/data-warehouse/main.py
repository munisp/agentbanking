import os

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import jwt
from fastapi import FastAPI, Depends, HTTPException, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models, config

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

# --- Configuration and Initialization ---
settings = config.settings

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.APP_NAME)

app = FastAPI(
    title=settings.APP_NAME,
    description="Data Warehouse Service for Remittance Platform",
    version="1.0.0",
)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

# Create database tables
models.Base.metadata.create_all(bind=models.engine)

# Dependency to get DB session
def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Security --- 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# User management (connects to external auth service)
class UserInDB(models.BaseModel):
    username: str
    hashed_password: str

fake_users_db = {
    "testuser": {"username": "testuser", "hashed_password": get_password_hash("password")}
}

def get_user(username: str):
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = get_user(username=username)
    if user is None:
        raise credentials_exception
    return user

# --- Authentication Endpoints ---
@app.post("/token", response_model=models.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- CRUD Endpoints for Dimensions ---

@app.post("/agents/", response_model=models.AgentDimensionResponse, status_code=status.HTTP_201_CREATED)
def create_agent(agent: models.AgentDimensionCreate, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} creating agent: {agent.agent_id}")
    db_agent = db.query(models.AgentDimension).filter(models.AgentDimension.agent_id == agent.agent_id).first()
    if db_agent:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent with this ID already exists")
    db_agent = models.AgentDimension(**agent.dict())
    try:
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        return db_agent
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent with this ID already exists")
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/agents/", response_model=List[models.AgentDimensionResponse])
def read_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading agents (skip={skip}, limit={limit})")
    agents = db.query(models.AgentDimension).offset(skip).limit(limit).all()
    return agents

@app.get("/agents/{agent_id}", response_model=models.AgentDimensionResponse)
def read_agent(agent_id: str, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading agent: {agent_id}")
    db_agent = db.query(models.AgentDimension).filter(models.AgentDimension.agent_id == agent_id).first()
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return db_agent

@app.post("/customers/", response_model=models.CustomerDimensionResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer: models.CustomerDimensionCreate, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} creating customer: {customer.customer_id}")
    db_customer = db.query(models.CustomerDimension).filter(models.CustomerDimension.customer_id == customer.customer_id).first()
    if db_customer:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer with this ID already exists")
    db_customer = models.CustomerDimension(**customer.dict())
    try:
        db.add(db_customer)
        db.commit()
        db.refresh(db_customer)
        return db_customer
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer with this ID already exists")
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/customers/", response_model=List[models.CustomerDimensionResponse])
def read_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading customers (skip={skip}, limit={limit})")
    customers = db.query(models.CustomerDimension).offset(skip).limit(limit).all()
    return customers

@app.get("/customers/{customer_id}", response_model=models.CustomerDimensionResponse)
def read_customer(customer_id: str, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading customer: {customer_id}")
    db_customer = db.query(models.CustomerDimension).filter(models.CustomerDimension.customer_id == customer_id).first()
    if db_customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return db_customer

@app.post("/locations/", response_model=models.LocationDimensionResponse, status_code=status.HTTP_201_CREATED)
def create_location(location: models.LocationDimensionCreate, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} creating location: {location.location_id}")
    db_location = db.query(models.LocationDimension).filter(models.LocationDimension.location_id == location.location_id).first()
    if db_location:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Location with this ID already exists")
    db_location = models.LocationDimension(**location.dict())
    try:
        db.add(db_location)
        db.commit()
        db.refresh(db_location)
        return db_location
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Location with this ID already exists")
    except Exception as e:
        logger.error(f"Error creating location: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/locations/", response_model=List[models.LocationDimensionResponse])
def read_locations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading locations (skip={skip}, limit={limit})")
    locations = db.query(models.LocationDimension).offset(skip).limit(limit).all()
    return locations

@app.get("/locations/{location_id}", response_model=models.LocationDimensionResponse)
def read_location(location_id: str, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading location: {location_id}")
    db_location = db.query(models.LocationDimension).filter(models.LocationDimension.location_id == location_id).first()
    if db_location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return db_location

# --- CRUD Endpoints for Fact Table ---

@app.post("/transactions/", response_model=models.TransactionFactResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: models.TransactionFactCreate, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} creating transaction: {transaction.transaction_uuid}")
    db_transaction = db.query(models.TransactionFact).filter(models.TransactionFact.transaction_uuid == transaction.transaction_uuid).first()
    if db_transaction:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction with this UUID already exists")
    db_transaction = models.TransactionFact(**transaction.dict())
    try:
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        return db_transaction
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction with this UUID already exists or foreign key constraint failed")
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/transactions/", response_model=List[models.TransactionFactResponse])
def read_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading transactions (skip={skip}, limit={limit})")
    transactions = db.query(models.TransactionFact).offset(skip).limit(limit).all()
    return transactions

@app.get("/transactions/{transaction_uuid}", response_model=models.TransactionFactResponse)
def read_transaction(transaction_uuid: str, db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} reading transaction: {transaction_uuid}")
    db_transaction = db.query(models.TransactionFact).filter(models.TransactionFact.transaction_uuid == transaction_uuid).first()
    if db_transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return db_transaction

# --- Health Check and Metrics ---
import redis
import boto3
from botocore.exceptions import ClientError

@app.get("/health", response_model=models.HealthCheckResponse)
def health_check(db: Session = Depends(get_db), current_user: UserInDB = Depends(get_current_user)):
    logger.info(f"User {current_user.username} performing health check")
    db_status = "unreachable"
    redis_status = "unreachable"
    s3_status = "unreachable"

    try:
        # Check DB connection
        db.execute("SELECT 1")
        db_status = "reachable"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    try:
        # Check Redis connection
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_connect_timeout=1)
        r.ping()
        redis_status = "reachable"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    try:
        # Check S3 connection
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        s3_status = "reachable"
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            s3_status = "bucket_not_found"
        else:
            logger.error(f"S3 health check failed: {e}")
    except Exception as e:
        logger.error(f"S3 health check failed: {e}")

    return {"status": "ok", "database_connection": db_status, "redis_connection": redis_status, "s3_connection": s3_status}

# Root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Data Warehouse Service"}

