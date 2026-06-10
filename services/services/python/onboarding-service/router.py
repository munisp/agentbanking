import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from . import models
from .config import get_db

# --- Configuration and Logging ---
router = APIRouter(
    prefix="/onboarding",
    tags=["Onboarding"],
    responses={404: {"description": "Not found"}},
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def create_activity_log(
    db: Session, 
    application_id: int, 
    activity_type: models.ActivityType, 
    description: str, 
    actor: str,
    old_status: Optional[models.OnboardingStatus] = None,
    new_status: Optional[models.OnboardingStatus] = None,
):
    """Creates a new entry in the onboarding activity log."""
    log_entry = models.OnboardingActivityLog(
        application_id=application_id,
        activity_type=activity_type,
        description=description,
        actor=actor,
        old_status=old_status,
        new_status=new_status,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# --- CRUD Endpoints for TenantOnboarding ---

@router.post(
    "/", 
    response_model=models.TenantOnboardingResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant onboarding application",
    description="Submits a new application for tenant onboarding. Initial status is PENDING_SUBMISSION."
)
def create_application(
    application: models.TenantOnboardingCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new TenantOnboarding record in the database.
    """
    # Check for existing application with the same email
    if db.query(models.TenantOnboarding).filter(models.TenantOnboarding.contact_email == application.contact_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An application with this contact email already exists."
        )

    db_application = models.TenantOnboarding(
        **application.model_dump(),
        status=models.OnboardingStatus.SUBMITTED, # Automatically move to SUBMITTED upon creation
        tenant_id=f"TEMP-{application.company_name.replace(' ', '-').upper()}-{int(models.datetime.now().timestamp())}" # Temporary ID
    )
    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    
    # Log the creation
    create_activity_log(
        db,
        db_application.id,
        models.ActivityType.STATUS_CHANGE,
        f"Application created and moved to {models.OnboardingStatus.SUBMITTED.value}",
        "user_submission",
        old_status=models.OnboardingStatus.PENDING_SUBMISSION,
        new_status=models.OnboardingStatus.SUBMITTED,
    )
    
    logger.info(f"Created new onboarding application ID: {db_application.id}")
    return db_application

@router.get(
    "/{application_id}", 
    response_model=models.TenantOnboardingResponse,
    summary="Retrieve a single onboarding application",
    description="Fetches the details of a specific tenant onboarding application by its ID."
)
def read_application(
    application_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single TenantOnboarding record by ID.
    """
    db_application = db.query(models.TenantOnboarding).filter(models.TenantOnboarding.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return db_application

@router.get(
    "/", 
    response_model=List[models.TenantOnboardingResponse],
    summary="List all onboarding applications",
    description="Retrieves a list of all tenant onboarding applications, with optional filtering and pagination."
)
def list_applications(
    status_filter: Optional[models.OnboardingStatus] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of TenantOnboarding records, optionally filtered by status.
    """
    query = db.query(models.TenantOnboarding)
    if status_filter:
        query = query.filter(models.TenantOnboarding.status == status_filter)
        
    applications = query.offset(skip).limit(limit).all()
    return applications

@router.put(
    "/{application_id}", 
    response_model=models.TenantOnboardingResponse,
    summary="Update an existing onboarding application",
    description="Updates the details of an existing tenant onboarding application."
)
def update_application(
    application_id: int, 
    application_update: models.TenantOnboardingUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing TenantOnboarding record by ID.
    """
    db_application = db.query(models.TenantOnboarding).filter(models.TenantOnboarding.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    update_data = application_update.model_dump(exclude_unset=True)
    
    # Prevent updating status via this endpoint
    if "status" in update_data:
        del update_data["status"]
        
    for key, value in update_data.items():
        setattr(db_application, key, value)

    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    
    # Log the update
    create_activity_log(
        db,
        db_application.id,
        models.ActivityType.DATA_UPDATE,
        f"Application data updated by user/system.",
        "system_update",
    )
    
    logger.info(f"Updated onboarding application ID: {db_application.id}")
    return db_application

@router.delete(
    "/{application_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an onboarding application",
    description="Deletes a tenant onboarding application and all associated activity logs."
)
def delete_application(
    application_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a TenantOnboarding record by ID.
    """
    db_application = db.query(models.TenantOnboarding).filter(models.TenantOnboarding.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    db.delete(db_application)
    db.commit()
    logger.warning(f"Deleted onboarding application ID: {application_id}")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{application_id}/status",
    response_model=models.TenantOnboardingResponse,
    summary="Update the status of an onboarding application",
    description="Moves the application to a new status and logs the change. This is the primary way to advance the onboarding workflow."
)
def update_application_status(
    application_id: int,
    status_update: models.StatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates the status of a TenantOnboarding record and creates an activity log entry.
    """
    db_application = db.query(models.TenantOnboarding).filter(models.TenantOnboarding.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    old_status = db_application.status
    new_status = status_update.new_status
    
    if old_status == new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application is already in status: {new_status.value}"
        )

    db_application.status = new_status
    db.add(db_application)
    db.commit()
    db.refresh(db_application)

    # Log the status change
    description = f"Status changed from {old_status.value} to {new_status.value}. Reason: {status_update.reason or 'N/A'}"
    create_activity_log(
        db,
        db_application.id,
        models.ActivityType.STATUS_CHANGE,
        description,
        status_update.actor,
        old_status=old_status,
        new_status=new_status,
    )
    
    logger.info(f"Application ID {application_id} status updated to {new_status.value}")
    return db_application

@router.post(
    "/{application_id}/assign-tenant-id",
    response_model=models.TenantOnboardingResponse,
    summary="Assign a final tenant ID to an approved application",
    description="Assigns the final, permanent tenant ID and moves the application to the ONBOARDED status. This action is irreversible."
)
def assign_final_tenant_id(
    application_id: int,
    tenant_id_assignment: models.TenantIdAssignment,
    db: Session = Depends(get_db)
):
    """
    Assigns the final tenant_id and sets the status to ONBOARDED.
    """
    db_application = db.query(models.TenantOnboarding).filter(models.TenantOnboarding.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if db_application.status != models.OnboardingStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign final tenant ID. Application status must be 'APPROVED', but is '{db_application.status.value}'."
        )
        
    # Check if the tenant_id is already in use
    if db.query(models.TenantOnboarding).filter(models.TenantOnboarding.tenant_id == tenant_id_assignment.tenant_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant ID '{tenant_id_assignment.tenant_id}' is already assigned to another application."
        )

    old_status = db_application.status
    db_application.tenant_id = tenant_id_assignment.tenant_id
    db_application.status = models.OnboardingStatus.ONBOARDED
    
    db.add(db_application)
    db.commit()
    db.refresh(db_application)

    # Log the finalization
    description = f"Final tenant ID '{tenant_id_assignment.tenant_id}' assigned. Status moved to {models.OnboardingStatus.ONBOARDED.value}."
    create_activity_log(
        db,
        db_application.id,
        models.ActivityType.SYSTEM_ACTION,
        description,
        tenant_id_assignment.actor,
        old_status=old_status,
        new_status=models.OnboardingStatus.ONBOARDED,
    )
    
    logger.info(f"Application ID {application_id} finalized with Tenant ID: {tenant_id_assignment.tenant_id}")
    return db_application

@router.get(
    "/{application_id}/activity-log",
    response_model=List[models.OnboardingActivityLogResponse],
    summary="Retrieve the activity log for an application",
    description="Fetches all activity log entries for a specific tenant onboarding application, ordered by timestamp."
)
def get_activity_log(
    application_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieves the activity log for a given application ID.
    """
    # Check if application exists
    if not db.query(models.TenantOnboarding).filter(models.TenantOnboarding.id == application_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    log_entries = db.query(models.OnboardingActivityLog).filter(
        models.OnboardingActivityLog.application_id == application_id
    ).order_by(desc(models.OnboardingActivityLog.timestamp)).all()
    
    return log_entries
