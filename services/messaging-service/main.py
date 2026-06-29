"""
Messaging Service - Agent Banking Platform
Handles real-time messaging between agents and customers with tenant isolation
Includes automatic message translation based on user language preferences
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import httpx
import threading
import logging

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

import os

logger = logging.getLogger(__name__)
AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")
DEFAULT_TENANT_ID = os.getenv("TENANT_ID", "54agent")

# Database setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/agent_banking"
)
TRANSLATION_SERVICE_URL = os.getenv(
    "TRANSLATION_SERVICE_URL", "http://realtime-translation:8000"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
class Conversation(Base):
    """Conversation thread between agent and customer"""

    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    agent_keycloak_id = Column(String, nullable=False, index=True)
    customer_keycloak_id = Column(String, nullable=False, index=True)
    agent_name = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    agent_language = Column(String, default="en")  # Agent's preferred language
    customer_language = Column(String, default="en")  # Customer's preferred language
    auto_translate = Column(Boolean, default=True)  # Enable auto-translation
    last_message = Column(Text)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    unread_count_agent = Column(String, default="0")  # Unread by agent
    unread_count_customer = Column(String, default="0")  # Unread by customer
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_tenant_agent", "tenant_id", "agent_keycloak_id"),
        Index("idx_tenant_customer", "tenant_id", "customer_keycloak_id"),
        Index("idx_agent_customer", "agent_keycloak_id", "customer_keycloak_id"),
    )


class Message(Base):
    """Individual message in a conversation"""

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    sender_keycloak_id = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    sender_type = Column(String, nullable=False)  # 'agent' or 'customer'
    channel = Column(
        String, nullable=False, default="web"
    )  # Communication channel: web, mobile, whatsapp, etc.
    content = Column(Text, nullable=False)  # Original message in sender's language
    content_translated = Column(Text)  # Translated message for recipient
    source_language = Column(String, default="en")  # Detected/set source language
    target_language = Column(String)  # Language translated to
    translation_engine = Column(String)  # Engine used for translation
    message_type = Column(String, default="text")  # text, image, file
    attachment_url = Column(String)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_conversation_created", "conversation_id", "created_at"),
        Index("idx_tenant_conversation", "tenant_id", "conversation_id"),
    )


# Pydantic Models
class MessageCreate(BaseModel):
    conversation_id: Optional[str] = None
    customer_keycloak_id: Optional[str] = None  # Required if no conversation_id
    content: str
    message_type: str = "text"
    attachment_url: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_keycloak_id: str
    sender_name: str
    sender_type: str
    channel: str
    content: str
    content_translated: Optional[str]
    source_language: str
    target_language: Optional[str]
    translation_engine: Optional[str]
    message_type: str
    attachment_url: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: str
    tenant_id: str
    agent_keycloak_id: str
    customer_keycloak_id: str
    agent_name: str
    customer_name: str
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    agent_language: str = "en"
    customer_language: str = "en"
    auto_translate: bool = True
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int  # From perspective of requester
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LanguagePreferenceUpdate(BaseModel):
    language: str = Field(..., pattern="^(en|yo|ha|ig|pcm|fr|ar)$")
    auto_translate: bool = True


class ConversationCreate(BaseModel):
    agent_keycloak_id: str
    customer_keycloak_id: str
    agent_name: str
    customer_name: str
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    agent_language: str = "en"
    customer_language: str = "en"


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json(message)


manager = ConnectionManager()

# FastAPI app
app = FastAPI(title="Messaging Service", version="1.0.0")


@app.on_event("startup")
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"DB table creation failed (non-fatal): {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def emit_audit_event(request: Request, status_code: int):
    event_type_map = {
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }
    event_type = event_type_map.get(request.method)
    if not event_type:
        return

    tenant_id = request.headers.get("x-tenant-id") or DEFAULT_TENANT_ID
    actor_id = request.headers.get("x-keycloak-id") or "system"

    payload = {
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "event_data": {
            "service": "messaging-service",
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "query": str(request.url.query),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    def _send():
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{AUDIT_SVC_URL}/audits",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-tenant-id": tenant_id,
                        "x-keycloak-id": actor_id,
                    },
                )
        except Exception:
            logger.warning("Failed to emit audit event")

    threading.Thread(target=_send, daemon=True).start()


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and response.status_code < 500
        and not request.url.path.startswith(("/docs", "/openapi", "/redoc"))
    ):
        emit_audit_event(request, response.status_code)
    return response


# Helper functions
async def translate_text(
    text: str,
    source_language: str,
    target_language: str,
    message_id: Optional[str] = None,
) -> dict:
    """Call translation service to translate text"""
    if source_language == target_language:
        return {
            "translated_text": text,
            "engine_used": "passthrough",
            "source_language": source_language,
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{TRANSLATION_SERVICE_URL}/api/translate/",
                json={
                    "text": text,
                    "source_language": source_language,
                    "target_language": target_language,
                    "message_id": message_id,
                    "apply_glossary": True,
                },
            )
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback to original text if translation fails
                return {
                    "translated_text": text,
                    "engine_used": "fallback",
                    "source_language": source_language,
                }
    except Exception as e:
        print(f"Translation error: {e}")
        return {
            "translated_text": text,
            "engine_used": "error_fallback",
            "source_language": source_language,
        }


def get_or_create_conversation(
    db: Session,
    tenant_id: str,
    agent_keycloak_id: str,
    customer_keycloak_id: str,
    agent_name: str,
    customer_name: str,
    agent_language: str = "en",
    customer_language: str = "en",
) -> Conversation:
    """Get existing conversation or create new one"""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant_id,
            Conversation.agent_keycloak_id == agent_keycloak_id,
            Conversation.customer_keycloak_id == customer_keycloak_id,
        )
        .first()
    )

    if not conversation:
        conversation = Conversation(
            tenant_id=tenant_id,
            agent_keycloak_id=agent_keycloak_id,
            customer_keycloak_id=customer_keycloak_id,
            agent_name=agent_name,
            customer_name=customer_name,
            agent_language=agent_language,
            customer_language=customer_language,
            auto_translate=True,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    return conversation


# API Endpoints
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "messaging"}


@app.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(
    tenant_id: str = Query(...),
    keycloak_id: str = Query(...),
    user_type: str = Query(..., pattern="^(agent|customer)$"),
    db: Session = Depends(get_db),
):
    """Get all conversations for a user (agent or customer)"""
    if user_type == "agent":
        conversations = (
            db.query(Conversation)
            .filter(
                Conversation.tenant_id == tenant_id,
                Conversation.agent_keycloak_id == keycloak_id,
            )
            .order_by(desc(Conversation.last_message_at))
            .all()
        )

        # Add unread count from agent's perspective
        result = []
        for conv in conversations:
            conv_dict = {
                "id": conv.id,
                "tenant_id": conv.tenant_id,
                "agent_keycloak_id": conv.agent_keycloak_id,
                "customer_keycloak_id": conv.customer_keycloak_id,
                "agent_name": conv.agent_name,
                "customer_name": conv.customer_name,
                "business_id": None,
                "business_name": None,
                "agent_language": conv.agent_language or "en",
                "customer_language": conv.customer_language or "en",
                "auto_translate": (
                    conv.auto_translate if conv.auto_translate is not None else True
                ),
                "last_message": conv.last_message,
                "last_message_at": conv.last_message_at,
                "unread_count": int(conv.unread_count_agent or "0"),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }
            result.append(ConversationResponse(**conv_dict))
        return result
    else:
        conversations = (
            db.query(Conversation)
            .filter(
                Conversation.tenant_id == tenant_id,
                Conversation.customer_keycloak_id == keycloak_id,
            )
            .order_by(desc(Conversation.last_message_at))
            .all()
        )

        result = []
        for conv in conversations:
            conv_dict = {
                "id": conv.id,
                "tenant_id": conv.tenant_id,
                "agent_keycloak_id": conv.agent_keycloak_id,
                "customer_keycloak_id": conv.customer_keycloak_id,
                "agent_name": conv.agent_name,
                "customer_name": conv.customer_name,
                "business_id": None,
                "business_name": None,
                "agent_language": conv.agent_language or "en",
                "customer_language": conv.customer_language or "en",
                "auto_translate": (
                    conv.auto_translate if conv.auto_translate is not None else True
                ),
                "last_message": conv.last_message,
                "last_message_at": conv.last_message_at,
                "unread_count": int(conv.unread_count_customer or "0"),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }
            result.append(ConversationResponse(**conv_dict))
        return result


@app.post("/conversations", response_model=ConversationResponse)
def create_or_get_conversation(
    tenant_id: str = Query(...),
    data: ConversationCreate = None,
    db: Session = Depends(get_db),
):
    """Create a new conversation or return existing one between agent and customer"""
    # Check if conversation already exists
    existing = (
        db.query(Conversation)
        .filter(
            Conversation.tenant_id == tenant_id,
            Conversation.agent_keycloak_id == data.agent_keycloak_id,
            Conversation.customer_keycloak_id == data.customer_keycloak_id,
        )
        .first()
    )

    if existing:
        return ConversationResponse(
            id=existing.id,
            tenant_id=existing.tenant_id,
            agent_keycloak_id=existing.agent_keycloak_id,
            customer_keycloak_id=existing.customer_keycloak_id,
            agent_name=existing.agent_name,
            customer_name=existing.customer_name,
            business_id=None,
            business_name=None,
            agent_language=existing.agent_language or "en",
            customer_language=existing.customer_language or "en",
            auto_translate=(
                existing.auto_translate if existing.auto_translate is not None else True
            ),
            last_message=existing.last_message,
            last_message_at=existing.last_message_at,
            unread_count=0,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )

    # Create new conversation
    conversation = Conversation(
        tenant_id=tenant_id,
        agent_keycloak_id=data.agent_keycloak_id,
        customer_keycloak_id=data.customer_keycloak_id,
        agent_name=data.agent_name,
        customer_name=data.customer_name,
        agent_language=data.agent_language,
        customer_language=data.customer_language,
        auto_translate=True,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationResponse(
        id=conversation.id,
        tenant_id=conversation.tenant_id,
        agent_keycloak_id=conversation.agent_keycloak_id,
        customer_keycloak_id=conversation.customer_keycloak_id,
        agent_name=conversation.agent_name,
        customer_name=conversation.customer_name,
        business_id=None,
        business_name=None,
        agent_language=conversation.agent_language,
        customer_language=conversation.customer_language,
        auto_translate=conversation.auto_translate,
        last_message=conversation.last_message,
        last_message_at=conversation.last_message_at,
        unread_count=0,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@app.get(
    "/conversations/{conversation_id}/messages", response_model=List[MessageResponse]
)
def get_conversation_messages(
    conversation_id: str,
    tenant_id: str = Query(...),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get messages in a conversation"""
    # Verify conversation belongs to tenant
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.tenant_id == tenant_id,
        )
        .order_by(Message.created_at)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return messages


@app.post("/messages", response_model=MessageResponse)
async def send_message(
    message_data: MessageCreate,
    tenant_id: str = Query(...),
    sender_keycloak_id: str = Query(...),
    sender_name: str = Query(...),
    sender_type: str = Query(..., pattern="^(agent|customer)$"),
    channel: str = Query(
        "web", description="Communication channel: web, mobile, whatsapp, etc."
    ),
    db: Session = Depends(get_db),
):
    """Send a message"""
    # Get or create conversation
    if message_data.conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == message_data.conversation_id,
                Conversation.tenant_id == tenant_id,
            )
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        if not message_data.customer_keycloak_id:
            raise HTTPException(
                status_code=400,
                detail="customer_keycloak_id required for new conversation",
            )

        if sender_type == "agent":
            # Agent initiating conversation - get customer name (placeholder for now)
            customer_name = f"Customer {message_data.customer_keycloak_id[:8]}"
            conversation = get_or_create_conversation(
                db,
                tenant_id,
                sender_keycloak_id,
                message_data.customer_keycloak_id,
                sender_name,
                customer_name,
            )
        else:
            # Customer initiating - shouldn't happen without agent first
            raise HTTPException(
                status_code=400, detail="Conversation must be initiated by agent"
            )

    # Determine source and target languages
    source_lang = (
        conversation.agent_language
        if sender_type == "agent"
        else conversation.customer_language
    )
    target_lang = (
        conversation.customer_language
        if sender_type == "agent"
        else conversation.agent_language
    )

    # Translate message if auto_translate is enabled and languages differ
    translated_content = None
    translation_engine = None

    if conversation.auto_translate and source_lang != target_lang:
        translation_result = await translate_text(
            message_data.content,
            source_lang,
            target_lang,
        )
        translated_content = translation_result.get("translated_text")
        translation_engine = translation_result.get("engine_used")

    # Create message
    message = Message(
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        sender_keycloak_id=sender_keycloak_id,
        sender_name=sender_name,
        sender_type=sender_type,
        channel=channel,
        content=message_data.content,
        content_translated=translated_content,
        source_language=source_lang,
        target_language=target_lang if translated_content else None,
        translation_engine=translation_engine,
        message_type=message_data.message_type,
        attachment_url=message_data.attachment_url,
    )
    db.add(message)

    # Update conversation
    conversation.last_message = message_data.content[:200]
    conversation.last_message_at = datetime.utcnow()

    # Increment unread count for recipient
    if sender_type == "agent":
        conversation.unread_count_customer = str(
            int(conversation.unread_count_customer or "0") + 1
        )
        recipient_id = conversation.customer_keycloak_id
    else:
        conversation.unread_count_agent = str(
            int(conversation.unread_count_agent or "0") + 1
        )
        recipient_id = conversation.agent_keycloak_id

    db.commit()
    db.refresh(message)

    # Send WebSocket notification
    await manager.send_personal_message(
        {
            "type": "new_message",
            "conversation_id": conversation.id,
            "message": {
                "id": message.id,
                "sender_name": message.sender_name,
                "sender_type": message.sender_type,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            },
        },
        recipient_id,
    )

    return message


@app.post("/conversations/{conversation_id}/mark-read")
def mark_conversation_read(
    conversation_id: str,
    tenant_id: str = Query(...),
    keycloak_id: str = Query(...),
    user_type: str = Query(..., pattern="^(agent|customer)$"),
    db: Session = Depends(get_db),
):
    """Mark all messages in conversation as read"""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Mark messages as read
    db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.sender_keycloak_id != keycloak_id,
        Message.is_read == False,
    ).update({"is_read": True, "read_at": datetime.utcnow()})

    # Reset unread count
    if user_type == "agent":
        conversation.unread_count_agent = "0"
    else:
        conversation.unread_count_customer = "0"

    db.commit()

    return {"message": "Marked as read"}


@app.put("/conversations/{conversation_id}/language-preference")
def update_conversation_language(
    conversation_id: str,
    preference: LanguagePreferenceUpdate,
    tenant_id: str = Query(...),
    keycloak_id: str = Query(...),
    user_type: str = Query(..., pattern="^(agent|customer)$"),
    db: Session = Depends(get_db),
):
    """Update language preference for a conversation"""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify user is part of the conversation
    if user_type == "agent" and conversation.agent_keycloak_id != keycloak_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if user_type == "customer" and conversation.customer_keycloak_id != keycloak_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update language preference
    if user_type == "agent":
        conversation.agent_language = preference.language
    else:
        conversation.customer_language = preference.language

    conversation.auto_translate = preference.auto_translate
    db.commit()

    return {
        "message": "Language preference updated",
        "agent_language": conversation.agent_language,
        "customer_language": conversation.customer_language,
        "auto_translate": conversation.auto_translate,
    }


@app.get("/supported-languages")
def get_supported_languages():
    """Get list of supported languages for translation"""
    return {
        "languages": {
            "en": {"name": "English", "native": "English"},
            "yo": {"name": "Yoruba", "native": "Yorùbá"},
            "ha": {"name": "Hausa", "native": "Hausa"},
            "ig": {"name": "Igbo", "native": "Igbo"},
            "pcm": {"name": "Nigerian Pidgin", "native": "Naijá"},
            "fr": {"name": "French", "native": "Français"},
            "ar": {"name": "Arabic", "native": "العربية"},
        }
    }


@app.get(
    "/conversations/by-business/{business_id}",
    response_model=List[ConversationResponse],
)
def get_conversations_by_business(
    business_id: str,
    tenant_id: str = Query(...),
    keycloak_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Get all conversations for a specific business
    
    Note: Business-based filtering is no longer supported in this version.
    Returns an empty list. Use /conversations endpoint instead.
    """
    return []


@app.get("/businesses/with-conversations")
def get_businesses_with_conversations(
    tenant_id: str = Query(...),
    keycloak_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Get all unique businesses that have conversations with the agent
    
    Note: Business-based grouping is no longer supported in this version.
    Returns an empty list.
    """
    return {"businesses": []}


@app.websocket("/ws/{keycloak_id}")
async def websocket_endpoint(websocket: WebSocket, keycloak_id: str):
    """WebSocket endpoint for real-time messages"""
    await manager.connect(websocket, keycloak_id)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, keycloak_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
