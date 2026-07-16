import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Unified Communication Hub
Central orchestration layer for all communication channels
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("unified-communication-hub")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import httpx
import asyncio
import os

app = FastAPI(title="Unified Communication Hub", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Channel Configuration
class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    USSD = "ussd"
    TELEGRAM = "telegram"
    EMAIL = "email"
    DISCORD = "discord"
    VOICE_AI = "voice_ai"
    MESSENGER = "messenger"
    INSTAGRAM = "instagram"
    RCS = "rcs"
    TIKTOK = "tiktok"
    VOICE_ASSISTANT = "voice_assistant"
    TWITTER = "twitter"
    SNAPCHAT = "snapchat"
    WECHAT = "wechat"
    JUMIA = "jumia"
    KONGA = "konga"
    AMAZON = "amazon"
    EBAY = "ebay"
    METAVERSE = "metaverse"
    GAMING = "gaming"

CHANNEL_SERVICES = {
    Channel.WHATSAPP: "http://localhost:8040",
    Channel.SMS: "http://localhost:8001",
    Channel.USSD: "http://localhost:8002",
    Channel.TELEGRAM: "http://localhost:8041",
    Channel.EMAIL: "http://localhost:8042",
    Channel.DISCORD: "http://localhost:8044",
    Channel.VOICE_AI: "http://localhost:8045",
    Channel.MESSENGER: "http://localhost:8047",
    Channel.INSTAGRAM: "http://localhost:8048",
    Channel.RCS: "http://localhost:8049",
    Channel.TIKTOK: "http://localhost:8050",
    Channel.VOICE_ASSISTANT: "http://localhost:8051",
    Channel.TWITTER: "http://localhost:8052",
    Channel.SNAPCHAT: "http://localhost:8053",
    Channel.WECHAT: "http://localhost:8055",
    Channel.JUMIA: "http://localhost:8046",
    Channel.KONGA: "http://localhost:8046",
    Channel.AMAZON: "http://localhost:8054",
    Channel.EBAY: "http://localhost:8054",
    Channel.METAVERSE: "http://localhost:8056",
    Channel.GAMING: "http://localhost:8057"
}

# Models
class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class MessageType(str, Enum):
    ORDER_CONFIRMATION = "order_confirmation"
    SHIPPING_UPDATE = "shipping_update"
    DELIVERY_CONFIRMATION = "delivery_confirmation"
    PAYMENT_REQUEST = "payment_request"
    PROMOTIONAL = "promotional"
    NOTIFICATION = "notification"
    SUPPORT = "support"

class Message(BaseModel):
    recipient_id: str
    recipient_name: Optional[str] = None
    message_type: MessageType
    content: str
    data: Optional[Dict[str, Any]] = None
    priority: MessagePriority = MessagePriority.NORMAL

class MultiChannelMessage(BaseModel):
    message: Message
    channels: List[Channel]
    fallback_enabled: bool = True
    retry_failed: bool = True

class ChannelPreference(BaseModel):
    customer_id: str
    preferred_channels: List[Channel]
    blocked_channels: Optional[List[Channel]] = []

# Storage
channel_stats: Dict[Channel, Dict] = {channel: {"sent": 0, "failed": 0, "delivered": 0} for channel in Channel}
customer_preferences: Dict[str, ChannelPreference] = {}
message_history: List[Dict] = []

# Helper Functions
async def send_to_channel(channel: Channel, message: Message) -> Dict:
    """Send message to specific channel"""
    try:
        service_url = CHANNEL_SERVICES.get(channel)
        if not service_url:
            return {"success": False, "error": "Channel not configured"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Different channels have different endpoints
            if channel == Channel.EMAIL:
                response = await client.post(
                    f"{service_url}/send",
                    json={
                        "to": [{"email": message.recipient_id, "name": message.recipient_name}],
                        "subject": f"{message.message_type.value.replace('_', ' ').title()}",
                        "template": message.message_type.value,
                        "data": message.data or {}
                    }
                )
            elif channel in [Channel.WHATSAPP, Channel.TELEGRAM, Channel.DISCORD]:
                response = await client.post(
                    f"{service_url}/send-notification/{message.recipient_id}",
                    json={"message": message.content}
                )
            elif channel == Channel.SMS:
                response = await client.post(
                    f"{service_url}/send",
                    json={
                        "to": message.recipient_id,
                        "message": message.content
                    }
                )
            else:
                # Generic endpoint for other channels
                response = await client.post(
                    f"{service_url}/send",
                    json=message.dict()
                )
            
            if response.status_code in [200, 201]:
                channel_stats[channel]["sent"] += 1
                channel_stats[channel]["delivered"] += 1
                return {"success": True, "channel": channel.value, "response": response.json()}
            else:
                channel_stats[channel]["failed"] += 1
                return {"success": False, "channel": channel.value, "error": response.text}
    
    except Exception as e:
        channel_stats[channel]["failed"] += 1
        return {"success": False, "channel": channel.value, "error": str(e)}

async def send_with_fallback(message: Message, channels: List[Channel]) -> Dict:
    """Send message with automatic fallback to next channel if one fails"""
    results = []
    
    for channel in channels:
        result = await send_to_channel(channel, message)
        results.append(result)
        
        if result["success"]:
            return {
                "success": True,
                "channel_used": channel.value,
                "attempts": len(results),
                "results": results
            }
    
    return {
        "success": False,
        "message": "All channels failed",
        "attempts": len(results),
        "results": results
    }

def get_customer_preferred_channels(customer_id: str) -> List[Channel]:
    """Get customer's preferred communication channels"""
    if customer_id in customer_preferences:
        return customer_preferences[customer_id].preferred_channels
    
    # Default preferences based on message type
    return [Channel.WHATSAPP, Channel.SMS, Channel.EMAIL]

def select_optimal_channel(message: Message, available_channels: List[Channel]) -> List[Channel]:
    """Intelligently select best channels based on message type and priority"""
    
    # Priority-based channel selection
    if message.priority == MessagePriority.URGENT:
        # For urgent messages, use instant channels
        priority_channels = [Channel.WHATSAPP, Channel.SMS, Channel.VOICE_AI, Channel.TELEGRAM]
    elif message.priority == MessagePriority.HIGH:
        priority_channels = [Channel.WHATSAPP, Channel.TELEGRAM, Channel.SMS, Channel.MESSENGER]
    else:
        priority_channels = available_channels
    
    # Message type specific channels
    type_preferences = {
        MessageType.ORDER_CONFIRMATION: [Channel.WHATSAPP, Channel.EMAIL, Channel.TELEGRAM],
        MessageType.SHIPPING_UPDATE: [Channel.WHATSAPP, Channel.SMS, Channel.TELEGRAM],
        MessageType.PAYMENT_REQUEST: [Channel.WHATSAPP, Channel.SMS, Channel.EMAIL],
        MessageType.PROMOTIONAL: [Channel.EMAIL, Channel.WHATSAPP, Channel.TELEGRAM, Channel.INSTAGRAM],
        MessageType.SUPPORT: [Channel.WHATSAPP, Channel.TELEGRAM, Channel.MESSENGER]
    }
    
    preferred = type_preferences.get(message.message_type, available_channels)
    
    # Combine and deduplicate
    combined = []
    for channel in priority_channels + preferred:
        if channel in available_channels and channel not in combined:
            combined.append(channel)
    
    return combined[:3]  # Top 3 channels

# API Endpoints

@app.get("/")
async def root():
    return {
        "service": "Unified Communication Hub",
        "version": "2.0.0",
        "channels": len(Channel),
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/send")
async def send_message(multi_msg: MultiChannelMessage, background_tasks: BackgroundTasks):
    """Send message through specified channels with fallback"""
    
    # Get customer preferences
    customer_channels = get_customer_preferred_channels(multi_msg.message.recipient_id)
    
    # Merge with requested channels
    final_channels = multi_msg.channels if multi_msg.channels else customer_channels
    
    # Select optimal channels
    optimal_channels = select_optimal_channel(multi_msg.message, final_channels)
    
    if multi_msg.fallback_enabled:
        result = await send_with_fallback(multi_msg.message, optimal_channels)
    else:
        # Send to all channels in parallel
        tasks = [send_to_channel(channel, multi_msg.message) for channel in optimal_channels]
        results = await asyncio.gather(*tasks)
        result = {
            "success": any(r["success"] for r in results),
            "channels_used": [r["channel"] for r in results if r["success"]],
            "results": results
        }
    
    # Log message
    message_history.append({
        "timestamp": datetime.now().isoformat(),
        "recipient": multi_msg.message.recipient_id,
        "type": multi_msg.message.message_type.value,
        "channels": [c.value for c in optimal_channels],
        "result": result
    })
    
    return result

@app.post("/send/order-confirmation")
async def send_order_confirmation(
    order_id: str,
    customer_id: str,
    customer_name: str,
    items: List[Dict],
    total: float,
    channels: Optional[List[Channel]] = None
):
    """Send order confirmation through optimal channels"""
    
    message = Message(
        recipient_id=customer_id,
        recipient_name=customer_name,
        message_type=MessageType.ORDER_CONFIRMATION,
        content=f"Order #{order_id} confirmed! Total: ₦{total:,.2f}",
        data={
            "order_id": order_id,
            "customer_name": customer_name,
            "items": items,
            "total": total
        },
        priority=MessagePriority.HIGH
    )
    
    multi_msg = MultiChannelMessage(
        message=message,
        channels=channels or [],
        fallback_enabled=True
    )
    
    return await send_message(multi_msg, BackgroundTasks())

@app.post("/send/shipping-update")
async def send_shipping_update(
    order_id: str,
    customer_id: str,
    customer_name: str,
    tracking_number: str,
    channels: Optional[List[Channel]] = None
):
    """Send shipping update through optimal channels"""
    
    message = Message(
        recipient_id=customer_id,
        recipient_name=customer_name,
        message_type=MessageType.SHIPPING_UPDATE,
        content=f"Your order #{order_id} has shipped! Tracking: {tracking_number}",
        data={
            "order_id": order_id,
            "tracking_number": tracking_number
        },
        priority=MessagePriority.NORMAL
    )
    
    multi_msg = MultiChannelMessage(
        message=message,
        channels=channels or [],
        fallback_enabled=True
    )
    
    return await send_message(multi_msg, BackgroundTasks())

@app.post("/preferences")
async def set_customer_preferences(preference: ChannelPreference):
    """Set customer's channel preferences"""
    customer_preferences[preference.customer_id] = preference
    return {"status": "updated", "customer_id": preference.customer_id}

@app.get("/preferences/{customer_id}")
async def get_preferences(customer_id: str):
    """Get customer's channel preferences"""
    if customer_id in customer_preferences:
        return customer_preferences[customer_id]
    return {"preferred_channels": [Channel.WHATSAPP, Channel.SMS, Channel.EMAIL]}

@app.get("/stats")
async def get_stats():
    """Get communication statistics across all channels"""
    total_sent = sum(stats["sent"] for stats in channel_stats.values())
    total_failed = sum(stats["failed"] for stats in channel_stats.values())
    total_delivered = sum(stats["delivered"] for stats in channel_stats.values())
    
    return {
        "total_messages": total_sent,
        "total_delivered": total_delivered,
        "total_failed": total_failed,
        "delivery_rate": (total_delivered / total_sent * 100) if total_sent > 0 else 0,
        "by_channel": {channel.value: stats for channel, stats in channel_stats.items()},
        "message_history_count": len(message_history)
    }

@app.get("/stats/{channel}")
async def get_channel_stats(channel: Channel):
    """Get statistics for specific channel"""
    return {
        "channel": channel.value,
        "stats": channel_stats[channel]
    }

@app.get("/channels")
async def list_channels():
    """List all available channels"""
    return {
        "channels": [
            {
                "name": channel.value,
                "service_url": CHANNEL_SERVICES.get(channel),
                "stats": channel_stats[channel]
            }
            for channel in Channel
        ],
        "total": len(Channel)
    }

@app.get("/channels/health")
async def check_channels_health():
    """Check health status of all channel services"""
    health_status = {}
    
    async def check_service(channel: Channel, url: str):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/health")
                return channel.value, response.status_code == 200
        except:
            return channel.value, False
    
    tasks = [check_service(channel, url) for channel, url in CHANNEL_SERVICES.items()]
    results = await asyncio.gather(*tasks)
    
    for channel_name, is_healthy in results:
        health_status[channel_name] = "healthy" if is_healthy else "unhealthy"
    
    healthy_count = sum(1 for status in health_status.values() if status == "healthy")
    
    return {
        "overall_health": f"{healthy_count}/{len(Channel)} channels healthy",
        "channels": health_status
    }

@app.get("/history")
async def get_message_history(limit: int = 50):
    """Get recent message history"""
    return {
        "messages": message_history[-limit:],
        "total": len(message_history)
    }

@app.post("/broadcast")
async def broadcast_message(
    message: Message,
    target_channels: List[Channel],
    background_tasks: BackgroundTasks
):
    """Broadcast message to multiple channels simultaneously"""
    
    tasks = [send_to_channel(channel, message) for channel in target_channels]
    results = await asyncio.gather(*tasks)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    return {
        "success": len(successful) > 0,
        "successful_channels": len(successful),
        "failed_channels": len(failed),
        "results": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)

