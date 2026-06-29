import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

# Assuming models and config are in the same directory structure
from . import models
from . import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hybrid-engine",
    tags=["Hybrid Engine Results"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the database session
get_db = config.get_db

# --- CRUD Endpoints for HybridEngineResult ---

@router.post(
    "/results",
    response_model=models.HybridEngineResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Hybrid Engine Result",
    description="Records the outcome of a single transaction processed by the hybrid fraud detection engine."
)
def create_result(
    result: models.HybridEngineResultCreate, db: Session = Depends(get_db)
):
    """
    Creates a new HybridEngineResult entry in the database.

    The initial log entry (action='CREATED') is automatically generated.
    """
    try:
        # Check for existing transaction_id to enforce uniqueness
        existing_result = db.query(models.HybridEngineResult).filter(
            models.HybridEngineResult.transaction_id == result.transaction_id
        ).first()
        if existing_result:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Result for transaction_id '{result.transaction_id}' already exists."
            )

        db_result = models.HybridEngineResult(**result.model_dump())
        db.add(db_result)
        db.flush()  # Flush to get the ID for the log entry

        # Automatically create an initial log entry
        initial_log = models.HybridEngineLog(
            result_id=db_result.id,
            action="CREATED",
            details=f"Hybrid Engine Result created with decision: {db_result.decision}",
        )
        db.add(initial_log)
        db.commit()
        db.refresh(db_result)
        logger.info(f"Created new result for transaction: {db_result.transaction_id}")
        return db_result
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )


@router.get(
    "/results/{result_id}",
    response_model=models.HybridEngineResultResponse,
    summary="Get a Hybrid Engine Result by ID",
    description="Retrieves a specific hybrid engine result and its associated activity logs."
)
def read_result(result_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a HybridEngineResult by its primary key ID.
    """
    db_result = db.query(models.HybridEngineResult).filter(
        models.HybridEngineResult.id == result_id
    ).first()
    if db_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hybrid Engine Result not found"
        )
    return db_result


@router.get(
    "/results",
    response_model=List[models.HybridEngineResultResponse],
    summary="List Hybrid Engine Results",
    description="Retrieves a list of hybrid engine results with optional filtering and pagination."
)
def list_results(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return."),
    decision: Optional[str] = Query(None, description="Filter by final decision ('ALLOW', 'REVIEW', 'DENY')."),
    is_fraud: Optional[bool] = Query(None, description="Filter by final fraud determination."),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum overall score."),
):
    """
    Lists HybridEngineResult entries, supporting filtering by decision, fraud status, and minimum score.
    """
    query = db.query(models.HybridEngineResult)

    if decision:
        query = query.filter(models.HybridEngineResult.decision == decision.upper())
    if is_fraud is not None:
        query = query.filter(models.HybridEngineResult.is_fraud == is_fraud)
    if min_score is not None:
        query = query.filter(models.HybridEngineResult.overall_score >= min_score)

    results = query.offset(skip).limit(limit).all()
    return results


@router.patch(
    "/results/{result_id}",
    response_model=models.HybridEngineResultResponse,
    summary="Update a Hybrid Engine Result",
    description="Updates one or more fields of an existing hybrid engine result. Automatically logs the update."
)
def update_result(
    result_id: int,
    result_update: models.HybridEngineResultUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates a HybridEngineResult by ID.
    """
    db_result = db.query(models.HybridEngineResult).filter(
        models.HybridEngineResult.id == result_id
    ).first()
    if db_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hybrid Engine Result not found"
        )

    update_data = result_update.model_dump(exclude_unset=True)
    
    if not update_data:
        return db_result # Nothing to update

    for key, value in update_data.items():
        setattr(db_result, key, value)

    # Automatically create an update log entry
    update_log = models.HybridEngineLog(
        result_id=db_result.id,
        action="UPDATED",
        details=f"Fields updated: {', '.join(update_data.keys())}",
    )
    db.add(update_log)
    
    db.commit()
    db.refresh(db_result)
    logger.info(f"Updated result ID {result_id}. Fields: {', '.join(update_data.keys())}")
    return db_result


@router.delete(
    "/results/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Hybrid Engine Result",
    description="Deletes a specific hybrid engine result and all its associated activity logs."
)
def delete_result(result_id: int, db: Session = Depends(get_db)):
    """
    Deletes a HybridEngineResult by ID.
    """
    db_result = db.query(models.HybridEngineResult).filter(
        models.HybridEngineResult.id == result_id
    ).first()
    if db_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hybrid Engine Result not found"
        )

    db.delete(db_result)
    db.commit()
    logger.info(f"Deleted result ID {result_id} and associated logs.")
    return


# --- Business-Specific Endpoints ---

@router.post(
    "/results/{result_id}/logs",
    response_model=models.HybridEngineLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity log entry to a result",
    description="Adds a new log entry, typically for manual review actions or system re-evaluations."
)
def add_log_entry(
    result_id: int,
    log_entry: models.HybridEngineLogCreate,
    db: Session = Depends(get_db),
):
    """
    Adds a new log entry to an existing HybridEngineResult.
    """
    db_result = db.query(models.HybridEngineResult).filter(
        models.HybridEngineResult.id == result_id
    ).first()
    if db_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hybrid Engine Result not found"
        )

    db_log = models.HybridEngineLog(
        result_id=result_id,
        action=log_entry.action,
        details=log_entry.details,
    )
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Added log entry to result ID {result_id}. Action: {db_log.action}")
    return db_log
