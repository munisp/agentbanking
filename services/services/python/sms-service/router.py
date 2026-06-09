import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Assuming models and config are in the same directory for this task
# In a real project, these would be imported from a package structure (e.g., from . import models, config)
import models
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sms",
    tags=["SMS Service"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (Service Layer Simulation) ---

def create_sms_message(db: Session, sms_in: models.SMSMessageCreate) -> models.SMSMessage:
    """
    Creates a new SMS message record in the database.
    """
    db_sms = models.SMSMessage(
        recipient_number=sms_in.recipient_number,
        sender_id=sms_in.sender_id,
        message_body=sms_in.message_body,
        scheduled_time=sms_in.scheduled_time,
        status=models.SMSStatus.PENDING.value
    )
    db.add(db_sms)
    
    # Add creation log
    log = models.SMSActivityLog(
        sms_message=db_sms,
        activity_type="CREATION",
        details=f"SMS message created with initial status: {models.SMSStatus.PENDING.value}"
    )
    db.add(log)
    
    db.commit()
    db.refresh(db_sms)
    logger.info(f"Created SMS message ID: {db_sms.id} for {db_sms.recipient_number}")
    return db_sms

def get_sms_message(db: Session, sms_id: int) -> Optional[models.SMSMessage]:
    """
    Retrieves a single SMS message by ID.
    """
    return db.query(models.SMSMessage).filter(models.SMSMessage.id == sms_id).first()

def get_sms_messages(db: Session, skip: int = 0, limit: int = 100) -> List[models.SMSMessage]:
    """
    Retrieves a list of SMS messages with pagination.
    """
    return db.query(models.SMSMessage).offset(skip).limit(limit).all()

def update_sms_message(db: Session, sms_id: int, sms_update: models.SMSMessageUpdate) -> models.SMSMessage:
    """
    Updates an existing SMS message record.
    """
    db_sms = get_sms_message(db, sms_id)
    if not db_sms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found")

    update_data = sms_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        if key == "status":
            old_status = db_sms.status
            setattr(db_sms, key, value.value) # Use .value for Enum
            
            # Add status update log
            log = models.SMSActivityLog(
                sms_message=db_sms,
                activity_type="STATUS_UPDATE",
                details=f"Status changed from {old_status} to {value.value}"
            )
            db.add(log)
            logger.info(f"SMS message ID: {sms_id} status updated to {value.value}")
        else:
            setattr(db_sms, key, value)

    db.commit()
    db.refresh(db_sms)
    return db_sms

def delete_sms_message(db: Session, sms_id: int):
    """
    Deletes an SMS message record.
    """
    db_sms = get_sms_message(db, sms_id)
    if not db_sms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found")
    
    db.delete(db_sms)
    db.commit()
    logger.info(f"Deleted SMS message ID: {sms_id}")

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.SMSMessageResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a new SMS message"
)
def create_message(
    sms_in: models.SMSMessageCreate, 
    db: Session = Depends(config.get_db)
):
    """
    Schedules a new SMS message to be sent. The initial status will be PENDING.
    """
    return create_sms_message(db, sms_in)

@router.get(
    "/{sms_id}", 
    response_model=models.SMSMessageResponse,
    summary="Get a single SMS message by ID"
)
def read_message(
    sms_id: int, 
    db: Session = Depends(config.get_db)
):
    """
    Retrieve details of a specific SMS message, including its activity log.
    """
    db_sms = get_sms_message(db, sms_id)
    if db_sms is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found")
    return db_sms

@router.get(
    "/", 
    response_model=List[models.SMSMessageResponse],
    summary="List all SMS messages"
)
def list_messages(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(config.get_db)
):
    """
    Retrieve a list of all SMS messages with optional pagination.
    """
    return get_sms_messages(db, skip=skip, limit=limit)

@router.patch(
    "/{sms_id}", 
    response_model=models.SMSMessageResponse,
    summary="Update SMS message details (e.g., status or scheduled time)"
)
def update_message(
    sms_id: int, 
    sms_update: models.SMSMessageUpdate, 
    db: Session = Depends(config.get_db)
):
    """
    Update the status or scheduled time of an existing SMS message.
    """
    return update_sms_message(db, sms_id, sms_update)

@router.delete(
    "/{sms_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an SMS message"
)
def delete_message(
    sms_id: int, 
    db: Session = Depends(config.get_db)
):
    """
    Permanently delete an SMS message record.
    """
    delete_sms_message(db, sms_id)
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{sms_id}/send",
    response_model=models.SMSMessageResponse,
    summary="Send an SMS message"
)
def send_sms_message(
    sms_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Sends the process of sending an SMS message. 
    It updates the status to SENT and records the sent time.
    """
    db_sms = get_sms_message(db, sms_id)
    if not db_sms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found")

    if db_sms.status in [models.SMSStatus.SENT.value, models.SMSStatus.DELIVERED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"SMS message ID {sms_id} is already {db_sms.status}"
        )

    # Send via provider
    db_sms.status = models.SMSStatus.SENT.value
    db_sms.sent_at = datetime.utcnow()
    
    # Add log
    log = models.SMSActivityLog(
        sms_message=db_sms,
        activity_type="SEND_ATTEMPT",
        details="SMS sending sent and status updated to SENT."
    )
    db.add(log)
    
    db.commit()
    db.refresh(db_sms)
    logger.info(f"SMS message sent, ID: {sms_id}")
    return db_sms

@router.get(
    "/{sms_id}/status",
    response_model=models.SMSStatus,
    summary="Get the current status of an SMS message"
)
def get_message_status(
    sms_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Retrieves only the current status of a specific SMS message.
    """
    db_sms = get_sms_message(db, sms_id)
    if not db_sms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found")
    
    return models.SMSStatus(db_sms.status)
