import logging
import os
from datetime import datetime, timedelta
from typing import Annotated

import jwt
from fastapi import FastAPI, Depends, HTTPException, status, Request
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel
from starlette.responses import JSONResponse

from .config import settings
from .models import Base, User, Message, MessageCreate, MessageResponse, UserCreate, UserResponse, Token, TokenData

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

# --- Logging Configuration ---
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Configuration ---
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create database tables
Base.metadata.create_all(bind=engine)

# --- FastAPI Application Instance ---
app = FastAPI(
    title="SMS Service API",
    description="API for sending and managing SMS messages",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

# --- Security (Authentication & Authorization) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
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
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# --- Exception Handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled Exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An unexpected error occurred."},
    )

# --- API Endpoints ---

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
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

@app.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"User created: {db_user.username}")
    return db_user

@app.get("/users/me/", response_model=UserResponse)
async def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user

@app.post("/sms/send", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_sms(
    message_data: MessageCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db)
):
    logger.info(f"User {current_user.username} attempting to send SMS to {message_data.recipient}")
    try:
        import httpx
        sms_provider = os.getenv("SMS_PROVIDER", "africas_talking")
        sms_api_key = os.getenv("SMS_API_KEY", "")
        sms_sender_id = os.getenv("SMS_SENDER_ID", "AgentBank")

        status_str = "failed"
        delivery_report_str = ""
        sent_at_dt = datetime.utcnow()

        if sms_api_key:
            if sms_provider == "africas_talking":
                at_url = "https://api.africastalking.com/version1/messaging"
                at_username = os.getenv("AT_USERNAME", "sandbox")
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        at_url,
                        headers={
                            "apiKey": sms_api_key,
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                        data={
                            "username": at_username,
                            "to": message_data.recipient,
                            "message": message_data.content,
                            "from": sms_sender_id,
                        },
                    )
                    if resp.status_code in (200, 201):
                        resp_data = resp.json()
                        recipients = resp_data.get("SMSMessageData", {}).get("Recipients", [])
                        if recipients and recipients[0].get("status") == "Success":
                            status_str = "sent"
                            delivery_report_str = recipients[0].get("messageId", "")
                        else:
                            delivery_report_str = str(resp_data)
                    else:
                        delivery_report_str = f"HTTP {resp.status_code}: {resp.text[:200]}"

            elif sms_provider == "twilio":
                twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
                twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
                twilio_from = os.getenv("TWILIO_FROM_NUMBER", "")
                twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        twilio_url,
                        auth=(twilio_sid, twilio_token),
                        data={
                            "To": message_data.recipient,
                            "From": twilio_from,
                            "Body": message_data.content,
                        },
                    )
                    if resp.status_code in (200, 201):
                        resp_data = resp.json()
                        status_str = "sent"
                        delivery_report_str = resp_data.get("sid", "")
                    else:
                        delivery_report_str = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                logger.warning(f"Unknown SMS provider: {sms_provider}")
                delivery_report_str = f"Unknown provider: {sms_provider}"
        else:
            logger.warning("SMS_API_KEY not configured, message stored but not sent")
            status_str = "queued"
            delivery_report_str = f"queued_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        db_message = Message(
            sender=message_data.sender,
            recipient=message_data.recipient,
            content=message_data.content,
            status=status_str,
            sent_at=sent_at_dt,
            delivery_report=delivery_report_str
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        logger.info(f"SMS sent successfully: {db_message.id} to {db_message.recipient}")
        return db_message
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send SMS")

@app.get("/sms/{message_id}", response_model=MessageResponse)
async def get_message_status(
    message_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db)
):
    logger.info(f"User {current_user.username} requesting status for message {message_id}")
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message

# --- Health Checks and Metrics ---
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    # In a real application, this would check database connection, external services (Redis, S3, SMS provider)
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1")) # Check DB connection
        db.close()
        # Add checks for Redis, S3, etc. here
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable")

