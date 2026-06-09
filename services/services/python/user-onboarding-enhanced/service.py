import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from models import User, KYCProfile, Document, OnboardingStatus, DocumentType, VerificationStatus
from schemas import UserCreate, UserUpdate, KYCProfileCreate, KYCProfileUpdate, DocumentUpload, DocumentUpdateStatus

# --- Configuration and Utilities ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# --- Custom Exceptions ---

class UserOnboardingException(Exception):
    """Base exception for the User Onboarding service."""
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail

class UserNotFound(UserOnboardingException):
    def __init__(self, user_id: int) -> None:
        super().__init__(status_code=404, detail=f"User with ID {user_id} not found.")

class EmailAlreadyExists(UserOnboardingException):
    def __init__(self, email: str) -> None:
        super().__init__(status_code=409, detail=f"User with email '{email}' already exists.")

class InvalidOnboardingStep(UserOnboardingException):
    def __init__(self, required_status: OnboardingStatus, current_status: OnboardingStatus) -> None:
        super().__init__(status_code=400, detail=f"Invalid step. Required status: {required_status.value}, current status: {current_status.value}.")

class KYCProfileExists(UserOnboardingException):
    def __init__(self, user_id: int) -> None:
        super().__init__(status_code=409, detail=f"KYC profile for user ID {user_id} already exists.")

class DocumentNotFound(UserOnboardingException):
    def __init__(self, document_id: int) -> None:
        super().__init__(status_code=404, detail=f"Document with ID {document_id} not found.")

# --- Service Class ---

class OnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- User CRUD and Step 1: Basic Info ---

    def create_user(self, user_data: UserCreate) -> User:
        if self.db.query(User).filter(User.email == user_data.email).first():
            raise EmailAlreadyExists(user_data.email)

        hashed_password = get_password_hash(user_data.password)
        
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            onboarding_status=OnboardingStatus.BASIC_INFO_COLLECTED
        )
        
        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            logger.info(f"User created and moved to {db_user.onboarding_status.value}: ID {db_user.id}")
            return db_user
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error during user creation: {e}")
            raise EmailAlreadyExists(user_data.email) # Re-raise as a more specific error if possible
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during user creation: {e}")
            raise UserOnboardingException(500, "An unexpected error occurred during user creation.")

    def get_user(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFound(user_id)
        return user

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).offset(skip).limit(limit).all()

    def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        db_user = self.get_user(user_id)
        
        update_data = user_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_user, key, value)
        
        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"User ID {user_id} updated.")
        return db_user

    def delete_user(self, user_id: int) -> Dict[str, Any]:
        db_user = self.get_user(user_id)
        self.db.delete(db_user)
        self.db.commit()
        logger.warning(f"User ID {user_id} deleted.")
        return {"message": f"User ID {user_id} successfully deleted."}

    # --- Step 2: Identity Information (KYC) ---

    def create_kyc_profile(self, user_id: int, kyc_data: KYCProfileCreate) -> KYCProfile:
        db_user = self.get_user(user_id)

        if db_user.onboarding_status.value not in [OnboardingStatus.BASIC_INFO_COLLECTED.value, OnboardingStatus.IDENTITY_INFO_COLLECTED.value]:
            raise InvalidOnboardingStep(OnboardingStatus.BASIC_INFO_COLLECTED, db_user.onboarding_status)

        if db_user.kyc_profile:
            raise KYCProfileExists(user_id)

        db_kyc = KYCProfile(**kyc_data.model_dump(), user_id=user_id)
        
        self.db.add(db_kyc)
        db_user.onboarding_status = OnboardingStatus.IDENTITY_INFO_COLLECTED
        
        self.db.commit()
        self.db.refresh(db_kyc)
        self.db.refresh(db_user)
        logger.info(f"KYC profile created for user ID {user_id}. Status updated to {db_user.onboarding_status.value}")
        return db_kyc

    def get_kyc_profile(self, user_id: int) -> KYCProfile:
        db_user = self.get_user(user_id)
        if not db_user.kyc_profile:
            raise UserOnboardingException(404, f"KYC profile not found for user ID {user_id}.")
        return db_user.kyc_profile

    # --- Step 3: Document Upload ---

    def upload_document(self, user_id: int, doc_data: DocumentUpload) -> Document:
        db_user = self.get_user(user_id)

        if db_user.onboarding_status.value not in [OnboardingStatus.IDENTITY_INFO_COLLECTED.value, OnboardingStatus.DOCUMENTS_UPLOADED.value, OnboardingStatus.VERIFICATION_FAILED.value]:
            raise InvalidOnboardingStep(OnboardingStatus.IDENTITY_INFO_COLLECTED, db_user.onboarding_status)

        # Check for existing document of the same type to prevent duplicates (optional logic)
        existing_doc = self.db.query(Document).filter(
            Document.user_id == user_id,
            Document.document_type == doc_data.document_type
        ).first()

        if existing_doc:
            # Update existing document instead of creating a new one
            existing_doc.file_path = doc_data.file_path
            existing_doc.upload_date = datetime.utcnow()
            existing_doc.verification_status = VerificationStatus.PENDING
            db_doc = existing_doc
            logger.info(f"Document type {doc_data.document_type.value} updated for user ID {user_id}.")
        else:
            db_doc = Document(**doc_data.model_dump(), user_id=user_id)
            self.db.add(db_doc)
            logger.info(f"Document type {doc_data.document_type.value} uploaded for user ID {user_id}.")

        # Update user status to DOCUMENTS_UPLOADED if it was IDENTITY_INFO_COLLECTED
        if db_user.onboarding_status == OnboardingStatus.IDENTITY_INFO_COLLECTED:
            db_user.onboarding_status = OnboardingStatus.DOCUMENTS_UPLOADED
        
        self.db.commit()
        self.db.refresh(db_doc)
        self.db.refresh(db_user)
        return db_doc

    def get_documents(self, user_id: int) -> List[Document]:
        self.get_user(user_id) # Check if user exists
        return self.db.query(Document).filter(Document.user_id == user_id).all()

    # --- Step 4: Verification (Admin/Internal Endpoint) ---

    def update_document_status(self, doc_id: int, status_data: DocumentUpdateStatus) -> Document:
        db_doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if not db_doc:
            raise DocumentNotFound(doc_id)

        db_doc.verification_status = status_data.verification_status
        db_doc.rejection_reason = status_data.rejection_reason
        
        self.db.commit()
        self.db.refresh(db_doc)
        logger.info(f"Document ID {doc_id} status updated to {db_doc.verification_status.value}.")
        
        # Trigger check for overall onboarding completion
        self._check_onboarding_completion(db_doc.user_id)
        
        return db_doc

    def _check_onboarding_completion(self, user_id: int) -> None:
        """Internal method to check if all documents are verified and update user status."""
        db_user = self.get_user(user_id)
        
        if db_user.onboarding_status.value not in [OnboardingStatus.DOCUMENTS_UPLOADED.value, OnboardingStatus.VERIFICATION_PENDING.value, OnboardingStatus.VERIFICATION_FAILED.value]:
            return # Only check if user is in a document-related status

        documents = self.get_documents(user_id)
        
        if not documents:
            return # No documents to check

        all_verified = all(doc.verification_status == VerificationStatus.VERIFIED for doc in documents)
        any_rejected = any(doc.verification_status == VerificationStatus.REJECTED for doc in documents)
        any_pending = any(doc.verification_status == VerificationStatus.PENDING for doc in documents)
        
        new_status = db_user.onboarding_status
        
        if all_verified:
            new_status = OnboardingStatus.VERIFICATION_SUCCESS
            db_user.is_active = True
        elif any_rejected:
            new_status = OnboardingStatus.VERIFICATION_FAILED
            db_user.is_active = False
        elif any_pending:
            new_status = OnboardingStatus.VERIFICATION_PENDING
        else:
            # Should not happen if all documents have a status
            pass

        if new_status != db_user.onboarding_status:
            db_user.onboarding_status = new_status
            self.db.commit()
            self.db.refresh(db_user)
            logger.info(f"User ID {user_id} overall onboarding status updated to {new_status.value}.")

    # --- Step 5: Final Review/Completion ---

    def complete_onboarding(self, user_id: int) -> User:
        db_user = self.get_user(user_id)

        if db_user.onboarding_status != OnboardingStatus.VERIFICATION_SUCCESS:
            raise InvalidOnboardingStep(OnboardingStatus.VERIFICATION_SUCCESS, db_user.onboarding_status)

        db_user.onboarding_status = OnboardingStatus.ONBOARDING_COMPLETE
        db_user.is_active = True
        
        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"User ID {user_id} onboarding complete.")
        return db_user

    # --- Authentication Helper (for use in router) ---
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        db_user = self.db.query(User).filter(User.email == email).first()
        if not db_user:
            return None
        if not verify_password(password, db_user.hashed_password):
            return None
        return db_user

    # --- Utility for fetching user with relations for response ---
    def get_user_with_relations(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFound(user_id)
        # Manually load relations for the response schema
        user.kyc_profile # Access to load
        user.documents # Access to load
        return user