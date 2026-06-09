"""
Unified Communication Service for Remittance Platform
Supports WhatsApp, SMS, and USSD with automatic failover and delivery tracking
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import httpx
import asyncio
import logging
from collections import defaultdict
import json
import os
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Unified Communication Service",
    description="Multi-channel communication with WhatsApp, SMS, and USSD",
    version="2.0.0"
)

# ============================================================================
# ENUMS & MODELS
# ============================================================================

class CommunicationChannel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    USSD = "ussd"
    EMAIL = "email"

class MessagePriority(str, Enum):
    CRITICAL = "critical"  # Send immediately, all channels
    HIGH = "high"          # Send within 1 minute
    MEDIUM = "medium"      # Send within 5 minutes
    LOW = "low"            # Can batch and send later

class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RETRY = "retry"

class Provider(str, Enum):
    AFRICAS_TALKING = "africas_talking"
    TWILIO = "twilio"
    META_WHATSAPP = "meta_whatsapp"
    AWS_SNS = "aws_sns"
    HUBTEL = "hubtel"

class MessageRequest(BaseModel):
    recipient_phone: str
    message: str
    preferred_channels: List[CommunicationChannel] = [CommunicationChannel.WHATSAPP, CommunicationChannel.SMS]
    priority: MessagePriority = MessagePriority.MEDIUM
    metadata: Dict[str, Any] = {}
    template_name: Optional[str] = None
    template_params: Dict[str, Any] = {}

class MessageResponse(BaseModel):
    message_id: str
    status: DeliveryStatus
    channel_used: CommunicationChannel
    provider_used: Provider
    cost: float
    delivery_time: Optional[datetime] = None

class DeliveryReport(BaseModel):
    message_id: str
    status: DeliveryStatus
    channel: CommunicationChannel
    provider: Provider
    attempts: int
    last_attempt: datetime
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None

# ============================================================================
# PROVIDER CONFIGURATIONS
# ============================================================================

class ProviderConfig:
    """Configuration for communication providers"""
    
    AFRICAS_TALKING = {
        "api_key": os.getenv("AT_API_KEY", ""),
        "username": os.getenv("AT_USERNAME", "sandbox"),
        "sms_url": "https://api.africastalking.com/version1/messaging",
        "ussd_url": "https://api.africastalking.com/ussd",
        "whatsapp_url": "https://api.africastalking.com/whatsapp",
        "supported_channels": [CommunicationChannel.SMS, CommunicationChannel.USSD, CommunicationChannel.WHATSAPP],
        "cost_per_sms": 0.006,  # USD
        "cost_per_ussd": 0.008,
        "cost_per_whatsapp": 0.005,
        "priority": 1  # Highest priority for Africa
    }
    
    TWILIO = {
        "account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
        "auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
        "phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
        "whatsapp_number": os.getenv("TWILIO_WHATSAPP_NUMBER", ""),
        "sms_url": "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        "whatsapp_url": "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        "supported_channels": [CommunicationChannel.SMS, CommunicationChannel.WHATSAPP],
        "cost_per_sms": 0.02,
        "cost_per_whatsapp": 0.005,
        "priority": 2  # Secondary provider
    }
    
    META_WHATSAPP = {
        "access_token": os.getenv("META_WHATSAPP_TOKEN", ""),
        "phone_id": os.getenv("META_WHATSAPP_PHONE_ID", ""),
        "api_url": "https://graph.facebook.com/v18.0/{phone_id}/messages",
        "supported_channels": [CommunicationChannel.WHATSAPP],
        "cost_per_whatsapp": 0.005,
        "priority": 1  # Highest priority for WhatsApp
    }
    
    AWS_SNS = {
        "access_key": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "supported_channels": [CommunicationChannel.SMS],
        "cost_per_sms": 0.01,
        "priority": 3  # Tertiary provider
    }

# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """Circuit breaker pattern for provider failover"""
    
    def __init__(self, failure_threshold=5, timeout=300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = defaultdict(int)
        self.last_failure_time = {}
        self.state = defaultdict(lambda: "closed")  # closed, open, half-open
    
    def record_success(self, provider: str):
        """Record successful request"""
        self.failures[provider] = 0
        self.state[provider] = "closed"
    
    def record_failure(self, provider: str):
        """Record failed request"""
        self.failures[provider] += 1
        self.last_failure_time[provider] = datetime.now()
        
        if self.failures[provider] >= self.failure_threshold:
            self.state[provider] = "open"
            logger.warning(f"Circuit breaker OPEN for {provider}")
    
    def can_attempt(self, provider: str) -> bool:
        """Check if we can attempt to use this provider"""
        if self.state[provider] == "closed":
            return True
        
        if self.state[provider] == "open":
            # Check if timeout has passed
            if provider in self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time[provider]).seconds
                if time_since_failure >= self.timeout:
                    self.state[provider] = "half-open"
                    logger.info(f"Circuit breaker HALF-OPEN for {provider}")
                    return True
            return False
        
        # half-open state
        return True

# ============================================================================
# PROVIDER IMPLEMENTATIONS
# ============================================================================

class AfricasTalkingProvider:
    """Africa's Talking provider implementation"""
    
    def __init__(self):
        self.config = ProviderConfig.AFRICAS_TALKING
        self.api_key = self.config["api_key"]
        self.username = self.config["username"]
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """Send SMS via Africa's Talking"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["sms_url"],
                    headers={
                        "apiKey": self.api_key,
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "username": self.username,
                        "to": phone,
                        "message": message
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "success": True,
                        "message_id": data["SMSMessageData"]["Recipients"][0]["messageId"],
                        "cost": self.config["cost_per_sms"]
                    }
                else:
                    raise Exception(f"SMS failed: {response.text}")
        
        except Exception as e:
            logger.error(f"Africa's Talking SMS error: {e}")
            raise
    
    async def send_whatsapp(self, phone: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp via Africa's Talking"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["whatsapp_url"],
                    headers={
                        "apiKey": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "username": self.username,
                        "to": phone,
                        "message": message
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message_id": data.get("messageId", ""),
                        "cost": self.config["cost_per_whatsapp"]
                    }
                else:
                    raise Exception(f"WhatsApp failed: {response.text}")
        
        except Exception as e:
            logger.error(f"Africa's Talking WhatsApp error: {e}")
            raise

class TwilioProvider:
    """Twilio provider implementation"""
    
    def __init__(self):
        self.config = ProviderConfig.TWILIO
        self.account_sid = self.config["account_sid"]
        self.auth_token = self.config["auth_token"]
        self.phone_number = self.config["phone_number"]
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        try:
            import base64
            auth = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["sms_url"].format(account_sid=self.account_sid),
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "From": self.phone_number,
                        "To": phone,
                        "Body": message
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "success": True,
                        "message_id": data["sid"],
                        "cost": self.config["cost_per_sms"]
                    }
                else:
                    raise Exception(f"SMS failed: {response.text}")
        
        except Exception as e:
            logger.error(f"Twilio SMS error: {e}")
            raise

class MetaWhatsAppProvider:
    """Meta WhatsApp Business API provider"""
    
    def __init__(self):
        self.config = ProviderConfig.META_WHATSAPP
        self.access_token = self.config["access_token"]
        self.phone_id = self.config["phone_id"]
    
    async def send_whatsapp(self, phone: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp via Meta Business API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["api_url"].format(phone_id=self.phone_id),
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": phone,
                        "type": "text",
                        "text": {"body": message}
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message_id": data["messages"][0]["id"],
                        "cost": self.config["cost_per_whatsapp"]
                    }
                else:
                    raise Exception(f"WhatsApp failed: {response.text}")
        
        except Exception as e:
            logger.error(f"Meta WhatsApp error: {e}")
            raise

# ============================================================================
# UNIFIED COMMUNICATION SERVICE
# ============================================================================

class UnifiedCommunicationService:
    """Main service orchestrating all communication channels"""
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.message_store = {}  # In production, use Redis or database
        self.delivery_reports = {}
        
        # Initialize providers
        self.providers = {
            Provider.AFRICAS_TALKING: AfricasTalkingProvider(),
            Provider.TWILIO: TwilioProvider(),
            Provider.META_WHATSAPP: MetaWhatsAppProvider()
        }
    
    def generate_message_id(self, phone: str, message: str) -> str:
        """Generate unique message ID"""
        data = f"{phone}{message}{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def send_message(self, request: MessageRequest) -> MessageResponse:
        """Send message with automatic channel and provider selection"""
        message_id = self.generate_message_id(request.recipient_phone, request.message)
        
        # Try each preferred channel in order
        for channel in request.preferred_channels:
            try:
                result = await self._send_via_channel(
                    channel=channel,
                    phone=request.recipient_phone,
                    message=request.message,
                    priority=request.priority
                )
                
                if result["success"]:
                    # Record successful delivery
                    response = MessageResponse(
                        message_id=message_id,
                        status=DeliveryStatus.SENT,
                        channel_used=channel,
                        provider_used=result["provider"],
                        cost=result["cost"],
                        delivery_time=datetime.now()
                    )
                    
                    self.message_store[message_id] = response
                    return response
            
            except Exception as e:
                logger.warning(f"Failed to send via {channel}: {e}")
                continue
        
        # All channels failed
        raise HTTPException(status_code=500, detail="All communication channels failed")
    
    async def _send_via_channel(self, channel: CommunicationChannel, phone: str, 
                                message: str, priority: MessagePriority) -> Dict[str, Any]:
        """Send message via specific channel with provider failover"""
        
        # Get providers that support this channel, sorted by priority
        available_providers = self._get_providers_for_channel(channel)
        
        for provider_name in available_providers:
            # Check circuit breaker
            if not self.circuit_breaker.can_attempt(provider_name.value):
                logger.info(f"Skipping {provider_name} (circuit breaker open)")
                continue
            
            try:
                provider = self.providers[provider_name]
                
                # Send via appropriate method
                if channel == CommunicationChannel.WHATSAPP:
                    result = await provider.send_whatsapp(phone, message)
                elif channel == CommunicationChannel.SMS:
                    result = await provider.send_sms(phone, message)
                else:
                    continue
                
                # Success!
                self.circuit_breaker.record_success(provider_name.value)
                result["provider"] = provider_name
                return result
            
            except Exception as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                self.circuit_breaker.record_failure(provider_name.value)
                continue
        
        raise Exception(f"All providers failed for channel {channel}")
    
    def _get_providers_for_channel(self, channel: CommunicationChannel) -> List[Provider]:
        """Get providers that support a channel, sorted by priority"""
        providers = []
        
        if channel == CommunicationChannel.WHATSAPP:
            providers = [
                (Provider.META_WHATSAPP, ProviderConfig.META_WHATSAPP["priority"]),
                (Provider.AFRICAS_TALKING, ProviderConfig.AFRICAS_TALKING["priority"]),
                (Provider.TWILIO, ProviderConfig.TWILIO["priority"])
            ]
        elif channel == CommunicationChannel.SMS:
            providers = [
                (Provider.AFRICAS_TALKING, ProviderConfig.AFRICAS_TALKING["priority"]),
                (Provider.TWILIO, ProviderConfig.TWILIO["priority"]),
                (Provider.AWS_SNS, ProviderConfig.AWS_SNS["priority"])
            ]
        
        # Sort by priority (lower number = higher priority)
        providers.sort(key=lambda x: x[1])
        return [p[0] for p in providers]
    
    async def get_delivery_status(self, message_id: str) -> DeliveryReport:
        """Get delivery status for a message"""
        if message_id not in self.message_store:
            raise HTTPException(status_code=404, detail="Message not found")
        
        message = self.message_store[message_id]
        
        return DeliveryReport(
            message_id=message_id,
            status=message.status,
            channel=message.channel_used,
            provider=message.provider_used,
            attempts=1,
            last_attempt=message.delivery_time,
            delivered_at=message.delivery_time
        )

# ============================================================================
# API ENDPOINTS
# ============================================================================

# Initialize service
comm_service = UnifiedCommunicationService()

@app.post("/send", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Send a message via the best available channel"""
    return await comm_service.send_message(request)

@app.get("/status/{message_id}", response_model=DeliveryReport)
async def get_message_status(message_id: str):
    """Get delivery status of a message"""
    return await comm_service.get_delivery_status(message_id)

@app.post("/send-bulk")
async def send_bulk_messages(requests: List[MessageRequest], background_tasks: BackgroundTasks):
    """Send multiple messages in bulk"""
    message_ids = []
    
    for request in requests:
        background_tasks.add_task(comm_service.send_message, request)
        message_id = comm_service.generate_message_id(request.recipient_phone, request.message)
        message_ids.append(message_id)
    
    return {
        "status": "queued",
        "message_ids": message_ids,
        "count": len(message_ids)
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "unified-communication-service",
        "version": "2.0.0",
        "providers": {
            "africas_talking": "configured" if ProviderConfig.AFRICAS_TALKING["api_key"] else "not_configured",
            "twilio": "configured" if ProviderConfig.TWILIO["account_sid"] else "not_configured",
            "meta_whatsapp": "configured" if ProviderConfig.META_WHATSAPP["access_token"] else "not_configured"
        }
    }

@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    total_messages = len(comm_service.message_store)
    
    # Count by channel
    by_channel = defaultdict(int)
    by_provider = defaultdict(int)
    total_cost = 0.0
    
    for msg in comm_service.message_store.values():
        by_channel[msg.channel_used.value] += 1
        by_provider[msg.provider_used.value] += 1
        total_cost += msg.cost
    
    return {
        "total_messages": total_messages,
        "by_channel": dict(by_channel),
        "by_provider": dict(by_provider),
        "total_cost_usd": round(total_cost, 4),
        "circuit_breaker_status": dict(comm_service.circuit_breaker.state)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)

