
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
import os

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

from .models import Base, User, Document, Permission, UserCreate, UserInDB, DocumentCreate, DocumentInDB, PermissionCreate, PermissionInDB, Token, TokenData

# --- Configuration --- #
# In a real application, these would come from environment variables or a config file
from dotenv import load_dotenv
import os

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

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/document_management")

# For production, restrict origins to your frontend domain
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
]

# --- Logging Setup --- #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Setup --- #
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Security Setup --- #
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
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

# --- FastAPI Application --- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Document Management Service starting up...")
    yield
    # Shutdown logic
    logger.info("Document Management Service shutting down...")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Document Management Service", version="1.0.0", lifespan=lifespan)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- API Endpoints --- #

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"User created: {db_user.username}")
    return db_user

@app.get("/users/me/", response_model=UserInDB)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/documents/", response_model=DocumentInDB, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str,
    file_type: str,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    bucket_name = os.getenv('S3_BUCKET_NAME', 'agent-banking-documents')
    s3_key = f"documents/{current_user.id}/{file.filename}"
    s3_file_path = f"s3://{bucket_name}/{s3_key}"
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'eu-west-1'),
            endpoint_url=os.getenv('S3_ENDPOINT_URL'),
        )
        s3_client.upload_fileobj(
            file.file,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': file.content_type or 'application/octet-stream'}
        )
        logger.info(f"S3 upload complete: {s3_file_path}")
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File storage error: {e}")
    file_location = s3_file_path

    db_document = Document(
        title=title,
        description=description,
        file_path=file_location,
        file_type=file_type,
        owner_id=current_user.id
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    logger.info(f"Document '{title}' uploaded by user {current_user.username}")
    return db_document

@app.get("/documents/", response_model=List[DocumentInDB])
async def get_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = db.query(Document).filter(Document.owner_id == current_user.id).all()
    return documents

@app.get("/documents/{document_id}", response_model=DocumentInDB)
async def get_document_by_id(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Check if current user is owner or has read permission
    if document.owner_id != current_user.id:
        permission = db.query(Permission).filter(
            Permission.user_id == current_user.id,
            Permission.document_id == document_id,
            Permission.can_read == True
        ).first()
        if not permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this document")
    return document

@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Check if current user is owner or has delete permission
    if document.owner_id != current_user.id:
        permission = db.query(Permission).filter(
            Permission.user_id == current_user.id,
            Permission.document_id == document_id,
            Permission.can_delete == True
        ).first()
        if not permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this document")
    
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    bucket_name = os.getenv('S3_BUCKET_NAME', 'agent-banking-documents')
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'eu-west-1'),
            endpoint_url=os.getenv('S3_ENDPOINT_URL'),
        )
        s3_key = document.file_path.replace(f"s3://{bucket_name}/", "")
        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        logger.info(f"S3 deletion complete: {document.file_path}")
    except (ClientError, NoCredentialsError) as e:
        logger.warning(f"S3 deletion failed (proceeding with DB delete): {e}")

    db.delete(document)
    db.commit()
    logger.info(f"Document {document_id} deleted by user {current_user.username}")
    return

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Document Management Service is running"}

# Metrics (basic example)
@app.get("/metrics")
async def get_metrics():
    # In a real application, integrate with Prometheus or similar
    total_documents = db.query(Document).count()
    total_users = db.query(User).count()
    return {"total_documents": total_documents, "total_users": total_users}

@app.post("/permissions/", response_model=PermissionInDB, status_code=status.HTTP_201_CREATED)
async def grant_permission(
    permission_create: PermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only document owner can grant permissions
    document = db.query(Document).filter(Document.id == permission_create.document_id).first()
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to grant permissions for this document")

    # Check if permission already exists
    db_permission = db.query(Permission).filter(
        Permission.user_id == permission_create.user_id,
        Permission.document_id == permission_create.document_id
    ).first()

    if db_permission:
        # Update existing permission
        db_permission.can_read = permission_create.can_read
        db_permission.can_write = permission_create.can_write
        db_permission.can_delete = permission_create.can_delete
    else:
        # Create new permission
        db_permission = Permission(**permission_create.dict())
        db.add(db_permission)
    
    db.commit()
    db.refresh(db_permission)
    logger.info(f"Permission granted/updated for user {permission_create.user_id} on document {permission_create.document_id} by {current_user.username}")
    return db_permission

@app.get("/permissions/{document_id}", response_model=List[PermissionInDB])
async def get_document_permissions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view permissions for this document")
    
    permissions = db.query(Permission).filter(Permission.document_id == document_id).all()
    return permissions

@app.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    permission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not db_permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    
    document = db.query(Document).filter(Document.id == db_permission.document_id).first()
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to revoke this permission")
    
    db.delete(db_permission)
    db.commit()
    logger.info(f"Permission {permission_id} revoked by {current_user.username}")
    return

