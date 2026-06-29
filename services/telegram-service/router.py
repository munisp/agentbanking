import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import get_db, get_settings

# --- Configuration and Logging ---
settings = get_settings()
router = APIRouter(
    prefix="/api/v1/telegram",
    tags=["telegram-service"],
)

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Utility Functions (Database Operations) ---

def get_chat_by_id(db: Session, chat_id: int) -> models.TelegramChat:
    """Fetches a TelegramChat record by its internal database ID."""
    chat = db.query(models.TelegramChat).filter(models.TelegramChat.id == chat_id).first()
    if not chat:
        logger.warning(f"TelegramChat with ID {chat_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TelegramChat with ID {chat_id} not found",
        )
    return chat

def get_chat_by_telegram_id(db: Session, telegram_chat_id: str) -> Optional[models.TelegramChat]:
    """Fetches a TelegramChat record by its external Telegram chat_id."""
    return db.query(models.TelegramChat).filter(models.TelegramChat.chat_id == telegram_chat_id).first()

# --- CRUD Endpoints for TelegramChat ---

@router.post(
    "/chats/",
    response_model=models.TelegramChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Telegram Chat record",
    description="Registers a new Telegram chat (user, group, or channel) in the database.",
)
def create_chat(
    chat: models.TelegramChatCreate, db: Session = Depends(get_db)
):
    """
    Creates a new TelegramChat record.

    If a chat with the given `chat_id` already exists, it returns the existing record.
    This prevents duplicate entries for the same Telegram chat.
    """
    db_chat = get_chat_by_telegram_id(db, telegram_chat_id=chat.chat_id)
    if db_chat:
        logger.info(f"Chat with Telegram ID {chat.chat_id} already exists. Returning existing record.")
        return db_chat

    db_chat = models.TelegramChat(**chat.model_dump())
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    logger.info(f"Created new TelegramChat with ID {db_chat.id}")
    return db_chat


@router.get(
    "/chats/",
    response_model=List[models.TelegramChatResponse],
    summary="List all Telegram Chat records",
    description="Retrieves a list of all registered Telegram chats with pagination.",
)
def read_chats(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of TelegramChat records with optional pagination.
    """
    chats = db.query(models.TelegramChat).offset(skip).limit(limit).all()
    return chats


@router.get(
    "/chats/{chat_id}",
    response_model=models.TelegramChatResponse,
    summary="Get a Telegram Chat record by internal ID",
    description="Retrieves a single Telegram Chat record using its internal database ID.",
)
def read_chat(chat_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single TelegramChat record by its internal database ID.

    Raises:
        HTTPException: 404 Not Found if the chat does not exist.
    """
    return get_chat_by_id(db, chat_id)


@router.put(
    "/chats/{chat_id}",
    response_model=models.TelegramChatResponse,
    summary="Update a Telegram Chat record",
    description="Updates an existing Telegram Chat record using its internal database ID.",
)
def update_chat(
    chat_id: int, chat: models.TelegramChatUpdate, db: Session = Depends(get_db)
):
    """
    Updates an existing TelegramChat record.

    Raises:
        HTTPException: 404 Not Found if the chat does not exist.
    """
    db_chat = get_chat_by_id(db, chat_id)
    
    update_data = chat.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_chat, key, value)

    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    logger.info(f"Updated TelegramChat with ID {chat_id}")
    return db_chat


@router.delete(
    "/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Telegram Chat record",
    description="Deletes a Telegram Chat record using its internal database ID.",
)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """
    Deletes a TelegramChat record.

    Raises:
        HTTPException: 404 Not Found if the chat does not exist.
    """
    db_chat = get_chat_by_id(db, chat_id)
    
    db.delete(db_chat)
    db.commit()
    logger.info(f"Deleted TelegramChat with ID {chat_id}")
    return {"ok": True}

# --- Business Logic Endpoints ---

class TelegramUpdate(models.BaseModel):
    """
    A simplified Pydantic model for a Telegram Update object,
    used for the webhook endpoint.
    """
    update_id: int
    message: Optional[dict] = None
    edited_message: Optional[dict] = None
    channel_post: Optional[dict] = None
    # Add other fields as needed for full Telegram API compliance

@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Telegram Webhook Handler",
    description="Receives updates from the Telegram Bot API. This is the main entry point for bot logic.",
)
def telegram_webhook(
    update: TelegramUpdate, db: Session = Depends(get_db)
):
    """
    Handles incoming Telegram updates (messages, callbacks, etc.).

    This function processes the update, logs the activity, and performs
    the necessary business logic (e.g., responding to a command).
    """
    logger.info(f"Received Telegram update: {update.update_id}")

    # 1. Extract relevant chat information
    chat_info = update.message or update.edited_message or update.channel_post
    if not chat_info:
        logger.warning("Update received without a message/post. Ignoring.")
        return {"status": "ignored", "reason": "No message/post in update"}

    telegram_chat_id = str(chat_info["chat"]["id"])
    chat_type = chat_info["chat"]["type"]
    title = chat_info["chat"].get("title") or chat_info["chat"].get("first_name")
    username = chat_info["chat"].get("username")
    
    # 2. Find or create the chat record
    db_chat = get_chat_by_telegram_id(db, telegram_chat_id)
    if not db_chat:
        chat_data = models.TelegramChatCreate(
            chat_id=telegram_chat_id,
            chat_type=chat_type,
            title=title,
            username=username,
        )
        db_chat = models.TelegramChat(**chat_data.model_dump())
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        logger.info(f"New chat registered from webhook: {telegram_chat_id}")
    else:
        # Optional: Update chat details if they have changed (e.g., title)
        db_chat.title = title
        db_chat.username = username
        db.commit()

    # 3. Log the activity
    activity_type = "MESSAGE_RECEIVED" if update.message else "OTHER_UPDATE"
    activity_description = chat_info.get("text", "No text content")
    
    activity_log = models.ActivityLogCreate(
        chat_id=db_chat.id,
        activity_type=activity_type,
        description=activity_description,
    )
    db_activity = models.ActivityLog(**activity_log.model_dump())
    db.add(db_activity)
    db.commit()
    
    # 4. Business Logic (send response)
    # In a real application, you would use the TELEGRAM_BOT_TOKEN from settings
    # to send a response back to the chat_info["chat"]["id"].
    if update.message and update.message.get("text", "").lower() == "/start":
        logger.info(f"Handling /start command for chat {telegram_chat_id}")
        # Example: send_telegram_message(telegram_chat_id, "Welcome to the service!")
        pass

    return {"status": "processed", "update_id": update.update_id}


@router.get(
    "/chats/{chat_id}/activities",
    response_model=List[models.ActivityLogResponse],
    summary="List activity logs for a chat",
    description="Retrieves all activity logs associated with a specific Telegram Chat record.",
)
def read_chat_activities(
    chat_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of ActivityLog records for a given TelegramChat ID.

    Raises:
        HTTPException: 404 Not Found if the chat does not exist.
    """
    # Ensure the chat exists
    get_chat_by_id(db, chat_id) 
    
    activities = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.chat_id == chat_id)
        .order_by(models.ActivityLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return activities
