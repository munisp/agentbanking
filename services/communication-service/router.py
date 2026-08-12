import logging
import os
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Local imports
from . import models
from .config import get_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/communications",
    tags=["communications"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions (Sendd Business Logic) ---

def _create_log_entry(db: Session, communication_id: int, event: str, details: str = None):
    """Creates a log entry for a communication."""
    log = models.CommunicationLog(
        communication_id=communication_id,
        event=event,
        details=details
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

# Provider endpoints are configured via environment. When a channel has no
# provider configured, sending FAILS LOUDLY instead of fabricating delivery.
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "")
SMS_GATEWAY_URL = os.getenv("SMS_GATEWAY_URL", "")
PUSH_NOTIFICATION_SERVICE_URL = os.getenv("PUSH_NOTIFICATION_SERVICE_URL", "")
PROVIDER_TIMEOUT = float(os.getenv("COMMUNICATION_PROVIDER_TIMEOUT", "15"))


def _dispatch_to_provider(communication: "models.Communication") -> str:
    """Dispatch a communication to its real channel provider.

    Returns a short description of the dispatch result. Raises RuntimeError
    when no provider is configured or the provider rejects the message, so
    callers record a real failure instead of a fake 'sent'.
    """
    import json as _json

    import httpx

    comm_type = communication.type.value
    if comm_type == "email":
        if not EMAIL_SERVICE_URL:
            raise RuntimeError("EMAIL_SERVICE_URL is not configured")
        url = f"{EMAIL_SERVICE_URL}/api/v1/send"
        payload = {
            "to": communication.recipient,
            "subject": getattr(communication, "subject", None) or "Notification",
            "body": communication.body,
        }
    elif comm_type == "sms":
        if not SMS_GATEWAY_URL:
            raise RuntimeError("SMS_GATEWAY_URL is not configured")
        url = f"{SMS_GATEWAY_URL}/api/v1/sms-gateway/send"
        payload = {"recipient": communication.recipient, "message": communication.body}
    elif comm_type in ("push", "push_notification"):
        if not PUSH_NOTIFICATION_SERVICE_URL:
            raise RuntimeError("PUSH_NOTIFICATION_SERVICE_URL is not configured")
        url = f"{PUSH_NOTIFICATION_SERVICE_URL}/notifications/send"
        payload = {
            "user_ids": [communication.recipient],
            "title": getattr(communication, "subject", None) or "Notification",
            "body": communication.body,
        }
    else:
        raise RuntimeError(f"No provider configured for communication type '{comm_type}'")

    with httpx.Client(timeout=PROVIDER_TIMEOUT) as client:
        resp = client.post(url, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"Provider rejected {comm_type} send: HTTP {resp.status_code}: {resp.text[:200]}")
    return f"Dispatched via {url} (HTTP {resp.status_code})"


def _send_send(db: Session, communication: models.Communication):
    """Send a communication via its configured external provider.

    FAIL LOUD: the previous implementation marked every communication SENT
    and logged a fake 'delivery_success' via a dummy provider. Now the
    message is only marked SENT after a real provider accepts it; otherwise
    the communication is marked FAILED and an error is raised.
    """
    logger.info(f"Attempting to send {communication.type.value} to {communication.recipient}...")

    dispatch_result = _dispatch_to_provider(communication)

    communication.status = models.CommunicationStatus.SENT
    communication.sent_at = datetime.utcnow()
    db.add(communication)
    db.commit()
    db.refresh(communication)

    _create_log_entry(
        db,
        communication.id,
        "attempted_send",
        f"Provider accepted message. New status: {communication.status.value}. {dispatch_result}",
    )

    logger.info(f"Communication ID {communication.id} accepted by provider.")
    return communication


# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.CommunicationResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new communication record",
    description="Creates a new communication record in the database with status 'pending'."
)
def create_communication(
    communication: models.CommunicationCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new communication record. The communication is initially set to 'pending' 
    and must be explicitly sent via the `/send` endpoint or a background worker.
    """
    db_communication = models.Communication(
        **communication.model_dump(),
        status=models.CommunicationStatus.PENDING
    )
    db.add(db_communication)
    db.commit()
    db.refresh(db_communication)
    
    _create_log_entry(db, db_communication.id, "created", "Communication record created.")
    
    return db_communication

@router.get(
    "/{communication_id}", 
    response_model=models.CommunicationResponse,
    summary="Get a communication by ID",
    description="Retrieves a single communication record, including its logs."
)
def read_communication(
    communication_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a communication by its unique ID.
    Raises 404 if the communication is not found.
    """
    communication = db.query(models.Communication).filter(models.Communication.id == communication_id).first()
    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Communication with ID {communication_id} not found"
        )
    return communication

@router.get(
    "/", 
    response_model=List[models.CommunicationResponse],
    summary="List all communications",
    description="Retrieves a list of all communication records, ordered by creation date."
)
def list_communications(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of communication records.
    """
    communications = db.query(models.Communication).order_by(desc(models.Communication.created_at)).offset(skip).limit(limit).all()
    return communications

@router.patch(
    "/{communication_id}", 
    response_model=models.CommunicationResponse,
    summary="Update communication status or metadata",
    description="Updates the status, subject, body, or metadata of an existing communication."
)
def update_communication(
    communication_id: int, 
    communication_update: models.CommunicationUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing communication record. Only non-null fields in the request body are updated.
    """
    db_communication = db.query(models.Communication).filter(models.Communication.id == communication_id).first()
    if db_communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Communication with ID {communication_id} not found"
        )

    update_data = communication_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_communication, key, value)

    db.add(db_communication)
    db.commit()
    db.refresh(db_communication)
    
    _create_log_entry(db, db_communication.id, "updated", f"Fields updated: {', '.join(update_data.keys())}")
    
    return db_communication

@router.delete(
    "/{communication_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a communication record",
    description="Deletes a communication record and all associated logs."
)
def delete_communication(
    communication_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a communication record by ID.
    Raises 404 if the communication is not found.
    """
    db_communication = db.query(models.Communication).filter(models.Communication.id == communication_id).first()
    if db_communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Communication with ID {communication_id} not found"
        )
    
    db.delete(db_communication)
    db.commit()
    logger.info(f"Communication ID {communication_id} and its logs deleted.")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/send",
    response_model=models.CommunicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Create and immediately send a new communication",
    description="Creates a new communication record and immediately attempts to send it via the appropriate provider."
)
def send_communication(
    communication_data: models.CommunicationSend,
    db: Session = Depends(get_db)
):
    """
    Handles the creation and immediate sending of a communication.
    
    The process involves:
    1. Creating the communication record with status 'pending'.
    2. Calling the internal `_send_send` function to process the sending.
    3. Updating the status to 'sent' (or 'failed') and logging the attempt.
    
    Returns the updated communication record.
    """
    # 1. Create the communication record
    db_communication = models.Communication(
        **communication_data.model_dump(),
        status=models.CommunicationStatus.PENDING
    )
    db.add(db_communication)
    db.commit()
    db.refresh(db_communication)
    
    _create_log_entry(db, db_communication.id, "created_for_send", "Communication record created for immediate sending.")
    
    # 2. Attempt to send (sent)
    try:
        sent_communication = _send_send(db, db_communication)
        return sent_communication
    except Exception as e:
        logger.error(f"Failed to send communication ID {db_communication.id}: {e}")
        db_communication.status = models.CommunicationStatus.FAILED
        db.add(db_communication)
        db.commit()
        db.refresh(db_communication)
        _create_log_entry(db, db_communication.id, "send_failed", str(e))
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to send communication: {e}"
        )

@router.get(
    "/status/{status_type}",
    response_model=List[models.CommunicationResponse],
    summary="List communications by status",
    description="Retrieves a list of communications filtered by a specific status (e.g., 'pending', 'failed')."
)
def list_communications_by_status(
    status_type: models.CommunicationStatus,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of communication records filtered by status.
    """
    communications = db.query(models.Communication).filter(models.Communication.status == status_type).order_by(desc(models.Communication.created_at)).offset(skip).limit(limit).all()
    return communications
