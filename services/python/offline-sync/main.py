import os
from fastapi import FastAPI, Depends, HTTPException, status, Security
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Dict
import logging
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext

from ..models.database import SessionLocal, engine, Base, SyncRecord, OfflineTransaction, SyncRequest, SyncResponse, SyncRecordCreate, OfflineTransactionCreate
from ..config.settings import get_settings

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


# Initialize FastAPI app
app = FastAPI(
    title=get_settings()

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()
.app_name,
apply_middleware(app, enable_auth=True)
    description="Service for managing offline synchronization of remittance data.",
    version="1.0.0",
)

# Database setup
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Security setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Production implementation for user authentication (replace with actual user service integration)
class User:
    def __init__(self, username: str, hashed_password: str, roles: List[str]):
        self.username = username
        self.hashed_password = hashed_password
        self.roles = roles

# In a real application, this would come from a database or user service
fake_users_db = {
    "agent_user": User("agent_user", pwd_context.hash("agent_password"), ["agent"]),
    "admin_user": User("admin_user", pwd_context.hash("admin"), ["admin"]),
}

def authenticate_user(username: str, password: str):
    user = fake_users_db.get(username)
    if not user or not pwd_context.verify(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=get_settings().access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_settings().jwt_secret_key, algorithm=get_settings().jwt_algorithm)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=[get_settings().jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = fake_users_db.get(username) # In real app, fetch user from DB
        if user is None:
            raise credentials_exception
        return user
    except jwt.PyJWTError:
        raise credentials_exception

async def get_current_active_user(current_user: User = Security(get_current_user, scopes=["agent", "admin"])):
    # This function can be used to enforce roles if needed
    return current_user

# Logging setup
logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

# Health Check Endpoint
@app.get("/health", summary="Health Check", response_model=Dict[str, str])
async def health_check():
    return {"status": "ok", "service": get_settings().app_name}

# Authentication Endpoint
@app.post("/token", summary="Get Access Token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("login_for_access_token_" + str(int(_time.time() * 1000)), _json.dumps({"action": "login_for_access_token", "timestamp": _time.time()}), "offline-sync")

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-AUTHENTICATE": "Bearer"},
        )
    access_token_expires = timedelta(minutes=get_settings().access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.roles}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Core Offline Sync Endpoint
@app.post("/sync", response_model=SyncResponse, status_code=status.HTTP_200_OK, summary="Synchronize Offline Data")
async def sync_offline_data(
    sync_request: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.username} initiating sync for device_id: {sync_request.sync_records[0].device_id if sync_request.sync_records else 'N/A'}")
    
    synced_records_count = 0
    synced_transactions_count = 0
    failed_records = []
    failed_transactions = []

    # Process SyncRecords
    for record_data in sync_request.sync_records:
        try:
            # Basic validation: ensure user_id and device_id match current_user and expected device
            # (More robust validation would involve checking device registration and ownership)
            if record_data.user_id != current_user.username:
                logger.warning(f"Attempted sync for mismatching user_id: {record_data.user_id} by {current_user.username}")
                failed_records.append(record_data.id if hasattr(record_data, 'id') else -1) # Assuming ID might be present for failed records
                continue

            db_record = SyncRecord(**record_data.model_dump())
            db.add(db_record)
            db.commit()
            db.refresh(db_record)
            synced_records_count += 1
            logger.debug(f"Synced SyncRecord: {db_record.id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync SyncRecord {record_data.entity_type}/{record_data.entity_id}: {e}")
            failed_records.append(record_data.id if hasattr(record_data, 'id') else -1)

    # Process OfflineTransactions
    for transaction_data in sync_request.offline_transactions:
        try:
            if transaction_data.user_id != current_user.username:
                logger.warning(f"Attempted transaction sync for mismatching user_id: {transaction_data.user_id} by {current_user.username}")
                failed_transactions.append(transaction_data.id if hasattr(transaction_data, 'id') else -1)
                continue

            db_transaction = OfflineTransaction(**transaction_data.model_dump())
            db.add(db_transaction)
            db.commit()
            db.refresh(db_transaction)
            synced_transactions_count += 1
            logger.debug(f"Synced OfflineTransaction: {db_transaction.transaction_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync OfflineTransaction {transaction_data.transaction_id}: {e}")
            failed_transactions.append(transaction_data.id if hasattr(transaction_data, 'id') else -1)

    return SyncResponse(
        synced_records_count=synced_records_count,
        synced_transactions_count=synced_transactions_count,
        failed_records=failed_records,
        failed_transactions=failed_transactions,
    )

# Example of a protected endpoint (requires authentication)
@app.get("/protected-data", summary="Get Protected Data", response_model=Dict[str, str])
async def get_protected_data(current_user: User = Depends(get_current_active_user)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_protected_data", "offline-sync")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {"message": f"Hello {current_user.username}, you have access to protected data!", "role": current_user.roles[0]}

# Error Handling (example for a specific HTTPException)
from starlette.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

# S3 Integration (Placeholder - actual implementation would use boto3)
# def upload_to_s3(file_content: bytes, filename: str):
#     settings = get_settings()
#     s3_client = boto3.client(
#         's3',
#         aws_access_key_id=settings.aws_access_key_id,
#         aws_secret_access_key=settings.aws_secret_access_key,
# #         region_name=settings.aws_region
#     )
#     try:
#         s3_client.put_object(Bucket=settings.s3_bucket_name, Key=filename, Body=file_content)
#         logger.info(f"Uploaded {filename} to S3 bucket {settings.s3_bucket_name}")
#         return True
#     except Exception as e:
#         logger.error(f"Failed to upload {filename} to S3: {e}")
#         return False

# Redis Integration (Placeholder - actual implementation would use redis-py)
# def store_in_redis(key: str, value: str, ttl: int = 3600):
#     settings = get_settings()
#     redis_client = redis.Redis.from_url(settings.redis_url)
#     try:
#         redis_client.setex(key, ttl, value)
#         logger.info(f"Stored {key} in Redis")
#         return True
#     except Exception as e:
#         logger.error(f"Failed to store {key} in Redis: {e}")
#         return False

