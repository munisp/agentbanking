import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from config import get_db, get_settings
from models import (
    AlertStatus,
    SecurityActivityLog,
    SecurityActivityLogCreate,
    SecurityActivityLogResponse,
    SecurityAlert,
    SecurityAlertCreate,
    SecurityAlertResponse,
    SecurityAlertUpdate,
)

# --- Configuration and Logging ---
settings = get_settings()
router = APIRouter(prefix="/alerts", tags=["security-monitoring"])

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_alert_by_id(db: Session, alert_id: uuid.UUID) -> SecurityAlert:
    """
    Helper function to fetch a SecurityAlert by its UUID, raising 404 if not found.
    """
    alert = (
        db.query(SecurityAlert)
        .options(joinedload(SecurityAlert.activity_logs))
        .filter(SecurityAlert.id == alert_id)
        .first()
    )
    if not alert:
        logger.warning(f"Alert not found: {alert_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security Alert with ID {alert_id} not found",
        )
    return alert

# --- SecurityAlert Endpoints (CRUD) ---

@router.post(
    "/",
    response_model=SecurityAlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Security Alert",
    description="Registers a new security alert from a monitoring source (e.g., Wazuh, Openappsec).",
)
def create_alert(alert_in: SecurityAlertCreate, db: Session = Depends(get_db)):
    """
    Creates a new security alert in the database.
    """
    logger.info(f"Attempting to create new alert: {alert_in.alert_id}")
    
    # Check for existing alert with the same source alert_id to prevent duplicates
    existing_alert = db.query(SecurityAlert).filter(SecurityAlert.alert_id == alert_in.alert_id).first()
    if existing_alert:
        logger.warning(f"Alert already exists: {alert_in.alert_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alert with source ID {alert_in.alert_id} already exists.",
        )

    try:
        db_alert = SecurityAlert(**alert_in.model_dump())
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        logger.info(f"Successfully created alert with ID: {db_alert.id}")
        return db_alert
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while creating the alert: {e}",
        )


@router.get(
    "/",
    response_model=List[SecurityAlertResponse],
    summary="List all Security Alerts",
    description="Retrieves a list of security alerts with optional filtering and pagination.",
)
def list_alerts(
    status_filter: Optional[AlertStatus] = Query(None, description="Filter by alert status."),
    severity_filter: Optional[str] = Query(None, description="Filter by alert severity (e.g., CRITICAL, HIGH)."),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)."),
    limit: int = Query(100, le=1000, description="Maximum number of records to return."),
    db: Session = Depends(get_db),
):
    """
    Fetches a list of security alerts based on provided filters and pagination parameters.
    """
    logger.debug(f"Listing alerts with status={status_filter}, severity={severity_filter}, skip={skip}, limit={limit}")
    
    query = db.query(SecurityAlert).options(joinedload(SecurityAlert.activity_logs))
    
    if status_filter:
        query = query.filter(SecurityAlert.status == status_filter)
    if severity_filter:
        # Case-insensitive search for severity
        query = query.filter(SecurityAlert.severity.ilike(severity_filter))

    alerts = query.offset(skip).limit(limit).all()
    return alerts


@router.get(
    "/{alert_id}",
    response_model=SecurityAlertResponse,
    summary="Get a Security Alert by ID",
    description="Retrieves a single security alert and its associated activity logs by its UUID.",
)
def read_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a specific security alert.
    """
    return get_alert_by_id(db, alert_id)


@router.patch(
    "/{alert_id}",
    response_model=SecurityAlertResponse,
    summary="Update Security Alert Status or Details",
    description="Updates the status, severity, or other details of an existing security alert.",
)
def update_alert(
    alert_id: uuid.UUID, alert_in: SecurityAlertUpdate, db: Session = Depends(get_db)
):
    """
    Updates an existing security alert with new data.
    """
    db_alert = get_alert_by_id(db, alert_id)
    update_data = alert_in.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    for key, value in update_data.items():
        setattr(db_alert, key, value)

    try:
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        logger.info(f"Successfully updated alert with ID: {alert_id}")
        return db_alert
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while updating the alert: {e}",
        )


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Security Alert",
    description="Deletes a security alert and all its associated activity logs.",
)
def delete_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes a security alert and cascades the deletion to its activity logs.
    """
    db_alert = get_alert_by_id(db, alert_id)
    
    try:
        db.delete(db_alert)
        db.commit()
        logger.info(f"Successfully deleted alert with ID: {alert_id}")
        return
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while deleting the alert: {e}",
        )

# --- SecurityActivityLog Endpoints (Business-Specific) ---

@router.post(
    "/{alert_id}/logs",
    response_model=SecurityActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an Activity Log to an Alert",
    description="Adds a new activity log entry (e.g., comment, status change) to a specific security alert.",
)
def add_activity_log(
    alert_id: uuid.UUID, log_in: SecurityActivityLogCreate, db: Session = Depends(get_db)
):
    """
    Creates a new activity log entry associated with a specific alert.
    """
    # Ensure the alert exists
    db_alert = get_alert_by_id(db, alert_id)
    
    logger.info(f"Adding log to alert {alert_id} by user {log_in.user_id}")

    try:
        # Create the log entry, ensuring the alert_id from the path is used
        log_data = log_in.model_dump(exclude={"alert_id"})
        db_log = SecurityActivityLog(alert_id=alert_id, **log_data)
        
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        
        # Optionally, update the alert's updated_at timestamp
        db_alert.updated_at = db_log.timestamp
        db.add(db_alert)
        db.commit()
        
        logger.info(f"Successfully added log with ID: {db_log.id} to alert {alert_id}")
        return db_log
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding activity log to alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while adding the activity log: {e}",
        )


@router.get(
    "/{alert_id}/logs",
    response_model=List[SecurityActivityLogResponse],
    summary="List Activity Logs for an Alert",
    description="Retrieves all activity logs for a specific security alert, ordered by timestamp.",
)
def list_activity_logs(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves all activity logs for a given alert ID.
    """
    # Ensure the alert exists
    get_alert_by_id(db, alert_id)
    
    logs = (
        db.query(SecurityActivityLog)
        .filter(SecurityActivityLog.alert_id == alert_id)
        .order_by(SecurityActivityLog.timestamp.asc())
        .all()
    )
    return logs
