from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime

from . import models
from .config import get_db, logger

router = APIRouter(
    prefix="/messages",
    tags=["messages"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def create_activity_log(db: Session, message_id: int, activity_type: models.ActivityType, details: Optional[str] = None):
    """
    Creates and adds an activity log entry to the database.
    """
    log = models.ActivityLog(
        message_id=message_id,
        activity_type=activity_type,
        details=details,
        timestamp=datetime.utcnow()
    )
    db.add(log)
    # Note: The commit is expected to happen in the main endpoint function.

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.MessageResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new message"
)
def create_message(message: models.MessageCreate, db: Session = Depends(get_db)):
    """
    Creates a new message between two users.
    """
    db_message = models.Message(
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        content=message.content,
        status=models.MessageStatus.SENT
    )
    
    db.add(db_message)
    db.flush() # Flush to get the message ID for the activity log

    create_activity_log(
        db, 
        db_message.id, 
        models.ActivityType.MESSAGE_CREATED, 
        f"Message created by user {message.sender_id}"
    )
    
    db.commit()
    db.refresh(db_message)
    logger.info(f"Message created: ID {db_message.id} from {db_message.sender_id} to {db_message.recipient_id}")
    return db_message

@router.get(
    "/{message_id}", 
    response_model=models.MessageWithLogsResponse,
    summary="Get a message by ID with its activity logs"
)
def read_message(message_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a specific message by its ID, including its full activity history.
    """
    db_message = db.query(models.Message).filter(
        models.Message.id == message_id,
        models.Message.is_deleted == False
    ).first()
    
    if db_message is None:
        logger.warning(f"Message not found: ID {message_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    return db_message

@router.get(
    "/", 
    response_model=List[models.MessageResponse],
    summary="List all messages with optional filtering and pagination"
)
def list_messages(
    sender_id: Optional[int] = Query(None, description="Filter by sender ID"),
    recipient_id: Optional[int] = Query(None, description="Filter by recipient ID"),
    status_filter: Optional[models.MessageStatus] = Query(None, alias="status", description="Filter by message status"),
    skip: int = Query(0, ge=0, description="Number of items to skip (offset)"),
    limit: int = Query(100, le=100, description="Maximum number of items to return (limit)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of messages, allowing for filtering by sender, recipient, and status, 
    and supports pagination.
    """
    query = db.query(models.Message).filter(models.Message.is_deleted == False)
    
    if sender_id is not None:
        query = query.filter(models.Message.sender_id == sender_id)
    if recipient_id is not None:
        query = query.filter(models.Message.recipient_id == recipient_id)
    if status_filter is not None:
        query = query.filter(models.Message.status == status_filter)
        
    messages = query.order_by(models.Message.created_at.desc()).offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(messages)} messages with filters: sender={sender_id}, recipient={recipient_id}, status={status_filter}")
    return messages

@router.put(
    "/{message_id}", 
    response_model=models.MessageResponse,
    summary="Update message content"
)
def update_message(message_id: int, message_update: models.MessageUpdate, db: Session = Depends(get_db)):
    """
    Updates the content of an existing message. Only content update is allowed here.
    Status updates should use the dedicated status endpoint.
    """
    db_message = db.query(models.Message).filter(
        models.Message.id == message_id,
        models.Message.is_deleted == False
    ).first()
    
    if db_message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    update_data = message_update.model_dump(exclude_unset=True)
    
    if "content" in update_data and update_data["content"] is not None:
        old_content = db_message.content
        db_message.content = update_data["content"]
        
        create_activity_log(
            db, 
            db_message.id, 
            models.ActivityType.MESSAGE_UPDATED, 
            f"Content updated from '{old_content[:20]}...' to '{db_message.content[:20]}...'"
        )
        
        db.commit()
        db.refresh(db_message)
        logger.info(f"Message content updated: ID {db_message.id}")
        return db_message
    
    # If no content is provided for update
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update (only 'content' is allowed)")

@router.delete(
    "/{message_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a message"
)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """
    Performs a soft delete on a message by setting the `is_deleted` flag to True.
    """
    db_message = db.query(models.Message).filter(
        models.Message.id == message_id,
        models.Message.is_deleted == False
    ).first()
    
    if db_message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        
    db_message.is_deleted = True
    
    create_activity_log(
        db, 
        db_message.id, 
        models.ActivityType.MESSAGE_DELETED, 
        "Message soft-deleted"
    )
    
    db.commit()
    logger.info(f"Message soft-deleted: ID {db_message.id}")
    return

# --- Business-Specific Endpoints ---

@router.put(
    "/{message_id}/status", 
    response_model=models.MessageResponse,
    summary="Update the status of a message (e.g., delivered, read)"
)
def update_message_status(
    message_id: int, 
    new_status: models.MessageStatus, 
    db: Session = Depends(get_db)
):
    """
    Updates the status of a message. This is typically used to mark a message as 
    DELIVERED or READ by the recipient.
    """
    db_message = db.query(models.Message).filter(
        models.Message.id == message_id,
        models.Message.is_deleted == False
    ).first()
    
    if db_message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        
    old_status = db_message.status
    if old_status == new_status:
        return db_message # No change needed

    db_message.status = new_status
    
    create_activity_log(
        db, 
        db_message.id, 
        models.ActivityType.STATUS_CHANGED, 
        f"Status changed from {old_status.value} to {new_status.value}"
    )
    
    db.commit()
    db.refresh(db_message)
    logger.info(f"Message status updated: ID {db_message.id} to {new_status.value}")
    return db_message

@router.get(
    "/conversation/{user1_id}/{user2_id}", 
    response_model=List[models.MessageResponse],
    summary="Get conversation history between two users"
)
def get_conversation_history(
    user1_id: int, 
    user2_id: int, 
    skip: int = Query(0, ge=0, description="Number of messages to skip (offset)"),
    limit: int = Query(100, le=100, description="Maximum number of messages to return (limit)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves the chronological conversation history between two specific users.
    This includes messages sent from user1 to user2 AND from user2 to user1.
    """
    messages = db.query(models.Message).filter(
        models.Message.is_deleted == False,
        or_(
            (models.Message.sender_id == user1_id) & (models.Message.recipient_id == user2_id),
            (models.Message.sender_id == user2_id) & (models.Message.recipient_id == user1_id)
        )
    ).order_by(models.Message.created_at.asc()).offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(messages)} messages for conversation between {user1_id} and {user2_id}")
    return messages
