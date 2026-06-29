"""Integrated Communication Hub — API Router"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from sqlalchemy.orm import Session
from .service import (
    CommunicationHubService, SendMessageRequest, MessageResponse,
    BroadcastRequest, ChannelConfigRequest, MessageChannel,
    BANKING_COMMANDS, WHATSAPP_TEMPLATES
)
from .config import get_db
import os

router = APIRouter(prefix="/comms", tags=["Communication Hub"])


def get_svc(db: Session = Depends(get_db)) -> CommunicationHubService:
    return CommunicationHubService(db)


# ─── Messaging ───────────────────────────────

@router.post("/messages/send", response_model=MessageResponse)
def send_message(payload: SendMessageRequest, svc: CommunicationHubService = Depends(get_svc)):
    """Send a message via any supported channel (in-app, WhatsApp, Telegram, SMS)."""
    return svc.send_message(payload)


@router.get("/conversations/{user_id}")
def get_conversations(user_id: str, limit: int = Query(20, ge=1, le=100), svc: CommunicationHubService = Depends(get_svc)):
    """Get all conversations for a user across all channels."""
    convs = svc.get_conversations(user_id, limit)
    return [
        {
            "id": c.id,
            "participant_ids": c.participant_ids,
            "channel": c.channel.value,
            "conversation_type": c.conversation_type.value,
            "last_message_at": str(c.last_message_at) if c.last_message_at else None,
            "unread_count": c.unread_count,
            "is_active": c.is_active,
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: CommunicationHubService = Depends(get_svc)
):
    """Get messages in a conversation."""
    msgs = svc.get_messages(conversation_id, limit, offset)
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "channel": m.channel.value,
            "direction": m.direction.value,
            "content": m.content,
            "translated_content": m.translated_content,
            "status": m.status.value,
            "created_at": str(m.created_at),
            "delivered_at": str(m.delivered_at) if m.delivered_at else None,
            "read_at": str(m.read_at) if m.read_at else None,
        }
        for m in msgs
    ]


@router.post("/conversations/{conversation_id}/read")
def mark_read(conversation_id: str, user_id: str = Query(...), svc: CommunicationHubService = Depends(get_svc)):
    """Mark all messages in a conversation as read."""
    svc.mark_messages_read(conversation_id, user_id)
    return {"marked_read": True}


# ─── WhatsApp Webhook ─────────────────────────

@router.get("/webhooks/whatsapp")
def whatsapp_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification endpoint (Meta requirement)."""
    expected_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "54agent_whatsapp_verify")
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, svc: CommunicationHubService = Depends(get_svc)):
    """Receive and process incoming WhatsApp messages and status updates."""
    payload = await request.json()
    messages = svc.handle_whatsapp_webhook(payload)
    return {"processed": len(messages)}


# ─── Telegram Webhook ─────────────────────────

@router.post("/webhooks/telegram")
async def telegram_webhook(request: Request, svc: CommunicationHubService = Depends(get_svc)):
    """Receive and process incoming Telegram Bot updates."""
    update = await request.json()
    msg = svc.handle_telegram_update(update)
    return {"processed": msg is not None}


@router.post("/telegram/set-webhook")
def set_telegram_webhook(webhook_url: str = Query(...), svc: CommunicationHubService = Depends(get_svc)):
    """Register the Telegram webhook URL with the Bot API."""
    result = svc.telegram.set_webhook(webhook_url)
    return result


# ─── Broadcast ───────────────────────────────

@router.post("/broadcast")
def send_broadcast(payload: BroadcastRequest, svc: CommunicationHubService = Depends(get_svc)):
    """Send a broadcast message to multiple recipients."""
    broadcast = svc.send_broadcast(payload)
    return {
        "id": broadcast.id,
        "status": broadcast.status,
        "total_recipients": broadcast.total_recipients,
        "sent_count": broadcast.sent_count,
        "failed_count": broadcast.failed_count,
        "scheduled_at": str(broadcast.scheduled_at) if broadcast.scheduled_at else None,
    }


# ─── Channel Configuration ────────────────────

@router.post("/channels/register")
def register_channel(payload: ChannelConfigRequest, svc: CommunicationHubService = Depends(get_svc)):
    """Register a user's channel contact details (WhatsApp number, Telegram chat ID, etc.)."""
    config = svc.register_channel(payload)
    return {
        "entity_id": config.entity_id,
        "channel": config.channel.value,
        "is_active": config.is_active,
        "whatsapp_number": config.whatsapp_number,
        "telegram_chat_id": config.telegram_chat_id,
    }


# ─── Reference Data ───────────────────────────

@router.get("/bot/commands")
def get_bot_commands():
    """List all available banking bot commands."""
    return {"commands": BANKING_COMMANDS}


@router.get("/whatsapp/templates")
def get_whatsapp_templates():
    """List all available WhatsApp message templates."""
    return {"templates": WHATSAPP_TEMPLATES}


@router.get("/health")
def health():
    return {"status": "ok", "service": "communication-hub"}
