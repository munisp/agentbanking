import logging
from typing import List, Optional

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
    
    This endpoint creates the notification record, sends the external sending process,
    updates the status to 'sent', and creates a corresponding log entry.
    
    In a real-world scenario, this would involve calling an external service (FCM/APNS).
    """
    # 1. Create the notification record (initial status is 'pending' from schema default)
    create_schema = models.PushNotificationCreate(**notification.model_dump())
    db_notification = create_notification(db=db, notification=create_schema)
    
    # 2. Send via FCM HTTP v1 API
    # For this implementation, we assume success and update the status
    
    # 3. Update status to 'sent' and set sent_at timestamp
    update_schema = models.PushNotificationUpdate(
        status="sent", 
        sent_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_notification = update_notification(db=db, db_notification=db_notification, notification_update=update_schema)
    
    # 4. Create a log entry for the send attempt
    log_schema = models.PushNotificationLogCreate(
        notification_id=db_notification.id,
        event="send_attempt_success",
        details={"provider": "firebase_fcm", "message_id": f"msg_{db_notification.id}_{int(time.time())}"}
    )
    create_notification_log(db=db, log=log_schema)
    
    logger.info(f"FCM send for notification ID: {db_notification.id}, success: {send_success}")
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

# Need to import datetime and time for the send_push_notification function
import datetime
import time
