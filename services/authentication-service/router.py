import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import get_db, get_settings
from models import (
    Base,
    User,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    Token,
    TokenData,
    AuthActivityLog,
    AuthActivityLogCreate,
    UserPasswordUpdate,
)

# --- Configuration and Setup ---

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
logger = logging.getLogger(__name__)

# --- Utility Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def log_activity(db: Session, user_id: int, activity_type: str, request: Request, details: Optional[str] = None):
    """Log an authentication activity."""
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    
    log_data = AuthActivityLogCreate(
        user_id=user_id,
        activity_type=activity_type,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db_log = AuthActivityLog(**log_data.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Activity logged for user {user_id}: {activity_type}")

# --- Dependencies ---

async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """
    Dependency to get the current authenticated user from the JWT token.
    Raises HTTPException if token is invalid or user is not found/inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure the current user is an active superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user

# --- Authentication Endpoints ---

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db), request: Request = None):
    """
    Registers a new user.
    """
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists",
        )

    hashed_password = get_password_hash(user_in.password)
    user_data = user_in.model_dump(exclude={"password"})
    db_user = User(**user_data, hashed_password=hashed_password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    log_activity(db, db_user.id, "REGISTRATION_SUCCESS", request, "New user registered.")
    logger.info(f"User registered: {db_user.email}")
    return db_user

@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Authenticates a user and returns an access token.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        log_activity(db, 0, "LOGIN_FAILURE", request, f"Failed login attempt for email: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        log_activity(db, user.id, "LOGIN_FAILURE", request, "User account is inactive.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email}, expires_delta=access_token_expires
    )
    
    log_activity(db, user.id, "LOGIN_SUCCESS", request, "User successfully logged in.")
    logger.info(f"User logged in: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user's details.
    """
    return current_user

@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    password_update: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Allows an authenticated user to change their password.
    """
    if not verify_password(password_update.old_password, current_user.hashed_password):
        log_activity(db, current_user.id, "PASSWORD_CHANGE_FAILURE", request, "Incorrect old password provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )
    
    if password_update.old_password == password_update.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password",
        )

    current_user.hashed_password = get_password_hash(password_update.new_password)
    db.add(current_user)
    db.commit()
    
    log_activity(db, current_user.id, "PASSWORD_CHANGE_SUCCESS", request, "User successfully changed password.")
    logger.info(f"Password changed for user: {current_user.email}")
    return

# --- Admin/Superuser Endpoints (CRUD for Users) ---

@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """
    Retrieve a list of users. Requires superuser privileges.
    """
    users = db.query(User).offset(skip).limit(limit).all()
    total = db.query(User).count()
    return UserListResponse(users=users, total=total)

@router.get("/users/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """
    Get a specific user by ID. Requires superuser privileges.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """
    Update an existing user's details. Requires superuser privileges.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    
    log_activity(db, current_user.id, "USER_UPDATE", request, f"Superuser updated user ID: {user_id}")
    logger.info(f"User updated by superuser: {user.email}")
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """
    Delete a user. Requires superuser privileges.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
    
    log_activity(db, current_user.id, "USER_DELETE", request, f"Superuser deleted user ID: {user_id}")
    logger.warning(f"User deleted by superuser: {user.email}")
    return

# --- Activity Log Endpoint (Admin Only) ---

@router.get("/activity-logs", response_model=List[AuthActivityLog])
def list_activity_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
):
    """
    Retrieve a list of authentication activity logs. Requires superuser privileges.
    """
    logs = db.query(AuthActivityLog).order_by(AuthActivityLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs
