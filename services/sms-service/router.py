import base64
import json
import logging
import os
from typing import List, Optional
from datetime import datetime
from urllib import request as urlrequest
from urllib.parse import urlencode

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

# --- SMS Provider Client (Africa's Talking / Twilio) ---
#
# Messages are only marked SENT when the configured provider returns a
# successful response with a real provider message ID. No console/print
# fallback may ever report success.

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "africas_talking").lower()

AT_API_KEY = os.getenv("AT_API_KEY", "")
AT_USERNAME = os.getenv("AT_USERNAME", "")
AT_ENVIRONMENT = os.getenv("AT_ENVIRONMENT", "production").lower()
AT_BASE_URL = (
    "https://api.sandbox.africastalking.com"
    if AT_ENVIRONMENT == "sandbox"
    else "https://api.africastalking.com"
)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

PROVIDER_TIMEOUT = 15  # seconds


def send_via_provider(recipient: str, body: str, sender_id: Optional[str] = None) -> dict:
    """Send an SMS via the configured provider.

    Returns {"success": True, "provider_message_id": ...} ONLY on a real
    provider success response with a real provider message id.
    """
    if SMS_PROVIDER == "africas_talking":
        if not (AT_API_KEY and AT_USERNAME):
            return {"success": False, "error": "Africa's Talking provider not configured (AT_API_KEY/AT_USERNAME missing)"}
        payload = urlencode({
            "username": AT_USERNAME,
            "to": recipient,
            "message": body,
            "from": sender_id or "",
        }).encode()
        req = urlrequest.Request(f"{AT_BASE_URL}/version1/messaging", data=payload)
        req.add_header("apiKey", AT_API_KEY)
        req.add_header("Accept", "application/json")
        try:
            with urlrequest.urlopen(req, timeout=PROVIDER_TIMEOUT) as resp:
                data = json.loads(resp.read().decode() or "{}")
        except Exception as exc:
            logger.error(f"[sms] Africa's Talking send failed: {exc}")
            return {"success": False, "error": str(exc)}
        recipients = data.get("SMSMessageData", {}).get("Recipients", [])
        if recipients:
            first = recipients[0]
            provider_status = str(first.get("status", "")).lower()
            message_id = first.get("messageId", "")
            if provider_status not in ("failed", "rejected") and message_id:
                return {"success": True, "provider": "africastalking", "provider_message_id": message_id, "cost": first.get("cost", "")}
        return {"success": False, "error": f"Africa's Talking rejected message: {data}"}

    if SMS_PROVIDER == "twilio":
        if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
            return {"success": False, "error": "Twilio provider not configured (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER missing)"}
        payload = urlencode({
            "From": TWILIO_FROM_NUMBER,
            "To": recipient,
            "Body": body,
        }).encode()
        req = urlrequest.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            data=payload,
        )
        auth = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urlrequest.urlopen(req, timeout=PROVIDER_TIMEOUT) as resp:
                data = json.loads(resp.read().decode() or "{}")
        except Exception as exc:
            logger.error(f"[sms] Twilio send failed: {exc}")
            return {"success": False, "error": str(exc)}
        sid = data.get("sid")
        if sid and data.get("status") not in ("failed", "undelivered"):
            return {"success": True, "provider": "twilio", "provider_message_id": sid, "provider_status": data.get("status")}
        return {"success": False, "error": f"Twilio rejected message: {data}"}

    return {"success": False, "error": f"Unknown SMS_PROVIDER '{SMS_PROVIDER}'"}


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
    Sends an SMS message via the configured SMS provider.

    The status is set to SENT only when the provider returns a successful
    response with a real provider message ID. On any provider failure the
    status is set to FAILED and a 502 is returned.
    """
    db_sms = get_sms_message(db, sms_id)
    if not db_sms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found")

    if db_sms.status in [models.SMSStatus.SENT.value, models.SMSStatus.DELIVERED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"SMS message ID {sms_id} is already {db_sms.status}"
        )

    # Send via the real SMS provider
    result = send_via_provider(db_sms.recipient_number, db_sms.message_body, db_sms.sender_id)

    if result.get("success"):
        db_sms.status = models.SMSStatus.SENT.value
        db_sms.sent_at = datetime.utcnow()

        log = models.SMSActivityLog(
            sms_message=db_sms,
            activity_type="SEND_ATTEMPT",
            details=(
                f"SMS sent via {result.get('provider', SMS_PROVIDER)}; "
                f"provider_message_id={result.get('provider_message_id')}"
            )
        )
        db.add(log)
        db.commit()
        db.refresh(db_sms)
        logger.info(f"SMS message sent, ID: {sms_id}, provider_message_id={result.get('provider_message_id')}")
        return db_sms

    # Provider failure — mark FAILED, never SENT
    failed_status = getattr(models.SMSStatus, "FAILED", None)
    db_sms.status = failed_status.value if failed_status is not None else "FAILED"
    log = models.SMSActivityLog(
        sms_message=db_sms,
        activity_type="SEND_ATTEMPT",
        details=f"SMS send FAILED via provider {SMS_PROVIDER}: {result.get('error')}"
    )
    db.add(log)
    db.commit()
    logger.error(f"SMS message send failed, ID: {sms_id}: {result.get('error')}")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"SMS provider send failed: {result.get('error')}"
    )

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
