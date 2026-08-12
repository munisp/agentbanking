import datetime
import json
import logging
import os
from typing import List, Optional
from urllib import request as urlrequest

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import get_db, get_settings

# --- Configuration and Logging ---

settings = get_settings()
router = APIRouter(
    prefix="/notifications",
    tags=["Push Notifications"],
    responses={404: {"description": "Not found"}},
)

# Set up logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Firebase Cloud Messaging (FCM) HTTP v1 Client ---
#
# Notifications are only marked 'sent' when the FCM HTTP v1 API returns a
# successful response with a real message name. There is no simulated path.

FCM_PROJECT_ID = os.getenv("FCM_PROJECT_ID", "")
FCM_TIMEOUT = 15  # seconds


def _get_fcm_access_token() -> str:
    """Mint an OAuth2 access token from the FCM service account credentials.

    Credentials are read from FCM_SERVICE_ACCOUNT_JSON (inline JSON) or
    GOOGLE_APPLICATION_CREDENTIALS (path to the service account file).
    """
    creds_json = os.getenv("FCM_SERVICE_ACCOUNT_JSON", "")
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GoogleAuthRequest
    except ImportError as exc:
        raise RuntimeError(
            "google-auth library is required for FCM HTTP v1 (pip install google-auth)"
        ) from exc

    scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
    if creds_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json), scopes=scopes)
    elif creds_path:
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=scopes)
    else:
        raise RuntimeError(
            "FCM service account credentials not configured "
            "(set FCM_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS)"
        )
    creds.refresh(GoogleAuthRequest())
    return creds.token


def send_fcm_notification(device_token: str, title: str, body: str, data: Optional[dict] = None) -> dict:
    """Send a push notification via the FCM HTTP v1 API.

    Returns {"message_id": <real FCM message name>} on success.
    Raises RuntimeError on any failure.
    """
    if not FCM_PROJECT_ID:
        raise RuntimeError("FCM_PROJECT_ID not configured")
    if not device_token:
        raise RuntimeError("device token is required")

    access_token = _get_fcm_access_token()
    message = {
        "message": {
            "token": device_token,
            "notification": {"title": title, "body": body},
        }
    }
    if data:
        message["message"]["data"] = {str(k): str(v) for k, v in data.items()}

    req = urlrequest.Request(
        f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send",
        data=json.dumps(message).encode(),
    )
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urlrequest.urlopen(req, timeout=FCM_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except Exception as exc:
        raise RuntimeError(f"FCM send failed: {exc}") from exc

    name = payload.get("name")
    if not name:
        raise RuntimeError(f"FCM response missing message name: {payload}")
    return {"message_id": name}

# --- CRUD Helper Functions ---

def get_notification(db: Session, notification_id: int) -> Optional[models.PushNotification]:
    """Retrieve a single notification by ID."""
    return db.query(models.PushNotification).filter(models.PushNotification.id == notification_id).first()

def get_notifications(db: Session, skip: int = 0, limit: int = 100) -> List[models.PushNotification]:
    """Retrieve a list of all notifications."""
    return db.query(models.PushNotification).offset(skip).limit(limit).all()

def get_notifications_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.PushNotification]:
    """Retrieve a list of notifications for a specific user."""
    return db.query(models.PushNotification).filter(models.PushNotification.user_id == user_id).offset(skip).limit(limit).all()

def create_notification(db: Session, notification: models.PushNotificationCreate) -> models.PushNotification:
    """Create a new notification record."""
    db_notification = models.PushNotification(**notification.model_dump(exclude_unset=True))
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    logger.info(f"Created notification ID: {db_notification.id} for user: {db_notification.user_id}")
    return db_notification

def update_notification(db: Session, db_notification: models.PushNotification, notification_update: models.PushNotificationUpdate) -> models.PushNotification:
    """Update an existing notification record."""
    update_data = notification_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_notification, key, value)
    
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    logger.info(f"Updated notification ID: {db_notification.id}")
    return db_notification

def delete_notification(db: Session, db_notification: models.PushNotification):
    """Delete a notification record."""
    db.delete(db_notification)
    db.commit()
    logger.warning(f"Deleted notification ID: {db_notification.id}")

def create_notification_log(db: Session, log: models.PushNotificationLogCreate) -> models.PushNotificationLog:
    """Create a new log entry for a notification."""
    db_log = models.PushNotificationLog(**log.model_dump(exclude_unset=True))
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.debug(f"Created log ID: {db_log.id} for notification: {db_log.notification_id}")
    return db_log

# --- API Endpoints ---

@router.post("/", response_model=models.PushNotificationResponse, status_code=status.HTTP_201_CREATED)
def create_new_notification(notification: models.PushNotificationCreate, db: Session = Depends(get_db)):
    """
    **Create a new Push Notification record.**
    
    This endpoint creates a record in the database. It does not immediately send the notification.
    The status will typically be 'pending'.
    """
    return create_notification(db=db, notification=notification)

@router.get("/", response_model=List[models.PushNotificationResponse])
def list_notifications(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    **Retrieve a list of all Push Notifications.**
    
    Supports pagination via `skip` and `limit` query parameters.
    """
    notifications = get_notifications(db, skip=skip, limit=limit)
    return notifications

@router.get("/{notification_id}", response_model=models.PushNotificationWithLogsResponse)
def read_notification(notification_id: int, db: Session = Depends(get_db)):
    """
    **Retrieve a single Push Notification by ID, including its activity logs.**
    
    Raises 404 if the notification is not found.
    """
    db_notification = get_notification(db, notification_id=notification_id)
    if db_notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return db_notification

@router.put("/{notification_id}", response_model=models.PushNotificationResponse)
def update_existing_notification(notification_id: int, notification: models.PushNotificationUpdate, db: Session = Depends(get_db)):
    """
    **Update an existing Push Notification record.**
    
    Allows modification of content, device token, or status.
    Raises 404 if the notification is not found.
    """
    db_notification = get_notification(db, notification_id=notification_id)
    if db_notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    return update_notification(db=db, db_notification=db_notification, notification_update=notification)

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_notification(notification_id: int, db: Session = Depends(get_db)):
    """
    **Delete a Push Notification record.**
    
    Also deletes all associated logs due to the cascade setting in the model.
    Raises 404 if the notification is not found.
    """
    db_notification = get_notification(db, notification_id=notification_id)
    if db_notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    delete_notification(db=db, db_notification=db_notification)
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.post("/send", response_model=models.PushNotificationResponse, status_code=status.HTTP_202_ACCEPTED)
def send_push_notification(notification: models.PushNotificationBase, db: Session = Depends(get_db)):
    """
    **Send a Push Notification via FCM.**

    Creates the notification record, sends it via the FCM HTTP v1 API using
    service-account credentials, and marks it 'sent' only when FCM returns a
    real message name. On any FCM failure the record is marked 'failed' and a
    502 is raised.
    """
    # 1. Create the notification record (initial status is 'pending' from schema default)
    create_schema = models.PushNotificationCreate(**notification.model_dump())
    db_notification = create_notification(db=db, notification=create_schema)

    # 2. Send via the real FCM HTTP v1 API
    device_token = getattr(notification, "device_token", None)
    title = getattr(notification, "title", None) or "54agent"
    body = getattr(notification, "body", None) or getattr(notification, "message", None) or ""
    data = getattr(notification, "data", None)

    try:
        fcm_result = send_fcm_notification(device_token, title, body, data)
    except RuntimeError as exc:
        logger.error(f"FCM send failed for notification ID {db_notification.id}: {exc}")
        update_notification(
            db=db,
            db_notification=db_notification,
            notification_update=models.PushNotificationUpdate(status="failed"),
        )
        create_notification_log(db=db, log=models.PushNotificationLogCreate(
            notification_id=db_notification.id,
            event="send_attempt_failed",
            details={"provider": "firebase_fcm", "error": str(exc)},
        ))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Push notification send failed: {exc}",
        )

    # 3. Update status to 'sent' and set sent_at timestamp (real FCM success)
    update_schema = models.PushNotificationUpdate(
        status="sent",
        sent_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_notification = update_notification(db=db, db_notification=db_notification, notification_update=update_schema)

    # 4. Create a log entry for the successful send attempt with the REAL FCM id
    log_schema = models.PushNotificationLogCreate(
        notification_id=db_notification.id,
        event="send_attempt_success",
        details={"provider": "firebase_fcm", "message_id": fcm_result["message_id"]},
    )
    create_notification_log(db=db, log=log_schema)

    logger.info(f"FCM send for notification ID: {db_notification.id}, message_id: {fcm_result['message_id']}")
    return db_notification

@router.get("/user/{user_id}", response_model=List[models.PushNotificationResponse])
def list_notifications_for_user(user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    **Retrieve all Push Notifications sent to a specific user.**
    
    Supports pagination.
    """
    notifications = get_notifications_by_user(db, user_id=user_id, skip=skip, limit=limit)
    return notifications

@router.post("/{notification_id}/log", response_model=models.PushNotificationLogResponse, status_code=status.HTTP_201_CREATED)
def add_notification_log(notification_id: int, log: models.PushNotificationLogBase, db: Session = Depends(get_db)):
    """
    **Add an activity log entry to an existing Push Notification.**
    
    This is typically used to record external events like delivery receipts, read status, or errors.
    Raises 404 if the notification is not found.
    """
    db_notification = get_notification(db, notification_id=notification_id)
    if db_notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    log_create_schema = models.PushNotificationLogCreate(notification_id=notification_id, **log.model_dump())
    return create_notification_log(db=db, log=log_create_schema)
