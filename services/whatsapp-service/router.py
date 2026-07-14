import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Body, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .config import get_db, settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{settings.API_V1_STR}/whatsapp",
    tags=["whatsapp"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions (External API Interaction) ---

def send_send_message(message_id: UUID, content: str, recipient: str):
    """
    Sends the asynchronous process of sending a message via an external WhatsApp API.
    In a real application, this would involve an HTTP request to the WhatsApp API.
    """
    logger.info(f"Simulating external API call to send message {message_id} to {recipient}")
    # Call WhatsApp Business API
    import time

    
    # In a real scenario, the API would return an external_message_id and a status
    external_id = f"ext-{message_id}"
    
    # Process response
    logger.info(f"Message {message_id} successfully sent to external API. External ID: {external_id}")
    return external_id

def update_message_status_in_db(db: Session, message_id: UUID, new_status: schemas.MessageStatus, external_id: Optional[str] = None):
    """
    Updates the message status and logs the activity.
    """
    db_message = db.query(models.WhatsAppMessage).filter(models.WhatsAppMessage.id == message_id).first()
    if not db_message:
        logger.error(f"Message with ID {message_id} not found for status update.")
        return

    old_status = db_message.status
    db_message.status = new_status
    if external_id:
        db_message.external_message_id = external_id
    
    # Log the status update
    log_entry = models.WhatsAppActivityLog(
        message_id=message_id,
        activity_type=schemas.ActivityType.STATUS_UPDATE,
        details=f"Status changed from {old_status.value} to {new_status.value}. External ID: {external_id or 'N/A'}"
    )
    db.add(log_entry)
    db.commit()
    db.refresh(db_message)
    logger.info(f"Message {message_id} status updated to {new_status.value}.")


# --- Business Logic Functions ---

def process_message_send(db: Session, message_id: UUID, content: str, recipient: str):
    """
    Handles the full lifecycle of sending a message after it's created in the DB.
    This function runs in the background.
    """
    try:
        # 1. Send the message via WhatsApp Business API
        external_id = send_send_message(message_id, content, recipient)
        
        # 2. Update status to SENT (or DELIVERED/FAILED based on real API response)
        # For this simulation, we'll assume it's immediately SENT to the API
        update_message_status_in_db(db, message_id, schemas.MessageStatus.SENT, external_id)
        
        # 3. Process delivery receipt
        # In a real system, this would be a webhook call from the WhatsApp API
        import time
        time.sleep(0.5)
        update_message_status_in_db(db, message_id, schemas.MessageStatus.DELIVERED)

    except Exception as e:
        logger.error(f"Error processing message send for {message_id}: {e}")
        # Log the error and update status to FAILED
        update_message_status_in_db(db, message_id, schemas.MessageStatus.FAILED)
        db_message = db.query(models.WhatsAppMessage).filter(models.WhatsAppMessage.id == message_id).first()
        if db_message:
            log_entry = models.WhatsAppActivityLog(
                message_id=message_id,
                activity_type=schemas.ActivityType.ERROR,
                details=f"Failed to send message: {str(e)}"
            )
            db.add(log_entry)
            db.commit()


# --- CRUD Endpoints for WhatsAppMessage ---

@router.post(
    "/messages", 
    response_model=schemas.WhatsAppMessageResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create and queue a new WhatsApp message for sending"
)
def create_whatsapp_message(
    message: schemas.WhatsAppMessageCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Creates a new WhatsApp message record in the database and queues it for sending.
    
    - **sender_phone_number**: The service's phone number.
    - **recipient_phone_number**: The target phone number.
    - **content**: The message content.
    - **status**: Defaults to 'queued'.
    """
    if message.is_incoming:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create an incoming message via this endpoint."
        )

    db_message = models.WhatsAppMessage(**message.model_dump(exclude_unset=True))
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # Log the creation
    log_entry = models.WhatsAppActivityLog(
        message_id=db_message.id,
        activity_type=schemas.ActivityType.MESSAGE_SENT,
        details=f"Message created and queued for recipient: {message.recipient_phone_number}"
    )
    db.add(log_entry)
    db.commit()
    
    # Start the background task to process the message send
    background_tasks.add_task(
        process_message_send, 
        db=Session(bind=db.connection()), # Pass a new session for the background task
        message_id=db_message.id, 
        content=db_message.content, 
        recipient=db_message.recipient_phone_number
    )

    return db_message

@router.get(
    "/messages", 
    response_model=List[schemas.WhatsAppMessageResponse],
    summary="Retrieve a list of all WhatsApp messages"
)
def list_whatsapp_messages(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of WhatsApp messages with pagination.
    """
    messages = db.query(models.WhatsAppMessage).offset(skip).limit(limit).all()
    return messages

@router.get(
    "/messages/{message_id}", 
    response_model=schemas.WhatsAppMessageWithLogsResponse,
    summary="Retrieve a specific WhatsApp message by ID, including its activity logs"
)
def read_whatsapp_message(
    message_id: UUID, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single WhatsApp message by its unique ID.
    """
    db_message = db.query(models.WhatsAppMessage).options(joinedload(models.WhatsAppMessage.activity_logs)).filter(models.WhatsAppMessage.id == message_id).first()
    if db_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Message with ID {message_id} not found"
        )
    return db_message

@router.patch(
    "/messages/{message_id}", 
    response_model=schemas.WhatsAppMessageResponse,
    summary="Update the status or content of a WhatsApp message"
)
def update_whatsapp_message(
    message_id: UUID, 
    message_update: schemas.WhatsAppMessageUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing WhatsApp message. Only non-null fields in the request body will be updated.
    """
    db_message = db.query(models.WhatsAppMessage).filter(models.WhatsAppMessage.id == message_id).first()
    if db_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Message with ID {message_id} not found"
        )

    update_data = message_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_message, key, value)

    db.commit()
    db.refresh(db_message)
    
    # Log the update
    log_entry = models.WhatsAppActivityLog(
        message_id=message_id,
        activity_type=schemas.ActivityType.CONFIGURATION_CHANGE,
        details=f"Message updated: {', '.join(update_data.keys())}"
    )
    db.add(log_entry)
    db.commit()
    
    return db_message

@router.delete(
    "/messages/{message_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a WhatsApp message"
)
def delete_whatsapp_message(
    message_id: UUID, 
    db: Session = Depends(get_db)
):
    """
    Deletes a WhatsApp message and all associated activity logs.
    """
    db_message = db.query(models.WhatsAppMessage).filter(models.WhatsAppMessage.id == message_id).first()
    if db_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Message with ID {message_id} not found"
        )

    db.delete(db_message)
    db.commit()
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/webhooks/inbound",
    status_code=status.HTTP_200_OK,
    summary="Endpoint for receiving inbound messages and status updates from WhatsApp API (Webhook)"
)
def handle_inbound_webhook(
    payload: dict = Body(..., description="The raw payload from the WhatsApp webhook."),
    db: Session = Depends(get_db)
):
    """
    This endpoint sends receiving a webhook from the WhatsApp API.
    It handles both incoming messages and status updates (delivered, read, failed).
    
    In a real implementation, the payload would be validated and parsed.
    """
    logger.info("Received inbound WhatsApp webhook payload.")
    
    # Simplified logic for demonstration
    if "entry" in payload and payload["entry"]:
        # Assume the payload is a status update for an existing message
        # In a real scenario, we would parse the payload to find the external_message_id
        # and the new status, then update the corresponding message in the DB.
        
        # For simulation, we'll just log an activity
        log_entry = models.WhatsAppActivityLog(
            activity_type=schemas.ActivityType.MESSAGE_RECEIVED,
            details=f"Inbound webhook received. Payload keys: {list(payload.keys())}"
        )
        db.add(log_entry)
        db.commit()
        
        return {"status": "success", "message": "Webhook processed (sent)."}
    
    # Handle verification request (e.g., Facebook challenge)
    if "hub.mode" in payload and payload["hub.mode"] == "subscribe":
        # Return the challenge token to verify the webhook
        return int(payload.get("hub.challenge", 0))

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid webhook payload or verification request."
    )

# --- Activity Log Endpoints (Read-Only) ---

@router.get(
    "/logs",
    response_model=List[schemas.WhatsAppActivityLogResponse],
    summary="Retrieve a list of all activity logs"
)
def list_activity_logs(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all activity logs with pagination.
    """
    logs = db.query(models.WhatsAppActivityLog).order_by(models.WhatsAppActivityLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

@router.get(
    "/logs/{log_id}",
    response_model=schemas.WhatsAppActivityLogResponse,
    summary="Retrieve a specific activity log by ID"
)
def read_activity_log(
    log_id: UUID, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single activity log by its unique ID.
    """
    db_log = db.query(models.WhatsAppActivityLog).filter(models.WhatsAppActivityLog.id == log_id).first()
    if db_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Activity log with ID {log_id} not found"
        )
    return db_log
