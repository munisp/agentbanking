import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db
from .models import CreditScore, CreditScoreActivityLog, CreditScoreResponse, CreditScoreCreate, CreditScoreUpdate, ScoreStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/credit-scoring",
    tags=["credit-scoring"],
    responses={404: {"description": "Not found"}},
)

def create_activity_log(db: Session, credit_score_id: int, activity_type: str, details: Optional[str] = None, performed_by: Optional[str] = "system"):
    """
    Helper function to create and commit an activity log entry.
    """
    log_entry = CreditScoreActivityLog(
        credit_score_id=credit_score_id,
        activity_type=activity_type,
        details=details,
        performed_by=performed_by
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# --- CRUD Endpoints ---

@router.post(
    "/scores", 
    response_model=CreditScoreResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new credit score record",
    description="Creates a new credit score record for a given entity. This is typically used after a score calculation is complete."
)
def create_score(score: CreditScoreCreate, db: Session = Depends(get_db)):
    """
    Creates a new credit score record in the database.
    """
    logger.info(f"Attempting to create score for entity_id: {score.entity_id}")
    
    db_score = CreditScore(**score.model_dump())
    
    try:
        db.add(db_score)
        db.commit()
        db.refresh(db_score)
        
        # Log the creation activity
        create_activity_log(db, db_score.id, "SCORE_CREATED", f"Initial score {db_score.score_value} created.")
        
        logger.info(f"Successfully created score with ID: {db_score.id}")
        return db_score
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error: Score already exists for entity_id: {score.entity_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A credit score already exists for entity_id: {score.entity_id}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating score: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during score creation."
        )

@router.get(
    "/scores/{score_id}", 
    response_model=CreditScoreResponse,
    summary="Retrieve a credit score by ID",
    description="Fetches a single credit score record and its activity logs by its primary key ID."
)
def read_score(score_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a credit score by its ID.
    """
    logger.info(f"Attempting to read score with ID: {score_id}")
    db_score = db.query(CreditScore).filter(CreditScore.id == score_id).first()
    if db_score is None:
        logger.warning(f"Score with ID {score_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit Score not found")
    return db_score

@router.get(
    "/scores", 
    response_model=List[CreditScoreResponse],
    summary="List all credit scores",
    description="Retrieves a list of all credit scores with optional pagination."
)
def list_scores(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a list of credit scores with pagination.
    """
    logger.info(f"Listing scores with skip={skip}, limit={limit}")
    scores = db.query(CreditScore).offset(skip).limit(limit).all()
    return scores

@router.put(
    "/scores/{score_id}", 
    response_model=CreditScoreResponse,
    summary="Update an existing credit score",
    description="Updates the details of an existing credit score record by its ID."
)
def update_score(score_id: int, score: CreditScoreUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing credit score record.
    """
    logger.info(f"Attempting to update score with ID: {score_id}")
    db_score = db.query(CreditScore).filter(CreditScore.id == score_id).first()
    if db_score is None:
        logger.warning(f"Update failed: Score with ID {score_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit Score not found")

    update_data = score.model_dump(exclude_unset=True)
    
    # Check if any fields are actually being updated
    if not update_data:
        return db_score # No change, return current object

    for key, value in update_data.items():
        setattr(db_score, key, value)

    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    
    # Log the update activity
    create_activity_log(db, db_score.id, "SCORE_UPDATED", f"Score updated with data: {update_data}")
    
    logger.info(f"Successfully updated score with ID: {score_id}")
    return db_score

@router.delete(
    "/scores/{score_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a credit score",
    description="Deletes a credit score record by its ID."
)
def delete_score(score_id: int, db: Session = Depends(get_db)):
    """
    Deletes a credit score record.
    """
    logger.info(f"Attempting to delete score with ID: {score_id}")
    db_score = db.query(CreditScore).filter(CreditScore.id == score_id).first()
    if db_score is None:
        logger.warning(f"Delete failed: Score with ID {score_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit Score not found")

    db.delete(db_score)
    db.commit()
    
    logger.info(f"Successfully deleted score with ID: {score_id}")
    return {"ok": True}

# --- Business-Specific Endpoint ---

class ScoreCalculationRequest(models.BaseModel):
    """Pydantic schema for requesting a new score calculation."""
    entity_id: UUID = models.Field(..., description="Unique identifier for the entity to be scored.")
    data_source_id: str = models.Field(..., description="Identifier for the data source to use for calculation.")
    force_recalculation: bool = models.Field(False, description="If true, forces a recalculation even if a recent score exists.")

@router.post(
    "/calculate",
    response_model=CreditScoreResponse,
    summary="Trigger a new credit score calculation",
    description="Triggers the asynchronous calculation of a new credit score for a given entity. Returns the current or newly calculated score."
)
def calculate_score(request: ScoreCalculationRequest, db: Session = Depends(get_db)):
    """
    Triggers the credit score calculation process.
    For production, this would typically involve a background task queue (e.g., Celery).
    """
    logger.info(f"Received calculation request for entity_id: {request.entity_id}")
    
    # 1. Check for existing score
    db_score = db.query(CreditScore).filter(CreditScore.entity_id == request.entity_id).first()

    if db_score and not request.force_recalculation:
        logger.info(f"Existing score found for entity {request.entity_id}. Returning current score.")
        return db_score

    # 2. Execute credit scoring model
    # In a real system, this would be an async call to a scoring engine.
    
    # Execute scoring calculation
    import random
    payment_history = score_data.get("payment_history_score", 0.35)
    credit_utilization = score_data.get("credit_utilization", 0.30)
    credit_age = score_data.get("credit_age_score", 0.15)
    credit_mix = score_data.get("credit_mix_score", 0.10)
    new_inquiries = score_data.get("new_inquiries_score", 0.10)
    weighted = (payment_history * 0.35 + (1.0 - credit_utilization) * 0.30 +
                credit_age * 0.15 + credit_mix * 0.10 + (1.0 - new_inquiries) * 0.10)
    new_score_value = int(300 + weighted * 550)
    new_risk_level = "High" if new_score_value < 580 else ("Medium" if new_score_value < 670 else "Low")
    new_model_version = "v1.2.3-hybrid-ml"
    new_score_factors = f'{{"debt_to_income": 0.4, "payment_history": "good", "inquiries": 2}}'
    
    if db_score:
        # Update existing score
        db_score.score_value = new_score_value
        db_score.risk_level = new_risk_level
        db_score.score_model_version = new_model_version
        db_score.score_factors = new_score_factors
        db_score.status = ScoreStatus.RECALCULATED
        
        db.add(db_score)
        db.commit()
        db.refresh(db_score)
        
        create_activity_log(db, db_score.id, "SCORE_RECALCULATED", f"Recalculated score to {new_score_value} using {new_model_version}.")
        logger.info(f"Recalculated score for entity {request.entity_id} to {new_score_value}.")
        return db_score
    else:
        # Create new score
        new_score = CreditScore(
            entity_id=request.entity_id,
            score_value=new_score_value,
            score_model_version=new_model_version,
            risk_level=new_risk_level,
            score_factors=new_score_factors,
            status=ScoreStatus.COMPLETED
        )
        
        try:
            db.add(new_score)
            db.commit()
            db.refresh(new_score)
            
            create_activity_log(db, new_score.id, "SCORE_CALCULATED", f"New score {new_score_value} calculated using {new_model_version}.")
            logger.info(f"New score calculated and created for entity {request.entity_id} with score {new_score_value}.")
            return new_score
        except IntegrityError:
            db.rollback()
            logger.error(f"Integrity error during new score creation for entity_id: {request.entity_id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A credit score already exists for entity_id: {request.entity_id}"
            )
