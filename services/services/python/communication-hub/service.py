"""
Integrated Communication Hub
Unified messaging across all channels:
- In-app chat (WebSocket-based)
- WhatsApp Business API (Meta Cloud API)
- Telegram Bot API
- SMS (USSD/SMS gateway)
- Push notifications (FCM/APNs)
- Email (SMTP/SendGrid)

Features:
- Unified inbox: all channels in one view
- Message routing: send via best available channel
- Delivery receipts and read confirmations
- Auto-reply templates for common banking queries
- Agent-to-customer messaging
- Broadcast messaging (bulk notifications)
- Conversation threading
- Message search and archiving
- Real-time translation integration
- Bot commands for self-service banking
"""

import os
import json
import httpx
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    Enum as SAEnum, Index, ForeignKey
)
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
import asyncio

logger = logging.getLogger(__name__)
Base = declarative_base()


class MessageChannel(str, Enum):
    IN_APP = "IN_APP"
    WHATSAPP = "WHATSAPP"
    TELEGRAM = "TELEGRAM"
    SMS = "SMS"
    PUSH = "PUSH"
    EMAIL = "EMAIL"


class MessageStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class ConversationType(str, Enum):
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    AGENT_CUSTOMER = "AGENT_CUSTOMER"
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"
    BROADCAST = "BROADCAST"
    BOT = "BOT"


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    participant_ids = Column(Text, nullable=False)       # JSON array
    conversation_type = Column(SAEnum(ConversationType), nullable=False)
    channel = Column(SAEnum(MessageChannel), default=MessageChannel.IN_APP)
    subject = Column(String(300), nullable=True)
    is_active = Column(Boolean, default=True)
    last_message_at = Column(DateTime, nullable=True)
    unread_count = Column(Integer, default=0)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="conversation", lazy="dynamic")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(String(100), nullable=False)
    sender_name = Column(String(200), nullable=True)
    recipient_id = Column(String(100), nullable=True)
    channel = Column(SAEnum(MessageChannel), nullable=False)
    direction = Column(SAEnum(MessageDirection), nullable=False)
    message_type = Column(String(50), default="TEXT")   # TEXT, IMAGE, DOCUMENT, AUDIO, TEMPLATE
    content = Column(Text, nullable=False)
    translated_content = Column(Text, nullable=True)
    original_language = Column(String(10), nullable=True)
    translated_language = Column(String(10), nullable=True)
    status = Column(SAEnum(MessageStatus), default=MessageStatus.PENDING)
    external_message_id = Column(String(200), nullable=True)  # WhatsApp/Telegram message ID
    media_url = Column(String(500), nullable=True)
    template_name = Column(String(100), nullable=True)
    template_params = Column(Text, nullable=True)       # JSON
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")
    __table_args__ = (
        Index("ix_message_conversation", "conversation_id"),
        Index("ix_message_sender", "sender_id"),
        Index("ix_message_created", "created_at"),
    )


class ChannelConfig(Base):
    __tablename__ = "channel_configs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id = Column(String(100), nullable=False, index=True)
    channel = Column(SAEnum(MessageChannel), nullable=False)
    phone_number = Column(String(30), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_username = Column(String(100), nullable=True)
    whatsapp_number = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    fcm_token = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sender_id = Column(String(100), nullable=False)
    channel = Column(SAEnum(MessageChannel), nullable=False)
    content = Column(Text, nullable=False)
    template_name = Column(String(100), nullable=True)
    recipient_filter = Column(Text, nullable=True)      # JSON filter criteria
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    status = Column(String(50), default="PENDING")
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    sender_id: str
    recipient_id: str
    channel: MessageChannel
    content: str
    message_type: str = "TEXT"
    media_url: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[Dict] = None
    conversation_id: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    channel: MessageChannel
    content: str
    status: MessageStatus
    created_at: datetime

    class Config:
        from_attributes = True


class WhatsAppWebhookPayload(BaseModel):
    """Meta WhatsApp Cloud API webhook payload."""
    object: str
    entry: List[Dict]


class TelegramUpdate(BaseModel):
    """Telegram Bot API update payload."""
    update_id: int
    message: Optional[Dict] = None
    callback_query: Optional[Dict] = None


class BroadcastRequest(BaseModel):
    sender_id: str
    channel: MessageChannel
    content: str
    template_name: Optional[str] = None
    recipient_ids: Optional[List[str]] = None
    recipient_filter: Optional[Dict] = None
    scheduled_at: Optional[datetime] = None


class ChannelConfigRequest(BaseModel):
    entity_id: str
    channel: MessageChannel
    phone_number: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    fcm_token: Optional[str] = None


# ─────────────────────────────────────────────
# WHATSAPP BUSINESS API CLIENT
# ─────────────────────────────────────────────

class WhatsAppClient:
    """Meta WhatsApp Cloud API client."""

    def __init__(self):
        self.token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"

    def send_text(self, to: str, text: str) -> Dict:
        """Send a plain text WhatsApp message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return self._post("/messages", payload)

    def send_template(self, to: str, template_name: str, language: str, components: List[Dict]) -> Dict:
        """Send a WhatsApp template message (for notifications)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components,
            },
        }
        return self._post("/messages", payload)

    def send_interactive_buttons(self, to: str, body_text: str, buttons: List[Dict]) -> Dict:
        """Send a WhatsApp interactive button message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": buttons},
            },
        }
        return self._post("/messages", payload)

    def mark_as_read(self, message_id: str) -> Dict:
        """Mark a received message as read."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return self._post("/messages", payload)

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        try:
            resp = httpx.post(
                f"{self.base_url}{endpoint}",
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"WhatsApp API error: {e}")
            return {"error": str(e)}


# ─────────────────────────────────────────────
# TELEGRAM BOT CLIENT
# ─────────────────────────────────────────────

class TelegramClient:
    """Telegram Bot API client."""

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML",
                     reply_markup: Optional[Dict] = None) -> Dict:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        return self._post("/sendMessage", payload)

    def send_inline_keyboard(self, chat_id: str, text: str, buttons: List[List[Dict]]) -> Dict:
        """Send a message with inline keyboard buttons."""
        return self.send_message(
            chat_id, text,
            reply_markup={"inline_keyboard": buttons}
        )

    def send_document(self, chat_id: str, document_url: str, caption: str = "") -> Dict:
        payload = {"chat_id": chat_id, "document": document_url, "caption": caption}
        return self._post("/sendDocument", payload)

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> Dict:
        return self._post("/answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

    def set_webhook(self, webhook_url: str) -> Dict:
        return self._post("/setWebhook", {"url": webhook_url})

    def _post(self, endpoint: str, payload: Dict) -> Dict:
        try:
            resp = httpx.post(f"{self.base_url}{endpoint}", json=payload, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return {"error": str(e)}


# ─────────────────────────────────────────────
# BANKING BOT COMMAND HANDLERS
# ─────────────────────────────────────────────

BANKING_COMMANDS = {
    "/balance": "Check your account balance",
    "/transfer": "Send money to another account",
    "/history": "View recent transactions",
    "/agents": "Find nearby agents",
    "/help": "Show available commands",
    "/language": "Change your preferred language",
    "/receipt": "Get your last transaction receipt",
    "/support": "Connect with customer support",
}

WHATSAPP_TEMPLATES = {
    "transaction_receipt": {
        "name": "transaction_receipt",
        "language": "en",
        "description": "Transaction receipt notification",
    },
    "otp_verification": {
        "name": "otp_verification",
        "language": "en",
        "description": "OTP verification code",
    },
    "account_alert": {
        "name": "account_alert",
        "language": "en",
        "description": "Account activity alert",
    },
    "agent_onboarding": {
        "name": "agent_onboarding",
        "language": "en",
        "description": "Agent onboarding welcome message",
    },
}


# ─────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────

class CommunicationHubService:

    def __init__(self, db: Session):
        self.db = db
        self.whatsapp = WhatsAppClient()
        self.telegram = TelegramClient()

    def _get_or_create_conversation(self, sender_id: str, recipient_id: str,
                                     channel: MessageChannel,
                                     conv_type: ConversationType) -> Conversation:
        """Get existing conversation or create a new one."""
        participants = json.dumps(sorted([sender_id, recipient_id]))
        existing = (
            self.db.query(Conversation)
            .filter(
                Conversation.participant_ids == participants,
                Conversation.channel == channel,
                Conversation.is_active == True,
            )
            .first()
        )
        if existing:
            return existing

        conv = Conversation(
            participant_ids=participants,
            conversation_type=conv_type,
            channel=channel,
        )
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def send_message(self, req: SendMessageRequest) -> Message:
        """Send a message via the specified channel."""
        # Get or create conversation
        if req.conversation_id:
            conv = self.db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        else:
            conv = self._get_or_create_conversation(
                req.sender_id, req.recipient_id, req.channel, ConversationType.AGENT_CUSTOMER
            )

        # Create message record
        msg = Message(
            conversation_id=conv.id,
            sender_id=req.sender_id,
            recipient_id=req.recipient_id,
            channel=req.channel,
            direction=MessageDirection.OUTBOUND,
            message_type=req.message_type,
            content=req.content,
            media_url=req.media_url,
            template_name=req.template_name,
            template_params=json.dumps(req.template_params) if req.template_params else None,
            status=MessageStatus.PENDING,
        )
        self.db.add(msg)

        # Update conversation
        conv.last_message_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(msg)

        # Dispatch to channel
        try:
            if req.channel == MessageChannel.WHATSAPP:
                self._dispatch_whatsapp(msg, req)
            elif req.channel == MessageChannel.TELEGRAM:
                self._dispatch_telegram(msg, req)
            elif req.channel == MessageChannel.IN_APP:
                msg.status = MessageStatus.SENT
            # SMS and Push handled by separate microservices
            self.db.commit()
        except Exception as e:
            logger.error(f"Message dispatch failed: {e}")
            msg.status = MessageStatus.FAILED
            self.db.commit()

        return msg

    def _dispatch_whatsapp(self, msg: Message, req: SendMessageRequest):
        """Dispatch a message via WhatsApp Business API."""
        # Get recipient's WhatsApp number
        config = (
            self.db.query(ChannelConfig)
            .filter(
                ChannelConfig.entity_id == req.recipient_id,
                ChannelConfig.channel == MessageChannel.WHATSAPP,
            )
            .first()
        )
        if not config or not config.whatsapp_number:
            raise ValueError(f"No WhatsApp number for {req.recipient_id}")

        if req.template_name:
            result = self.whatsapp.send_template(
                config.whatsapp_number,
                req.template_name,
                "en",
                req.template_params.get("components", []) if req.template_params else [],
            )
        else:
            result = self.whatsapp.send_text(config.whatsapp_number, req.content)

        if "messages" in result:
            msg.external_message_id = result["messages"][0].get("id")
            msg.status = MessageStatus.SENT
        else:
            msg.status = MessageStatus.FAILED

    def _dispatch_telegram(self, msg: Message, req: SendMessageRequest):
        """Dispatch a message via Telegram Bot API."""
        config = (
            self.db.query(ChannelConfig)
            .filter(
                ChannelConfig.entity_id == req.recipient_id,
                ChannelConfig.channel == MessageChannel.TELEGRAM,
            )
            .first()
        )
        if not config or not config.telegram_chat_id:
            raise ValueError(f"No Telegram chat ID for {req.recipient_id}")

        result = self.telegram.send_message(config.telegram_chat_id, req.content)
        if result.get("ok"):
            msg.external_message_id = str(result.get("result", {}).get("message_id", ""))
            msg.status = MessageStatus.SENT
        else:
            msg.status = MessageStatus.FAILED

    def handle_whatsapp_webhook(self, payload: Dict) -> List[Message]:
        """Process incoming WhatsApp webhook events."""
        messages = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for wa_msg in value.get("messages", []):
                    msg = self._process_inbound_whatsapp(wa_msg, value)
                    if msg:
                        messages.append(msg)
                # Process delivery/read receipts
                for status in value.get("statuses", []):
                    self._process_whatsapp_status(status)
        return messages

    def _process_inbound_whatsapp(self, wa_msg: Dict, value: Dict) -> Optional[Message]:
        """Process a single inbound WhatsApp message."""
        from_number = wa_msg.get("from", "")
        wa_message_id = wa_msg.get("id", "")
        msg_type = wa_msg.get("type", "text")

        # Find entity by WhatsApp number
        config = (
            self.db.query(ChannelConfig)
            .filter(
                ChannelConfig.whatsapp_number == from_number,
                ChannelConfig.channel == MessageChannel.WHATSAPP,
            )
            .first()
        )
        sender_id = config.entity_id if config else f"wa_{from_number}"

        content = ""
        if msg_type == "text":
            content = wa_msg.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = wa_msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                content = interactive.get("button_reply", {}).get("title", "")
        elif msg_type == "image":
            content = "[Image received]"
        elif msg_type == "document":
            content = f"[Document: {wa_msg.get('document', {}).get('filename', 'unknown')}]"

        # Get system conversation
        system_id = os.environ.get("SYSTEM_USER_ID", "system")
        conv = self._get_or_create_conversation(
            sender_id, system_id, MessageChannel.WHATSAPP, ConversationType.BOT
        )

        msg = Message(
            conversation_id=conv.id,
            sender_id=sender_id,
            channel=MessageChannel.WHATSAPP,
            direction=MessageDirection.INBOUND,
            content=content,
            external_message_id=wa_message_id,
            status=MessageStatus.DELIVERED,
            delivered_at=datetime.utcnow(),
        )
        self.db.add(msg)
        conv.last_message_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(msg)

        # Mark as read
        if wa_message_id:
            self.whatsapp.mark_as_read(wa_message_id)

        # Handle bot commands
        self._handle_bot_command(content, sender_id, MessageChannel.WHATSAPP, config)

        return msg

    def _process_whatsapp_status(self, status: Dict):
        """Update message status from WhatsApp delivery receipt."""
        external_id = status.get("id", "")
        wa_status = status.get("status", "")
        msg = (
            self.db.query(Message)
            .filter(Message.external_message_id == external_id)
            .first()
        )
        if msg:
            if wa_status == "delivered":
                msg.status = MessageStatus.DELIVERED
                msg.delivered_at = datetime.utcnow()
            elif wa_status == "read":
                msg.status = MessageStatus.READ
                msg.read_at = datetime.utcnow()
            self.db.commit()

    def handle_telegram_update(self, update: Dict) -> Optional[Message]:
        """Process incoming Telegram Bot update."""
        tg_message = update.get("message", {})
        if not tg_message:
            return None

        chat_id = str(tg_message.get("chat", {}).get("id", ""))
        text = tg_message.get("text", "")
        tg_message_id = str(tg_message.get("message_id", ""))
        from_user = tg_message.get("from", {})

        config = (
            self.db.query(ChannelConfig)
            .filter(
                ChannelConfig.telegram_chat_id == chat_id,
                ChannelConfig.channel == MessageChannel.TELEGRAM,
            )
            .first()
        )
        sender_id = config.entity_id if config else f"tg_{chat_id}"

        system_id = os.environ.get("SYSTEM_USER_ID", "system")
        conv = self._get_or_create_conversation(
            sender_id, system_id, MessageChannel.TELEGRAM, ConversationType.BOT
        )

        msg = Message(
            conversation_id=conv.id,
            sender_id=sender_id,
            sender_name=f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
            channel=MessageChannel.TELEGRAM,
            direction=MessageDirection.INBOUND,
            content=text,
            external_message_id=tg_message_id,
            status=MessageStatus.DELIVERED,
            delivered_at=datetime.utcnow(),
        )
        self.db.add(msg)
        conv.last_message_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(msg)

        # Handle bot commands
        self._handle_bot_command(text, sender_id, MessageChannel.TELEGRAM, config, chat_id=chat_id)

        return msg

    def _handle_bot_command(self, text: str, sender_id: str, channel: MessageChannel,
                             config: Optional[ChannelConfig], chat_id: Optional[str] = None):
        """Handle banking bot commands from WhatsApp or Telegram."""
        if not text or not text.startswith("/"):
            return

        command = text.split()[0].lower()
        response_text = None

        if command == "/help":
            response_text = "Available commands:\n" + "\n".join(
                f"{cmd} - {desc}" for cmd, desc in BANKING_COMMANDS.items()
            )
        elif command == "/balance":
            response_text = "To check your balance, please log in to the 54link app or visit your nearest agent."
        elif command == "/agents":
            response_text = "Find your nearest agent at: https://54link.ng/agents"
        elif command == "/support":
            response_text = "Connecting you to a support agent. Please wait..."

        if response_text and config:
            if channel == MessageChannel.WHATSAPP and config.whatsapp_number:
                self.whatsapp.send_text(config.whatsapp_number, response_text)
            elif channel == MessageChannel.TELEGRAM and chat_id:
                self.telegram.send_message(chat_id, response_text)

    def register_channel(self, req: ChannelConfigRequest) -> ChannelConfig:
        """Register a user's channel contact details."""
        existing = (
            self.db.query(ChannelConfig)
            .filter(ChannelConfig.entity_id == req.entity_id, ChannelConfig.channel == req.channel)
            .first()
        )
        if existing:
            for field, value in req.dict(exclude_unset=True).items():
                setattr(existing, field, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        config = ChannelConfig(**req.dict())
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_conversations(self, user_id: str, limit: int = 20) -> List[Conversation]:
        """Get all conversations for a user."""
        return (
            self.db.query(Conversation)
            .filter(Conversation.participant_ids.contains(user_id))
            .order_by(Conversation.last_message_at.desc())
            .limit(limit)
            .all()
        )

    def get_messages(self, conversation_id: str, limit: int = 50, offset: int = 0) -> List[Message]:
        """Get messages in a conversation."""
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def send_broadcast(self, req: BroadcastRequest) -> BroadcastMessage:
        """Send a broadcast message to multiple recipients."""
        broadcast = BroadcastMessage(
            sender_id=req.sender_id,
            channel=req.channel,
            content=req.content,
            template_name=req.template_name,
            recipient_filter=json.dumps(req.recipient_filter) if req.recipient_filter else None,
            total_recipients=len(req.recipient_ids) if req.recipient_ids else 0,
            scheduled_at=req.scheduled_at,
            status="PROCESSING" if not req.scheduled_at else "SCHEDULED",
        )
        self.db.add(broadcast)
        self.db.commit()

        if req.recipient_ids and not req.scheduled_at:
            for recipient_id in req.recipient_ids:
                try:
                    self.send_message(SendMessageRequest(
                        sender_id=req.sender_id,
                        recipient_id=recipient_id,
                        channel=req.channel,
                        content=req.content,
                        template_name=req.template_name,
                    ))
                    broadcast.sent_count += 1
                except Exception:
                    broadcast.failed_count += 1
            broadcast.status = "COMPLETED"
            broadcast.completed_at = datetime.utcnow()
            self.db.commit()

        self.db.refresh(broadcast)
        return broadcast

    def mark_messages_read(self, conversation_id: str, user_id: str):
        """Mark all messages in a conversation as read for a user."""
        (
            self.db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.recipient_id == user_id,
                Message.status != MessageStatus.READ,
            )
            .update({"status": MessageStatus.READ, "read_at": datetime.utcnow()})
        )
        self.db.commit()
