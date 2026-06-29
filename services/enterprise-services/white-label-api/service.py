import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from . import models, schemas
from .config import settings
from passlib.context import CryptContext
import secrets
import string
import json

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Security Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def generate_api_key(length: int = 32) -> str:
    """Generates a secure, random API key."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# --- Custom Exceptions ---
class ServiceException(Exception):
    """Base class for service-layer exceptions."""
    def __init__(self, detail: str, code: str, status_code: int = 400):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(self.detail)

class NotFoundException(ServiceException):
    def __init__(self, detail: str):
        super().__init__(detail, "NOT_FOUND", 404)

class ConflictException(ServiceException):
    def __init__(self, detail: str):
        super().__init__(detail, "CONFLICT", 409)

class UnauthorizedException(ServiceException):
    def __init__(self, detail: str = "Invalid API Key"):
        super().__init__(detail, "UNAUTHORIZED", 401)

# --- Partner Service ---

def create_partner(db: Session, partner_data: schemas.PartnerCreate) -> schemas.PartnerResponse:
    """Creates a new partner and generates a secure API key."""
    logger.info(f"Attempting to create new partner: {partner_data.name}")
    
    # 1. Generate API Key and Hash
    raw_api_key = generate_api_key()
    api_key_hash = get_password_hash(raw_api_key)
    
    db_partner = models.Partner(
        name=partner_data.name,
        api_key_hash=api_key_hash,
        is_active=partner_data.is_active
    )
    
    try:
        db.add(db_partner)
        db.commit()
        db.refresh(db_partner)
        logger.info(f"Partner created successfully with ID: {db_partner.id}")
        
        # Return the raw API key ONLY on creation
        response = schemas.PartnerResponse.model_validate(db_partner)
        response.api_key = raw_api_key
        return response
    except IntegrityError:
        db.rollback()
        logger.warning(f"Partner creation failed due to name conflict: {partner_data.name}")
        raise ConflictException(f"Partner with name '{partner_data.name}' already exists.")

def get_partner_by_api_key(db: Session, api_key: str) -> models.Partner:
    """Authenticates a partner using the provided API key."""
    # Note: This is an inefficient way to authenticate, as it requires iterating through all hashes.
    # In a real production system, a more complex, indexed key management system would be used.
    # However, for this exercise, we'll stick to a simple, secure hash comparison.
    
    partners = db.query(models.Partner).filter(models.Partner.is_active == True).all()
    
    for partner in partners:
        if verify_password(api_key, partner.api_key_hash):
            logger.debug(f"Partner authenticated: {partner.name}")
            return partner
            
    logger.warning("Authentication failed for provided API key.")
    raise UnauthorizedException()

# --- Verification Request Service ---

def create_verification_request(db: Session, partner_id: int, request_data: schemas.VerificationRequestCreate) -> models.VerificationRequest:
    """Creates a new verification request."""
    logger.info(f"Creating verification request for partner {partner_id} with ref_id: {request_data.external_ref_id}")
    
    db_request = models.VerificationRequest(
        partner_id=partner_id,
        external_ref_id=request_data.external_ref_id,
        verification_type=request_data.verification_type,
        subject_data=json.dumps(request_data.subject_data), # Convert dict to JSON string for storage
        status=models.VerificationStatus.PENDING # Always start as PENDING
    )
    
    try:
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        logger.info(f"Verification request created with ID: {db_request.id}")
        return db_request
    except IntegrityError:
        db.rollback()
        logger.warning(f"Request creation failed due to conflict: partner_id={partner_id}, ref_id={request_data.external_ref_id}")
        raise ConflictException(f"Request with external_ref_id '{request_data.external_ref_id}' already exists for this partner.")

def get_verification_request(db: Session, request_id: int, partner_id: int) -> models.VerificationRequest:
    """Retrieves a specific verification request for a partner."""
    db_request = db.query(models.VerificationRequest).filter(
        models.VerificationRequest.id == request_id,
        models.VerificationRequest.partner_id == partner_id
    ).first()
    
    if not db_request:
        logger.warning(f"Verification request not found: ID={request_id}, Partner={partner_id}")
        raise NotFoundException(f"Verification request with ID {request_id} not found.")
        
    return db_request

def list_verification_requests(db: Session, partner_id: int, skip: int = 0, limit: int = 100) -> List[models.VerificationRequest]:
    """Lists all verification requests for a partner."""
    return db.query(models.VerificationRequest).filter(
        models.VerificationRequest.partner_id == partner_id
    ).offset(skip).limit(limit).all()

def count_verification_requests(db: Session, partner_id: int) -> int:
    """Counts all verification requests for a partner."""
    return db.query(models.VerificationRequest).filter(
        models.VerificationRequest.partner_id == partner_id
    ).count()

def update_verification_request(db: Session, request_id: int, partner_id: int, update_data: schemas.VerificationRequestUpdate) -> models.VerificationRequest:
    """Updates the status and result details of a verification request."""
    db_request = get_verification_request(db, request_id, partner_id)
    
    update_data_dict = update_data.model_dump(exclude_unset=True)
    
    if not update_data_dict:
        logger.info(f"No update data provided for request ID: {request_id}")
        return db_request
        
    logger.info(f"Updating verification request ID: {request_id} with data: {update_data_dict}")
    
    for key, value in update_data_dict.items():
        if key == "result_details" and value is not None:
            setattr(db_request, key, json.dumps(value)) # Convert dict to JSON string for storage
        else:
            setattr(db_request, key, value)
        
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    logger.info(f"Verification request ID: {request_id} updated successfully.")
    return db_request

def delete_verification_request(db: Session, request_id: int, partner_id: int):
    """Deletes a verification request."""
    db_request = get_verification_request(db, request_id, partner_id)
    
    logger.warning(f"Deleting verification request ID: {request_id}")
    db.delete(db_request)
    db.commit()
    logger.info(f"Verification request ID: {request_id} deleted successfully.")
    return {"message": "Request deleted successfully"}