import json
import logging
import os
from typing import List, Optional
from urllib import request as urlrequest
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

# --- Meta WhatsApp Business Cloud API Client ---
#
# Messages are only marked SENT when the Meta Graph API returns a real
# message id. DELIVERED/READ statuses are only ever applied from real
# delivery webhooks — never simulated locally.

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v18.0")
WHATSAPP_TIMEOUT = 15  # seconds

# --- Utility Functions (External API Interaction) ---

def send_send_message(message_id: UUID, content: str, recipient: str):
    """
    Sends a message via the Meta WhatsApp Business Cloud API.

    Returns the REAL external message id assigned by Meta. Raises
    RuntimeError when the API is unconfigured or rejects the send.
    """
    if not (WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID):
        raise RuntimeError(
            "WhatsApp Business API not configured "
            "(WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID missing)"
        )

    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": content},
    }
    req = urlrequest.Request(url, data=json.dumps(payload).encode())
    req.add_header("Authorization", f"Bearer {WHATSAPP_ACCESS_TOKEN}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlrequest.urlopen(req, timeout=WHATSAPP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except Exception as exc:
        raise RuntimeError(f"WhatsApp API send failed: {exc}") from exc

    messages = data.get("messages") or []
    if not messages or not messages[0].get("id"):
        raise RuntimeError(f"WhatsApp API returned no message id: {data}")

    external_id = messages[0]["id"]
    logger.info(f"Message {message_id} sent via WhatsApp API. External ID: {external_id}")
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

    The message is marked SENT only with the real Meta message id. DELIVERED
    and READ statuses are applied exclusively by the inbound webhook handler
    when Meta sends real delivery receipts.
    """
    try:
        # 1. Send the message via the real WhatsApp Business API
        external_id = send_send_message(message_id, content, recipient)

        # 2. Update status to SENT with the real external id
        update_message_status_in_db(db, message_id, schemas.MessageStatus.SENT, external_id)

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
    Handles real Meta WhatsApp webhook payloads:

    - **statuses**: delivery receipts (sent/delivered/read/failed) matched to
      our messages by the real external message id.
    - **messages**: inbound customer messages, stored as incoming records.
    """
    logger.info("Received inbound WhatsApp webhook payload.")

    # Map Meta delivery statuses to our internal message statuses
    status_map = {
        "sent": schemas.MessageStatus.SENT,
        "delivered": schemas.MessageStatus.DELIVERED,
        "failed": schemas.MessageStatus.FAILED,
    }
    read_status = getattr(schemas.MessageStatus, "READ", None)
    if read_status is not None:
        status_map["read"] = read_status

    processed = 0

    for entry in payload.get("entry") or []:
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # ── Real delivery receipts ────────────────────────────────────
            for st in value.get("statuses", []) or []:
                external_id = st.get("id")
                meta_status = st.get("status")
                new_status = status_map.get(meta_status)
                if not external_id or new_status is None:
                    continue
                db_message = db.query(models.WhatsAppMessage).filter(
                    models.WhatsAppMessage.external_message_id == external_id
                ).first()
                if db_message is None:
                    logger.warning(f"Delivery receipt for unknown external id {external_id}")
                    continue
                update_message_status_in_db(db, db_message.id, new_status)
                processed += 1

            # ── Real inbound customer messages ────────────────────────────
            contacts = {
                c.get("wa_id"): (c.get("profile") or {}).get("name", "")
                for c in (value.get("contacts") or [])
            }
            metadata = value.get("metadata") or {}
            for msg in value.get("messages", []) or []:
                sender = msg.get("from", "")
                text_body = (msg.get("text") or {}).get("body", "")
                db_message = models.WhatsAppMessage(
                    sender_phone_number=sender,
                    recipient_phone_number=metadata.get("display_phone_number", ""),
                    content=text_body,
                    is_incoming=True,
                    external_message_id=msg.get("id"),
                )
                db.add(db_message)
                db.commit()
                db.refresh(db_message)
                log_entry = models.WhatsAppActivityLog(
                    message_id=db_message.id,
                    activity_type=schemas.ActivityType.MESSAGE_RECEIVED,
                    details=f"Inbound message from {sender} ({contacts.get(sender, 'unknown')}): {text_body[:100]}"
                )
                db.add(log_entry)
                db.commit()
                processed += 1

    if processed:
        return {"status": "success", "processed": processed}

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
