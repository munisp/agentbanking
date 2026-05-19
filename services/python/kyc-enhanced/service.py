import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update, delete
from fastapi import status

from models import EnhancedKYCCase, EDDDetail, CaseStatus
from schemas import EnhancedKYCCaseCreate, EnhancedKYCCaseUpdate, EDDDetailCreate, EDDDetailUpdate
from main import KYCServiceException # Import custom exception

logger = logging.getLogger(__name__)

# --- Custom Service Exceptions ---

class CaseNotFoundError(KYCServiceException):
    def __init__(self, case_id: int) -> None:
        super().__init__(
            name="CaseNotFoundError",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Enhanced Case with ID {case_id} not found."
        )

class CaseAlreadyExistsError(KYCServiceException):
    def __init__(self, customer_id: str) -> None:
        super().__init__(
            name="CaseAlreadyExistsError",
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active KYC Enhanced Case already exists for customer ID {customer_id}."
        )

class EDDDetailNotFoundError(KYCServiceException):
    def __init__(self, case_id: int) -> None:
        super().__init__(
            name="EDDDetailNotFoundError",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EDD Details for Case ID {case_id} not found."
        )

# --- Service Class ---

class KYCService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- EnhancedKYCCase CRUD Operations ---

    def create_case(self, case_data: EnhancedKYCCaseCreate) -> EnhancedKYCCase:
        """Creates a new Enhanced KYC Case."""
        logger.info(f"Attempting to create new case for customer: {case_data.customer_id}")
        
        # Check for existing active case (simple check for now)
        existing_case = self.db.scalar(
            select(EnhancedKYCCase)
            .where(EnhancedKYCCase.customer_id == case_data.customer_id)
            .where(EnhancedKYCCase.status.in_([CaseStatus.PENDING, CaseStatus.IN_REVIEW]))
        )
        
        if existing_case:
            raise CaseAlreadyExistsError(case_data.customer_id)

        db_case = EnhancedKYCCase(**case_data.model_dump())
        self.db.add(db_case)
        self.db.commit()
        self.db.refresh(db_case)
        logger.info(f"Successfully created case ID {db_case.id} for customer {db_case.customer_id}")
        return db_case

    def get_case(self, case_id: int) -> EnhancedKYCCase:
        """Retrieves a single Enhanced KYC Case by ID."""
        case = self.db.scalar(
            select(EnhancedKYCCase)
            .where(EnhancedKYCCase.id == case_id)
        )
        if not case:
            raise CaseNotFoundError(case_id)
        return case

    def get_cases(self, skip: int = 0, limit: int = 100, status_filter: Optional[CaseStatus] = None) -> List[EnhancedKYCCase]:
        """Retrieves a list of Enhanced KYC Cases."""
        stmt = select(EnhancedKYCCase).offset(skip).limit(limit).order_by(EnhancedKYCCase.created_at.desc())
        if status_filter:
            stmt = stmt.where(EnhancedKYCCase.status == status_filter)
            
        cases = self.db.scalars(stmt).all()
        return cases

    def get_case_count(self, status_filter: Optional[CaseStatus] = None) -> int:
        """Retrieves the total count of Enhanced KYC Cases."""
        stmt = select(func.count()).select_from(EnhancedKYCCase)
        if status_filter:
            stmt = stmt.where(EnhancedKYCCase.status == status_filter)
        return self.db.scalar(stmt)

    def update_case(self, case_id: int, case_data: EnhancedKYCCaseUpdate) -> EnhancedKYCCase:
        """Updates an existing Enhanced KYC Case."""
        db_case = self.get_case(case_id)
        
        update_data = case_data.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(db_case, key, value)
            
        self.db.add(db_case)
        self.db.commit()
        self.db.refresh(db_case)
        logger.info(f"Successfully updated case ID {case_id}")
        return db_case

    def delete_case(self, case_id: int) -> Dict[str, Any]:
        """Deletes an Enhanced KYC Case."""
        db_case = self.get_case(case_id)
        
        self.db.delete(db_case)
        self.db.commit()
        logger.warning(f"Successfully deleted case ID {case_id}")
        return {"message": f"Case {case_id} deleted successfully"}

    # --- EDDDetail Operations ---

    def create_edd_detail(self, case_id: int, detail_data: EDDDetailCreate) -> EDDDetail:
        """Creates EDD details for a given case."""
        db_case = self.get_case(case_id) # Ensures case exists
        
        if db_case.details:
            # If details already exist, we should update instead of create
            logger.warning(f"EDD Details already exist for case ID {case_id}. Performing update instead.")
            return self.update_edd_detail(case_id, EDDDetailUpdate(**detail_data.model_dump()))

        db_detail = EDDDetail(**detail_data.model_dump(), kyc_case_id=case_id)
        self.db.add(db_detail)
        self.db.commit()
        self.db.refresh(db_detail)
        logger.info(f"Successfully created EDD details for case ID {case_id}")
        return db_detail

    def get_edd_detail(self, case_id: int) -> EDDDetail:
        """Retrieves EDD details for a given case."""
        db_case = self.get_case(case_id) # Ensures case exists
        
        if not db_case.details:
            raise EDDDetailNotFoundError(case_id)
            
        return db_case.details

    def update_edd_detail(self, case_id: int, detail_data: EDDDetailUpdate) -> EDDDetail:
        """Updates EDD details for a given case."""
        db_detail = self.get_edd_detail(case_id) # Ensures case and details exist
        
        update_data = detail_data.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(db_detail, key, value)
            
        self.db.add(db_detail)
        self.db.commit()
        self.db.refresh(db_detail)
        logger.info(f"Successfully updated EDD details for case ID {case_id}")
        return db_detail

    def delete_edd_detail(self, case_id: int) -> Dict[str, Any]:
        """Deletes EDD details for a given case."""
        db_detail = self.get_edd_detail(case_id)
        
        self.db.delete(db_detail)
        self.db.commit()
        logger.warning(f"Successfully deleted EDD details for case ID {case_id}")
        return {"message": f"EDD Details for case {case_id} deleted successfully"}