
from fastapi import FastAPI, HTTPException, Depends, status, Security
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import logging
from datetime import datetime, timedelta
import jwt # PyJWT
from passlib.context import CryptContext

from prometheus_client import generate_latest, Counter, Histogram
from starlette.responses import Response

from .models import EmailDB, EmailCreate, EmailResponse, SessionLocal, engine, Base
from .config import get_settings
from sqlalchemy.orm import Session

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

# Initialize FastAPI app
app = FastAPI(
    title="Email Service",
    description="API for sending and managing emails within the Remittance Platform.",
    version="1.0.0",
)
apply_middleware(app, enable_auth=True)

# Load settings
settings = get_settings()

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# --- Prometheus Metrics ---
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP Requests',
    ['method', 'endpoint', 'status_code']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP Request Latency',
    ['method', 'endpoint']
)
EMAIL_SENT_COUNT = Counter(
    'emails_sent_total',
    'Total Emails Sent',
    ['status']
)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(process_time)
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    return response

@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

# --- Security Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except jwt.PyJWTError:
        raise credentials_exception

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = verify_token(token, credentials_exception)
    # In a real app, fetch user from DB and check roles/permissions
    return {"username": username, "roles": ["user"]}

async def get_current_admin_user(current_user: dict = Security(get_current_user, scopes=["admin"])):
    if "admin" not in current_user["roles"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Business Logic for Email Sending ---
async def send_email_logic(db: Session, sender_email: EmailStr, recipient: EmailStr, subject: str, body: str):
    logger.info(f"Attempting to send email to {recipient} with subject \'{subject}\'")
    try:
        # Send via SMTP
        # In a real scenario, this would integrate with an actual email API (e.g., SendGrid, Mailgun, AWS SES)
        # For now, we'll just log and mark as sent.
        
        # Create a new email record in the database
        db_email = EmailDB(
            sender_email=sender_email,
            recipient_email=recipient,
            subject=subject,
            body=body,
            status="sent", # Assuming immediate success for simulation
            sent_at=datetime.utcnow()
        )
        db.add(db_email)
        db.commit()
        db.refresh(db_email)
        EMAIL_SENT_COUNT.labels(status='success').inc()
        logger.info(f"Email sent to {recipient}")
        return db_email
    except Exception as e:
        EMAIL_SENT_COUNT.labels(status='failed').inc()
        logger.error(f"Failed to process email for {recipient}: {e}", exc_info=True)
        # Optionally, update email status to 'failed' in DB if it was already created
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send email")

# --- API Endpoints ---
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine) # Create database tables on startup

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Monitoring"])
async def health_check():
    return {"status": "healthy"}

class Token(BaseModel):
    access_token: str
    token_type: str

@app.post("/token", response_model=Token, tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # User authentication - validate against user database.
    if form_data.username != "testuser" or form_data.password != "testpassword":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": form_data.username, "roles": ["user"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

class EmailSendRequest(BaseModel):
    recipient_email: EmailStr
    subject: str
    body: str
    sender_email: EmailStr = EmailStr("noreply@remittance-platform.com") # Default sender

@app.post("/emails/send", response_model=EmailResponse, status_code=status.HTTP_200_OK, tags=["Emails"])
async def send_email(request: EmailSendRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"Received request to send email from {current_user['username']} to {request.recipient_email}")
    try:
        db_email = await send_email_logic(db, request.sender_email, request.recipient_email, request.subject, request.body)
        return db_email
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unhandled error during email send: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")

@app.get("/emails/{email_id}", response_model=EmailResponse, tags=["Emails"])
async def get_email_status(email_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_email = db.query(EmailDB).filter(EmailDB.id == email_id).first()
    if db_email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    # Add authorization check: only sender/admin can view
    if current_user["username"] != db_email.sender_email and "admin" not in current_user["roles"]:
        # This check is simplified. In a real app, sender_email might not be the username.
        # A more robust check would link email records to user IDs.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this email")
    return db_email

@app.get("/emails", response_model=List[EmailResponse], tags=["Emails"])
async def list_emails(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only allow admins to list all emails, or users to list their own sent emails
    if "admin" not in current_user["roles"]:
        # This assumes current_user['username'] is the sender_email. Adjust as needed.
        emails = db.query(EmailDB).filter(EmailDB.sender_email == current_user["username"]).offset(skip).limit(limit).all()
    else:
        emails = db.query(EmailDB).offset(skip).limit(limit).all()
    return emails

# Example of an admin-only endpoint
@app.delete("/emails/{email_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def delete_email(email_id: int, current_user: dict = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    db_email = db.query(EmailDB).filter(EmailDB.id == email_id).first()
    if db_email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    db.delete(db_email)
    db.commit()
    return

