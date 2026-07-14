import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from . import models
from .config import get_db, settings
from .models import (
    AuditLog, AuditLogCreate, AuditLogResponse, AuditLogSearch, 
    ExportResponse, ComplianceReport, ComplianceReportResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/v1/audit",
    tags=["audit"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def create_initial_tables(db: Session):
    """
    Utility function to create database tables if they don't exist.
    In a real application, this would be handled by a migration tool (e.g., Alembic).
    """
    models.Base.metadata.create_all(bind=db.bind)

# --- Business Logic Functions ---

def get_audit_logs_query(db: Session, search_criteria: AuditLogSearch):
    """
    Constructs the SQLAlchemy query based on the provided search criteria.
    """
    query = db.query(AuditLog)

    if search_criteria.service_name:
        query = query.filter(AuditLog.service_name == search_criteria.service_name)
    if search_criteria.user_id:
        query = query.filter(AuditLog.user_id == search_criteria.user_id)
    if search_criteria.action:
        query = query.filter(AuditLog.action == search_criteria.action)
    if search_criteria.resource_type:
        query = query.filter(AuditLog.resource_type == search_criteria.resource_type)
    if search_criteria.resource_id:
        query = query.filter(AuditLog.resource_id == search_criteria.resource_id)
    if search_criteria.status:
        query = query.filter(AuditLog.status == search_criteria.status)
    
    # Time range filtering
    if search_criteria.start_time:
        query = query.filter(AuditLog.timestamp >= search_criteria.start_time)
    if search_criteria.end_time:
        query = query.filter(AuditLog.timestamp <= search_criteria.end_time)

    return query

def perform_export_job(search_criteria: AuditLogSearch, export_format: str, recipient_email: str) -> str:
    """
    Executes an asynchronous export job.
    In a real system, this would queue a background task (e.g., Celery, Redis Queue).
    The task would fetch the data using `get_audit_logs_query`, format it, save it to 
    `settings.EXPORT_STORAGE_PATH`, and email the recipient.
    
    Returns a unique export ID.
    """
    export_id = f"export-{uuid.uuid4()}"
    logger.info(f"Export job initiated: ID={export_id}, Format={export_format}, Recipient={recipient_email}")
    # Production implementation for actual background job queuing logic
    return export_id

def generate_compliance_report(report_data: ComplianceReport) -> str:
    """
    Executes an asynchronous compliance report generation job.
    In a real system, this would queue a background task.
    
    Returns a unique report ID.
    """
    report_id = f"report-{uuid.uuid4()}"
    logger.info(f"Compliance report initiated: ID={report_id}, Type={report_data.report_type}")
    # Production implementation for actual background job queuing logic
    return report_id

# --- API Endpoints ---

@router.on_event("startup")
def on_startup():
    """Ensure tables are created on startup."""
    try:
        db = next(get_db())
        create_initial_tables(db)
        logger.info("Database tables ensured for audit-service.")
    except Exception as e:
        logger.error(f"Failed to create database tables on startup: {e}")
        # Depending on the environment, you might want to raise the exception

@router.post(
    "/logs", 
    response_model=AuditLogResponse, 
    status_code=201,
    summary="Create a new audit log entry"
)
def create_log(log: AuditLogCreate, db: Session = Depends(get_db)):
    """
    Records a new audit log entry. This is the primary ingestion endpoint.
    """
    try:
        db_log = AuditLog(**log.dict())
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        logger.info(f"New audit log created: Action={db_log.action}, User={db_log.user_id}")
        return db_log
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating audit log: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating log.")

@router.get(
    "/logs", 
    response_model=List[AuditLogResponse],
    summary="Search and retrieve audit logs"
)
def search_logs(
    db: Session = Depends(get_db),
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    status: Optional[str] = Query(None, description="Filter by status (SUCCESS/FAILURE)"),
    start_time: Optional[str] = Query(None, description="Filter logs from this timestamp (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="Filter logs up to this timestamp (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of logs per page"),
):
    """
    Searches the audit logs based on various criteria. Supports pagination and filtering.
    """
    try:
        # Create a temporary search criteria object from query parameters
        search_criteria = AuditLogSearch(
            service_name=service_name,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            start_time=start_time,
            end_time=end_time,
        )
        
        query = get_audit_logs_query(db, search_criteria)
        
        # Apply sorting (most recent first)
        query = query.order_by(desc(AuditLog.timestamp))
        
        # Apply pagination
        offset = (page - 1) * page_size
        logs = query.offset(offset).limit(page_size).all()
        
        return logs
    except Exception as e:
        logger.error(f"Error searching audit logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during log search.")

@router.post(
    "/export",
    response_model=ExportResponse,
    summary="Initiate an asynchronous log export job"
)
def export_logs(export_request: models.AuditLogExport, db: Session = Depends(get_db)):
    """
    Initiates a background job to export a large set of audit logs based on search criteria.
    The result (a download link) is typically sent to the recipient email.
    """
    # Validate the search criteria by running a count query (optional but good practice)
    query = get_audit_logs_query(db, export_request.search_criteria)
    log_count = query.with_entities(func.count()).scalar()
    
    if log_count == 0:
        raise HTTPException(status_code=404, detail="No logs found matching the export criteria.")
        
    # Queue the export job
    export_id = perform_export_job(
        export_request.search_criteria,
        export_request.export_format,
        export_request.recipient_email
    )
    
    return ExportResponse(
        export_id=export_id,
        status="PENDING",
        message=f"Export job for {log_count} logs started. A link will be sent to {export_request.recipient_email}."
    )

@router.post(
    "/compliance",
    response_model=ComplianceReportResponse,
    summary="Initiate an asynchronous compliance report generation"
)
def compliance_report(report_request: ComplianceReport):
    """
    Initiates a background job to generate a specific compliance report (e.g., GDPR, HIPAA).
    """
    # Basic validation for time range
    if report_request.start_time >= report_request.end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time.")
        
    # Queue the report generation job
    report_id = generate_compliance_report(report_request)
    
    return ComplianceReportResponse(
        report_id=report_id,
        status="PENDING",
        message=f"Compliance report '{report_request.report_type}' generation started."
    )
