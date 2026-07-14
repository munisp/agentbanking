"""
FastAPI router for the customer-analytics service, providing CRUD and business logic endpoints.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func
from pydantic import conint

from . import models
from .config import get_db
from .models import (
    CustomerAnalytic, 
    AnalyticActivityLog, 
    CustomerAnalyticCreate, 
    CustomerAnalyticUpdate, 
    CustomerAnalyticResponse,
    AnalyticActivityLogCreate,
    AnalyticActivityLogResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["customer-analytics"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (Database Operations) ---

def get_analytic_by_id(db: Session, analytic_id: int) -> Optional[CustomerAnalytic]:
    """Retrieve a CustomerAnalytic record by its ID."""
    return db.get(CustomerAnalytic, analytic_id)

def get_analytic_by_customer_and_type(db: Session, customer_id: int, analytic_type: str) -> Optional[CustomerAnalytic]:
    """Retrieve a CustomerAnalytic record by customer ID and analytic type."""
    stmt = select(CustomerAnalytic).where(
        CustomerAnalytic.customer_id == customer_id,
        CustomerAnalytic.analytic_type == analytic_type
    )
    return db.execute(stmt).scalar_one_or_none()

# --- CRUD Endpoints for CustomerAnalytic ---

@router.post(
    "/", 
    response_model=CustomerAnalyticResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer analytic record"
)
def create_analytic(
    analytic_in: CustomerAnalyticCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new customer analytic record.
    
    Raises:
        HTTPException 409: If an analytic for the given customer_id and analytic_type already exists.
    """
    # Check for existing record to enforce unique constraint
    existing_analytic = get_analytic_by_customer_and_type(
        db, 
        analytic_in.customer_id, 
        analytic_in.analytic_type
    )
    if existing_analytic:
        logger.warning(f"Attempted to create duplicate analytic: customer_id={analytic_in.customer_id}, type={analytic_in.analytic_type}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analytic record for this customer and type already exists."
        )

    db_analytic = CustomerAnalytic(**analytic_in.model_dump())
    db.add(db_analytic)
    db.commit()
    db.refresh(db_analytic)
    logger.info(f"Created new analytic record with ID: {db_analytic.id}")
    return db_analytic

@router.get(
    "/{analytic_id}", 
    response_model=CustomerAnalyticResponse,
    summary="Retrieve a customer analytic record by ID"
)
def read_analytic(
    analytic_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single customer analytic record by its unique ID.
    
    Raises:
        HTTPException 404: If the analytic record is not found.
    """
    db_analytic = get_analytic_by_id(db, analytic_id)
    if db_analytic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Customer analytic record not found"
        )
    return db_analytic

@router.get(
    "/", 
    response_model=List[CustomerAnalyticResponse],
    summary="List all customer analytic records"
)
def list_analytics(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of customer analytic records with pagination.
    """
    stmt = select(CustomerAnalytic).offset(skip).limit(limit)
    analytics = db.execute(stmt).scalars().all()
    return analytics

@router.put(
    "/{analytic_id}", 
    response_model=CustomerAnalyticResponse,
    summary="Update an existing customer analytic record"
)
def update_analytic(
    analytic_id: int, 
    analytic_in: CustomerAnalyticUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing customer analytic record by ID.
    
    Raises:
        HTTPException 404: If the analytic record is not found.
    """
    db_analytic = get_analytic_by_id(db, analytic_id)
    if db_analytic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Customer analytic record not found"
        )

    update_data = analytic_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_analytic, key, value)

    db.add(db_analytic)
    db.commit()
    db.refresh(db_analytic)
    logger.info(f"Updated analytic record with ID: {analytic_id}")
    return db_analytic

@router.delete(
    "/{analytic_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer analytic record"
)
def delete_analytic(
    analytic_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a customer analytic record by ID. Related activity logs are also deleted (cascade).
    
    Raises:
        HTTPException 404: If the analytic record is not found.
    """
    db_analytic = get_analytic_by_id(db, analytic_id)
    if db_analytic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Customer analytic record not found"
        )

    db.delete(db_analytic)
    db.commit()
    logger.info(f"Deleted analytic record with ID: {analytic_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.get(
    "/customer/{customer_id}",
    response_model=List[CustomerAnalyticResponse],
    summary="Get all analytic records for a specific customer"
)
def get_analytics_by_customer_id(
    customer_id: conint(ge=1),
    db: Session = Depends(get_db)
):
    """
    Retrieves all customer analytic records associated with a given customer ID.
    """
    stmt = select(CustomerAnalytic).where(CustomerAnalytic.customer_id == customer_id)
    analytics = db.execute(stmt).scalars().all()
    if not analytics:
        logger.info(f"No analytic records found for customer_id: {customer_id}")
        # Return an empty list instead of 404, as a customer may simply have no analytics yet
        return [] 
    return analytics

# --- Activity Log Endpoints ---

@router.post(
    "/{analytic_id}/logs",
    response_model=AnalyticActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity log entry to a customer analytic record"
)
def create_activity_log(
    analytic_id: int,
    log_in: AnalyticActivityLogBase,
    db: Session = Depends(get_db)
):
    """
    Adds a new activity log entry to the specified customer analytic record.
    
    Raises:
        HTTPException 404: If the parent analytic record is not found.
    """
    db_analytic = get_analytic_by_id(db, analytic_id)
    if db_analytic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Parent customer analytic record not found"
        )

    log_data = log_in.model_dump()
    db_log = AnalyticActivityLog(analytic_id=analytic_id, **log_data)
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Added activity log to analytic ID: {analytic_id}")
    return db_log

@router.get(
    "/{analytic_id}/logs",
    response_model=List[AnalyticActivityLogResponse],
    summary="List activity log entries for a customer analytic record"
)
def list_activity_logs(
    analytic_id: int,
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of activity log entries for a specific customer analytic record.
    
    Raises:
        HTTPException 404: If the parent analytic record is not found.
    """
    db_analytic = get_analytic_by_id(db, analytic_id)
    if db_analytic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Parent customer analytic record not found"
        )
        
    stmt = (
        select(AnalyticActivityLog)
        .where(AnalyticActivityLog.analytic_id == analytic_id)
        .order_by(AnalyticActivityLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    logs = db.execute(stmt).scalars().all()
    return logs

