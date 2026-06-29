from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import status, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
import logging

from .. import models, schemas
from ..config import settings
from ..database import get_db

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class SecurityServiceException(HTTPException):
    """
    Custom exception for business logic errors in the SecurityService.
    """
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)

# --- Utility Functions ---

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# --- Security Service Class ---

class SecurityService:
    """
    Business logic layer for User, Role, and Permission management.
    """
    def __init__(self, db: Session):
        self.db = db

    # --- User CRUD Operations ---

    def create_user(self, user_in: schemas.UserCreate) -> models.User:
        """Creates a new user and assigns initial roles."""
        if self.db.query(models.User).filter(models.User.email == user_in.email).first():
            raise SecurityServiceException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists.")

        hashed_password = hash_password(user_in.password)
        db_user = models.User(
            email=user_in.email,
            hashed_password=hashed_password,
            is_superuser=user_in.is_superuser
        )

        # Assign roles
        roles = self.db.query(models.Role).filter(models.Role.id.in_(user_in.role_ids)).all()
        if len(roles) != len(user_in.role_ids):
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more role IDs are invalid.")
        db_user.roles.extend(roles)

        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            logger.info(f"User created: {db_user.email}")
            return db_user
        except IntegrityError:
            self.db.rollback()
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integrity error during user creation.")

    def get_user(self, user_id: int) -> models.User:
        """Retrieves a user by ID."""
        user = self.db.query(models.User).options(joinedload(models.User.roles).joinedload(models.Role.permissions)).filter(models.User.id == user_id).first()
        if not user:
            raise SecurityServiceException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    def get_user_by_email(self, email: str) -> Optional[models.User]:
        """Retrieves a user by email."""
        return self.db.query(models.User).options(joinedload(models.User.roles).joinedload(models.Role.permissions)).filter(models.User.email == email).first()

    def get_users(self, skip: int = 0, limit: int = 100) -> List[models.User]:
        """Retrieves a list of users."""
        return self.db.query(models.User).options(joinedload(models.User.roles).joinedload(models.Role.permissions)).offset(skip).limit(limit).all()

    def update_user(self, user_id: int, user_in: schemas.UserUpdate) -> models.User:
        """Updates an existing user's details."""
        db_user = self.get_user(user_id) # Uses get_user for 404 check

        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        for key, value in update_data.items():
            setattr(db_user, key, value)

        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            logger.info(f"User updated: {db_user.email}")
            return db_user
        except IntegrityError:
            self.db.rollback()
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integrity error during user update (e.g., duplicate email).")

    def delete_user(self, user_id: int):
        """Deletes a user by ID."""
        db_user = self.get_user(user_id) # Uses get_user for 404 check
        self.db.delete(db_user)
        self.db.commit()
        logger.info(f"User deleted: ID {user_id}")

    # --- Role CRUD Operations ---

    def create_role(self, role_in: schemas.RoleCreate) -> models.Role:
        """Creates a new role and assigns initial permissions."""
        if self.db.query(models.Role).filter(models.Role.name == role_in.name).first():
            raise SecurityServiceException(status_code=status.HTTP_409_CONFLICT, detail="Role with this name already exists.")

        db_role = models.Role(
            name=role_in.name,
            description=role_in.description,
            is_default=role_in.is_default
        )

        # Assign permissions
        permissions = self.db.query(models.Permission).filter(models.Permission.id.in_(role_in.permission_ids)).all()
        if len(permissions) != len(role_in.permission_ids):
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more permission IDs are invalid.")
        db_role.permissions.extend(permissions)

        try:
            self.db.add(db_role)
            self.db.commit()
            self.db.refresh(db_role)
            logger.info(f"Role created: {db_role.name}")
            return db_role
        except IntegrityError:
            self.db.rollback()
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integrity error during role creation.")

    def get_role(self, role_id: int) -> models.Role:
        """Retrieves a role by ID."""
        role = self.db.query(models.Role).options(joinedload(models.Role.permissions)).filter(models.Role.id == role_id).first()
        if not role:
            raise SecurityServiceException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        return role

    def get_roles(self, skip: int = 0, limit: int = 100) -> List[models.Role]:
        """Retrieves a list of roles."""
        return self.db.query(models.Role).options(joinedload(models.Role.permissions)).offset(skip).limit(limit).all()

    def update_role(self, role_id: int, role_in: schemas.RoleUpdate) -> models.Role:
        """Updates an existing role's details."""
        db_role = self.get_role(role_id)

        update_data = role_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_role, key, value)

        try:
            self.db.add(db_role)
            self.db.commit()
            self.db.refresh(db_role)
            logger.info(f"Role updated: {db_role.name}")
            return db_role
        except IntegrityError:
            self.db.rollback()
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integrity error during role update (e.g., duplicate name).")

    def delete_role(self, role_id: int):
        """Deletes a role by ID."""
        db_role = self.get_role(role_id)
        self.db.delete(db_role)
        self.db.commit()
        logger.info(f"Role deleted: ID {role_id}")

    # --- Permission CRUD Operations ---

    def create_permission(self, permission_in: schemas.PermissionCreate) -> models.Permission:
        """Creates a new permission."""
        if self.db.query(models.Permission).filter(models.Permission.name == permission_in.name).first():
            raise SecurityServiceException(status_code=status.HTTP_409_CONFLICT, detail="Permission with this name already exists.")

        db_permission = models.Permission(**permission_in.model_dump())

        try:
            self.db.add(db_permission)
            self.db.commit()
            self.db.refresh(db_permission)
            logger.info(f"Permission created: {db_permission.name}")
            return db_permission
        except IntegrityError:
            self.db.rollback()
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integrity error during permission creation.")

    def get_permission(self, permission_id: int) -> models.Permission:
        """Retrieves a permission by ID."""
        permission = self.db.query(models.Permission).filter(models.Permission.id == permission_id).first()
        if not permission:
            raise SecurityServiceException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
        return permission

    def get_permissions(self, skip: int = 0, limit: int = 100) -> List[models.Permission]:
        """Retrieves a list of permissions."""
        return self.db.query(models.Permission).offset(skip).limit(limit).all()

    def update_permission(self, permission_id: int, permission_in: schemas.PermissionUpdate) -> models.Permission:
        """Updates an existing permission's details."""
        db_permission = self.get_permission(permission_id)

        update_data = permission_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_permission, key, value)

        try:
            self.db.add(db_permission)
            self.db.commit()
            self.db.refresh(db_permission)
            logger.info(f"Permission updated: {db_permission.name}")
            return db_permission
        except IntegrityError:
            self.db.rollback()
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integrity error during permission update (e.g., duplicate name).")

    def delete_permission(self, permission_id: int):
        """Deletes a permission by ID."""
        db_permission = self.get_permission(permission_id)
        self.db.delete(db_permission)
        self.db.commit()
        logger.info(f"Permission deleted: ID {permission_id}")

    # --- Role/Permission Assignment Operations ---

    def assign_role_to_user(self, user_id: int, role_id: int) -> models.User:
        """Assigns a role to a user."""
        db_user = self.get_user(user_id)
        db_role = self.get_role(role_id)

        if db_role in db_user.roles:
            raise SecurityServiceException(status_code=status.HTTP_409_CONFLICT, detail="Role is already assigned to this user.")

        db_user.roles.append(db_role)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def remove_role_from_user(self, user_id: int, role_id: int) -> models.User:
        """Removes a role from a user."""
        db_user = self.get_user(user_id)
        db_role = self.get_role(role_id)

        if db_role not in db_user.roles:
            raise SecurityServiceException(status_code=status.HTTP_404_NOT_FOUND, detail="Role is not assigned to this user.")

        db_user.roles.remove(db_role)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def assign_permission_to_role(self, role_id: int, permission_id: int) -> models.Role:
        """Assigns a permission to a role."""
        db_role = self.get_role(role_id)
        db_permission = self.get_permission(permission_id)

        if db_permission in db_role.permissions:
            raise SecurityServiceException(status_code=status.HTTP_409_CONFLICT, detail="Permission is already assigned to this role.")

        db_role.permissions.append(db_permission)
        self.db.commit()
        self.db.refresh(db_role)
        return db_role

    def remove_permission_from_role(self, role_id: int, permission_id: int) -> models.Role:
        """Removes a permission from a role."""
        db_role = self.get_role(role_id)
        db_permission = self.get_permission(permission_id)

        if db_permission not in db_role.permissions:
            raise SecurityServiceException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission is not assigned to this role.")

        db_role.permissions.remove(db_permission)
        self.db.commit()
        self.db.refresh(db_role)
        return db_role

    # --- Authentication and Authorization ---

    def authenticate_user_and_create_token(self, email: str, password: str) -> schemas.Token:
        """Authenticates a user and generates an access token."""
        user = self.get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise SecurityServiceException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        if not user.is_active:
            raise SecurityServiceException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )

        # Collect all unique permissions (scopes) for the user
        permissions = set()
        for role in user.roles:
            for permission in role.permissions:
                permissions.add(permission.name)

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "scopes": list(permissions)},
            expires_delta=access_token_expires
        )
        logger.info(f"Token generated for user: {user.email}")
        return schemas.Token(access_token=access_token, token_type="bearer")

# --- FastAPI Dependencies for Authorization ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/token")

def get_current_user_from_token(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    """Decodes JWT token and retrieves the user from the database."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise SecurityServiceException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials (no user ID).")
        token_data = schemas.TokenData(user_id=int(user_id), scopes=payload.get("scopes", []))
    except JWTError:
        raise SecurityServiceException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials (invalid token).")

    service = SecurityService(db)
    user = service.get_user(token_data.user_id)
    if user is None:
        raise SecurityServiceException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user

def get_current_active_user(current_user: models.User = Depends(get_current_user_from_token)) -> schemas.UserRead:
    """Ensures the user is active."""
    if not current_user.is_active:
        raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user.")
    return schemas.UserRead.model_validate(current_user)

def get_current_superuser(current_user: models.User = Depends(get_current_user_from_token)) -> schemas.UserRead:
    """Ensures the user is a superuser."""
    if not current_user.is_superuser:
        raise SecurityServiceException(status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges (superuser required).")
    return schemas.UserRead.model_validate(current_user)

def has_permission(required_permission: str):
    """
    Dependency factory to check if the current user has a specific permission.
    """
    def permission_checker(current_user: models.User = Depends(get_current_user_from_token)) -> schemas.UserRead:
        if not current_user.is_active:
            raise SecurityServiceException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user.")

        # Superusers bypass permission checks
        if current_user.is_superuser:
            return schemas.UserRead.model_validate(current_user)

        # Collect all unique permissions (scopes) for the user
        user_permissions = set()
        for role in current_user.roles:
            for permission in role.permissions:
                user_permissions.add(permission.name)

        if required_permission not in user_permissions:
            raise SecurityServiceException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have the required permission: '{required_permission}'",
            )
        return schemas.UserRead.model_validate(current_user)
    return permission_checker
