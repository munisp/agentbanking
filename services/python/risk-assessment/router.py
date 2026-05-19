import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/risk-assessments",
    tags=["risk-assessments"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def get_assessment_by_id(db: Session, assessment_id: uuid.UUID) -> models.RiskAssessment:
    """Helper function to fetch a risk assessment by ID or raise 404."""
    assessment = db.query(models.RiskAssessment).filter(models.RiskAssessment.id == assessment_id).first()
    if not assessment:
        logger.warning(f"Risk Assessment with ID {assessment_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk Assessment with ID {assessment_id} not found."
        )
    return assessment

def create_log_entry(db: Session, assessment_id: uuid.UUID, action: str, details: str = None):
    """Helper function to create a log entry for an assessment."""
    log_entry = models.RiskAssessmentLog(
        assessment_id=assessment_id,
        action=action,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.RiskAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Risk Assessment",
    description="Creates a new risk assessment record for a given entity."
)
def create_risk_assessment(
    assessment: models.RiskAssessmentCreate, db: Session = Depends(get_db)
):
    """
    Creates a new Risk Assessment in the database.
    
    Raises:
        HTTPException 409: If an assessment for the entity_id and entity_type already exists.
    """
    # Check for existing assessment for the same entity
    existing_assessment = db.query(models.RiskAssessment).filter(
        models.RiskAssessment.entity_id == assessment.entity_id,
        models.RiskAssessment.entity_type == assessment.entity_type
    ).first()
    
    if existing_assessment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Risk Assessment already exists for entity_id: {assessment.entity_id} and entity_type: {assessment.entity_type}. Use PUT to update."
        )

    db_assessment = models.RiskAssessment(**assessment.model_dump())
    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)
    
    create_log_entry(db, db_assessment.id, "ASSESSMENT_CREATED", f"Initial score: {assessment.score}, status: {assessment.status}")
    
    logger.info(f"Created new Risk Assessment with ID: {db_assessment.id}")
    return db_assessment

@router.get(
    "/{assessment_id}",
    response_model=models.RiskAssessmentResponse,
    summary="Get a Risk Assessment by ID",
    description="Retrieves a specific risk assessment record, including its logs."
)
def read_risk_assessment(assessment_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a Risk Assessment by its unique ID.
    
    Raises:
        HTTPException 404: If the assessment is not found.
    """
    return get_assessment_by_id(db, assessment_id)

@router.get(
    "/",
    response_model=List[models.RiskAssessmentResponse],
    summary="List all Risk Assessments",
    description="Retrieves a list of all risk assessment records with optional pagination."
)
def list_risk_assessments(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of Risk Assessments.
    """
    assessments = db.query(models.RiskAssessment).offset(skip).limit(limit).all()
    return assessments

@router.put(
    "/{assessment_id}",
    response_model=models.RiskAssessmentResponse,
    summary="Update an existing Risk Assessment",
    description="Updates the score, status, or reason of an existing risk assessment."
)
def update_risk_assessment(
    assessment_id: uuid.UUID,
    assessment_update: models.RiskAssessmentUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates an existing Risk Assessment by its unique ID.
    
    Raises:
        HTTPException 404: If the assessment is not found.
    """
    db_assessment = get_assessment_by_id(db, assessment_id)
    
    update_data = assessment_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update."
        )

    log_details = []
    for key, value in update_data.items():
        setattr(db_assessment, key, value)
        log_details.append(f"Updated {key} to {value}")

    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)
    
    create_log_entry(db, db_assessment.id, "ASSESSMENT_UPDATED", ", ".join(log_details))
    
    logger.info(f"Updated Risk Assessment with ID: {db_assessment.id}")
    return db_assessment

@router.delete(
    "/{assessment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Risk Assessment",
    description="Deletes a specific risk assessment record and all associated logs."
)
def delete_risk_assessment(assessment_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes a Risk Assessment by its unique ID.
    
    Raises:
        HTTPException 404: If the assessment is not found.
    """
    db_assessment = get_assessment_by_id(db, assessment_id)
    
    db.delete(db_assessment)
    db.commit()
    
    logger.info(f"Deleted Risk Assessment with ID: {assessment_id}")
    return

# --- Business-Specific Endpoint ---

@router.post(
    "/{assessment_id}/log",
    response_model=models.RiskAssessmentLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity log to a Risk Assessment",
    description="Adds a new activity log entry to an existing risk assessment, useful for tracking manual reviews or system actions."
)
def add_assessment_log(
    assessment_id: uuid.UUID,
    action: str,
    details: str = None,
    db: Session = Depends(get_db)
):
    """
    Adds a new log entry to a Risk Assessment.
    
    Args:
        assessment_id: The ID of the risk assessment.
        action: The action performed (e.g., 'MANUAL_REVIEW', 'SCORE_OVERRIDE').
        details: Optional details about the action.
        db: The database session.
        
    Raises:
        HTTPException 404: If the assessment is not found.
    """
    # Ensure the assessment exists
    get_assessment_by_id(db, assessment_id)
    
    log_entry = create_log_entry(db, assessment_id, action, details)
    
    logger.info(f"Added log entry for Assessment ID: {assessment_id}, Action: {action}")
    return log_entry
