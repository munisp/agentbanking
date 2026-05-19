import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Communication Gateway for Remittance Platform
Orchestrates all communication services and provides unified API
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("communication-gateway")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, EmailStr
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import aioredis
from celery import Celery
from kombu import Queue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/communication_gateway")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Celery setup for background tasks
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "communication_gateway",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["gateway"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "gateway.send_notification_task": {"queue": "notifications"},
        "gateway.send_bulk_notifications_task": {"queue": "bulk_notifications"},
        "gateway.process_scheduled_notifications": {"queue": "scheduled"},
    },
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("notifications"),
        Queue("bulk_notifications"),
        Queue("scheduled"),
        Queue("high_priority"),
    ),
)

class MessageType(str, Enum):
    NOTIFICATION = "notification"
    ALERT = "alert"
    MARKETING = "marketing"
    SYSTEM = "system"
    TRANSACTIONAL = "transactional"

class CommunicationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBSOCKET = "websocket"
    IN_APP = "in_app"
    VOICE = "voice"
    WHATSAPP = "whatsapp"

class MessagePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

class MessageStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

@dataclass
class CommunicationRequest:
    recipient_id: str
    message_type: MessageType
    priority: MessagePriority
    subject: str
    content: str
    channels: List[CommunicationChannel]
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    scheduled_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    callback_url: Optional[str] = None
    idempotency_key: Optional[str] = None

@dataclass
class CommunicationResponse:
    message_id: str
    recipient_id: str
    status: MessageStatus
    channels_attempted: List[CommunicationChannel]
    channels_successful: List[CommunicationChannel]
    delivery_details: Dict[CommunicationChannel, Dict[str, Any]]
    estimated_delivery_time: Optional[datetime]
    timestamp: datetime

class CommunicationMessage(Base):
    __tablename__ = "communication_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_id = Column(String, nullable=False)
    message_type = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    channels = Column(JSON, nullable=False)
    data = Column(JSON)
    template_id = Column(String)
    template_data = Column(JSON)
    status = Column(String, default=MessageStatus.PENDING.value)
    channels_attempted = Column(JSON)
    channels_successful = Column(JSON)
    delivery_details = Column(JSON)
    scheduled_time = Column(DateTime)
    expiry_time = Column(DateTime)
    callback_url = Column(String)
    idempotency_key = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)

class CommunicationLog(Base):
    __tablename__ = "communication_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    status = Column(String, nullable=False)
    provider = Column(String)
    provider_message_id = Column(String)
    error_message = Column(Text)
    metadata = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)

class CommunicationTemplate(Base):
    __tablename__ = "communication_templates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    message_type = Column(String, nullable=False)
    channels = Column(JSON, nullable=False)
    subject_template = Column(String)
    content_template = Column(Text, nullable=False)
    variables = Column(JSON)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Service Registry
class ServiceRegistry:
    def __init__(self):
        self.services = {
            CommunicationChannel.EMAIL: {
                "url": os.getenv("EMAIL_SERVICE_URL", "http://localhost:8005"),
                "health_endpoint": "/health",
                "send_endpoint": "/send-email"
            },
            CommunicationChannel.SMS: {
                "url": os.getenv("SMS_SERVICE_URL", "http://localhost:8006"),
                "health_endpoint": "/health",
                "send_endpoint": "/send-sms"
            },
            CommunicationChannel.PUSH: {
                "url": os.getenv("PUSH_SERVICE_URL", "http://localhost:8007"),
                "health_endpoint": "/health",
                "send_endpoint": "/send-push"
            },
            CommunicationChannel.WEBSOCKET: {
                "url": os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8008"),
                "health_endpoint": "/health",
                "send_endpoint": "/send-websocket"
            },
            "notification_service": {
                "url": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004"),
                "health_endpoint": "/health",
                "send_endpoint": "/send-notification"
            }
        }
    
    def get_service_url(self, channel: CommunicationChannel) -> str:
        """Get service URL for communication channel"""
        return self.services.get(channel, {}).get("url", "")
    
    async def check_service_health(self, channel: CommunicationChannel) -> bool:
        """Check if service is healthy"""
        service_info = self.services.get(channel)
        if not service_info:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{service_info['url']}{service_info['health_endpoint']}",
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {channel}: {e}")
            return False

# Communication Gateway Service
class CommunicationGateway:
    def __init__(self):
        self.service_registry = ServiceRegistry()
        self.redis_client = None
        self.rate_limiters = {}
        
    async def initialize(self):
        """Initialize communication gateway"""
        try:
            # Initialize Redis for caching and rate limiting
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            # Initialize rate limiters
            self.rate_limiters = {
                CommunicationChannel.EMAIL: RateLimiter(100, 3600),  # 100 emails per hour
                CommunicationChannel.SMS: RateLimiter(50, 3600),     # 50 SMS per hour
                CommunicationChannel.PUSH: RateLimiter(1000, 3600),  # 1000 push per hour
            }
            
            logger.info("Communication Gateway initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Communication Gateway: {e}")
            raise
    
    async def send_message(self, request: CommunicationRequest) -> CommunicationResponse:
        """Send message through specified channels"""
        try:
            # Check for duplicate request
            if request.idempotency_key:
                existing_message = await self.get_message_by_idempotency_key(request.idempotency_key)
                if existing_message:
                    return self.create_response_from_message(existing_message)
            
            # Generate message ID
            message_id = str(uuid.uuid4())
            
            # Save message to database
            await self.save_message(message_id, request)
            
            # Check if message should be scheduled
            if request.scheduled_time and request.scheduled_time > datetime.utcnow():
                # Schedule message for later
                await self.schedule_message(message_id, request.scheduled_time)
                
                return CommunicationResponse(
                    message_id=message_id,
                    recipient_id=request.recipient_id,
                    status=MessageStatus.QUEUED,
                    channels_attempted=[],
                    channels_successful=[],
                    delivery_details={},
                    estimated_delivery_time=request.scheduled_time,
                    timestamp=datetime.utcnow()
                )
            
            # Process message immediately
            return await self.process_message(message_id, request)
            
        except Exception as e:
            logger.error(f"Message sending failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def process_message(self, message_id: str, request: CommunicationRequest) -> CommunicationResponse:
        """Process message through all specified channels"""
        # Update status to processing
        await self.update_message_status(message_id, MessageStatus.PROCESSING)
        
        # Determine optimal channel order based on priority and reliability
        ordered_channels = self.optimize_channel_order(request.channels, request.priority)
        
        channels_attempted = []
        channels_successful = []
        delivery_details = {}
        
        # Process each channel
        for channel in ordered_channels:
            try:
                # Check rate limits
                if not await self.check_rate_limit(request.recipient_id, channel):
                    logger.warning(f"Rate limit exceeded for {request.recipient_id} on {channel}")
                    delivery_details[channel] = {
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    continue
                
                # Check service health
                if not await self.service_registry.check_service_health(channel):
                    logger.warning(f"Service {channel} is not healthy")
                    delivery_details[channel] = {
                        'success': False,
                        'error': 'Service unavailable',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    continue
                
                channels_attempted.append(channel)
                
                # Send through channel
                result = await self.send_through_channel(channel, request)
                
                delivery_details[channel] = result
                
                if result.get('success'):
                    channels_successful.append(channel)
                    
                    # Log successful delivery
                    await self.log_communication(message_id, channel, MessageStatus.SENT, result)
                    
                    # For critical messages, continue to all channels
                    # For others, stop after first successful delivery
                    if request.priority not in [MessagePriority.URGENT, MessagePriority.CRITICAL]:
                        break
                else:
                    # Log failed delivery
                    await self.log_communication(message_id, channel, MessageStatus.FAILED, result)
                
            except Exception as e:
                logger.error(f"Failed to send through {channel}: {e}")
                delivery_details[channel] = {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Log failed delivery
                await self.log_communication(message_id, channel, MessageStatus.FAILED, 
                                           {'error': str(e)})
        
        # Determine overall status
        if channels_successful:
            status = MessageStatus.SENT
            # Update message status
            await self.update_message_status(message_id, status, channels_attempted, 
                                           channels_successful, delivery_details)
        else:
            status = MessageStatus.FAILED
            await self.update_message_status(message_id, status, channels_attempted, 
                                           channels_successful, delivery_details)
        
        # Send callback if specified
        if request.callback_url:
            await self.send_callback(request.callback_url, message_id, status, delivery_details)
        
        return CommunicationResponse(
            message_id=message_id,
            recipient_id=request.recipient_id,
            status=status,
            channels_attempted=channels_attempted,
            channels_successful=channels_successful,
            delivery_details=delivery_details,
            estimated_delivery_time=None,
            timestamp=datetime.utcnow()
        )
    
    def optimize_channel_order(self, channels: List[CommunicationChannel], 
                             priority: MessagePriority) -> List[CommunicationChannel]:
        """Optimize channel order based on priority and reliability"""
        # Channel reliability scores (higher is better)
        reliability_scores = {
            CommunicationChannel.EMAIL: 0.95,
            CommunicationChannel.PUSH: 0.90,
            CommunicationChannel.WEBSOCKET: 0.85,
            CommunicationChannel.SMS: 0.80,
            CommunicationChannel.IN_APP: 0.75,
            CommunicationChannel.WHATSAPP: 0.70,
            CommunicationChannel.VOICE: 0.60,
        }
        
        # Speed scores (higher is faster)
        speed_scores = {
            CommunicationChannel.WEBSOCKET: 1.0,
            CommunicationChannel.PUSH: 0.9,
            CommunicationChannel.IN_APP: 0.9,
            CommunicationChannel.SMS: 0.7,
            CommunicationChannel.WHATSAPP: 0.6,
            CommunicationChannel.EMAIL: 0.5,
            CommunicationChannel.VOICE: 0.3,
        }
        
        # Weight factors based on priority
        if priority in [MessagePriority.URGENT, MessagePriority.CRITICAL]:
            # Prioritize speed for urgent messages
            weight_speed = 0.7
            weight_reliability = 0.3
        else:
            # Prioritize reliability for normal messages
            weight_speed = 0.3
            weight_reliability = 0.7
        
        # Calculate composite scores
        channel_scores = []
        for channel in channels:
            reliability = reliability_scores.get(channel, 0.5)
            speed = speed_scores.get(channel, 0.5)
            composite_score = (reliability * weight_reliability) + (speed * weight_speed)
            channel_scores.append((channel, composite_score))
        
        # Sort by composite score (descending)
        channel_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [channel for channel, score in channel_scores]
    
    async def send_through_channel(self, channel: CommunicationChannel, 
                                 request: CommunicationRequest) -> Dict[str, Any]:
        """Send message through specific channel"""
        try:
            # Use the comprehensive notification service for all channels
            notification_service_url = self.service_registry.services["notification_service"]["url"]
            
            # Prepare notification request
            notification_data = {
                "recipient_id": request.recipient_id,
                "notification_type": channel.value,
                "category": request.message_type.value,
                "priority": request.priority.value,
                "title": request.subject,
                "message": request.content,
                "data": request.data,
                "template_id": request.template_id,
                "template_data": request.template_data,
                "channels": [channel.value] if channel != CommunicationChannel.WEBSOCKET else None
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{notification_service_url}/send-notification",
                    json=notification_data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        'success': True,
                        'channel': channel.value,
                        'provider_response': result,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        'success': False,
                        'channel': channel.value,
                        'error': f"HTTP {response.status_code}: {response.text}",
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"Channel {channel} sending failed: {e}")
            return {
                'success': False,
                'channel': channel.value,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def check_rate_limit(self, recipient_id: str, channel: CommunicationChannel) -> bool:
        """Check rate limit for recipient and channel"""
        if channel not in self.rate_limiters:
            return True
        
        rate_limiter = self.rate_limiters[channel]
        key = f"rate_limit:{recipient_id}:{channel.value}"
        
        return await rate_limiter.is_allowed(key, self.redis_client)
    
    async def schedule_message(self, message_id: str, scheduled_time: datetime):
        """Schedule message for later delivery"""
        # Use Celery to schedule the task
        send_scheduled_message_task.apply_async(
            args=[message_id],
            eta=scheduled_time
        )
    
    async def send_bulk_messages(self, requests: List[CommunicationRequest]) -> List[CommunicationResponse]:
        """Send multiple messages efficiently"""
        # Group by channels and priority for batch processing
        grouped_requests = self.group_requests_for_batch_processing(requests)
        
        responses = []
        
        for group_key, group_requests in grouped_requests.items():
            # Process each group
            group_responses = await self.process_bulk_group(group_requests)
            responses.extend(group_responses)
        
        return responses
    
    def group_requests_for_batch_processing(self, requests: List[CommunicationRequest]) -> Dict[str, List[CommunicationRequest]]:
        """Group requests for efficient batch processing"""
        groups = {}
        
        for request in requests:
            # Create group key based on channels and priority
            channels_key = ",".join(sorted([c.value for c in request.channels]))
            group_key = f"{channels_key}:{request.priority.value}"
            
            if group_key not in groups:
                groups[group_key] = []
            
            groups[group_key].append(request)
        
        return groups
    
    async def process_bulk_group(self, requests: List[CommunicationRequest]) -> List[CommunicationResponse]:
        """Process a group of similar requests efficiently"""
        responses = []
        
        # Process in batches to avoid overwhelming services
        batch_size = 50
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self.send_message(request) for request in batch]
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for response in batch_responses:
                if isinstance(response, Exception):
                    logger.error(f"Bulk message processing failed: {response}")
                    # Create error response
                    error_response = CommunicationResponse(
                        message_id=str(uuid.uuid4()),
                        recipient_id="unknown",
                        status=MessageStatus.FAILED,
                        channels_attempted=[],
                        channels_successful=[],
                        delivery_details={},
                        estimated_delivery_time=None,
                        timestamp=datetime.utcnow()
                    )
                    responses.append(error_response)
                else:
                    responses.append(response)
        
        return responses
    
    async def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message status and delivery details"""
        db = SessionLocal()
        try:
            message = db.query(CommunicationMessage).filter(
                CommunicationMessage.id == message_id
            ).first()
            
            if message:
                return {
                    'message_id': message.id,
                    'recipient_id': message.recipient_id,
                    'status': message.status,
                    'channels_attempted': message.channels_attempted,
                    'channels_successful': message.channels_successful,
                    'delivery_details': message.delivery_details,
                    'created_at': message.created_at.isoformat(),
                    'sent_at': message.sent_at.isoformat() if message.sent_at else None,
                    'delivered_at': message.delivered_at.isoformat() if message.delivered_at else None
                }
            
            return None
            
        finally:
            db.close()
    
    async def get_message_by_idempotency_key(self, idempotency_key: str) -> Optional[CommunicationMessage]:
        """Get message by idempotency key"""
        db = SessionLocal()
        try:
            return db.query(CommunicationMessage).filter(
                CommunicationMessage.idempotency_key == idempotency_key
            ).first()
        finally:
            db.close()
    
    def create_response_from_message(self, message: CommunicationMessage) -> CommunicationResponse:
        """Create response object from database message"""
        return CommunicationResponse(
            message_id=message.id,
            recipient_id=message.recipient_id,
            status=MessageStatus(message.status),
            channels_attempted=[CommunicationChannel(c) for c in (message.channels_attempted or [])],
            channels_successful=[CommunicationChannel(c) for c in (message.channels_successful or [])],
            delivery_details={CommunicationChannel(k): v for k, v in (message.delivery_details or {}).items()},
            estimated_delivery_time=message.scheduled_time,
            timestamp=message.created_at
        )
    
    async def save_message(self, message_id: str, request: CommunicationRequest):
        """Save message to database"""
        db = SessionLocal()
        try:
            message = CommunicationMessage(
                id=message_id,
                recipient_id=request.recipient_id,
                message_type=request.message_type.value,
                priority=request.priority.value,
                subject=request.subject,
                content=request.content,
                channels=[c.value for c in request.channels],
                data=request.data,
                template_id=request.template_id,
                template_data=request.template_data,
                scheduled_time=request.scheduled_time,
                expiry_time=request.expiry_time,
                callback_url=request.callback_url,
                idempotency_key=request.idempotency_key
            )
            
            db.add(message)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    async def update_message_status(self, message_id: str, status: MessageStatus,
                                  channels_attempted: List[CommunicationChannel] = None,
                                  channels_successful: List[CommunicationChannel] = None,
                                  delivery_details: Dict[CommunicationChannel, Dict[str, Any]] = None):
        """Update message status in database"""
        db = SessionLocal()
        try:
            message = db.query(CommunicationMessage).filter(
                CommunicationMessage.id == message_id
            ).first()
            
            if message:
                message.status = status.value
                message.updated_at = datetime.utcnow()
                
                if channels_attempted:
                    message.channels_attempted = [c.value for c in channels_attempted]
                
                if channels_successful:
                    message.channels_successful = [c.value for c in channels_successful]
                
                if delivery_details:
                    message.delivery_details = {k.value: v for k, v in delivery_details.items()}
                
                if status == MessageStatus.SENT:
                    message.sent_at = datetime.utcnow()
                elif status == MessageStatus.DELIVERED:
                    message.delivered_at = datetime.utcnow()
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update message status: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def log_communication(self, message_id: str, channel: CommunicationChannel,
                              status: MessageStatus, result: Dict[str, Any]):
        """Log communication attempt"""
        db = SessionLocal()
        try:
            log_entry = CommunicationLog(
                message_id=message_id,
                channel=channel.value,
                status=status.value,
                provider=result.get('provider'),
                provider_message_id=result.get('message_id'),
                error_message=result.get('error'),
                metadata=result
            )
            
            db.add(log_entry)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log communication: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def send_callback(self, callback_url: str, message_id: str, 
                          status: MessageStatus, delivery_details: Dict[str, Any]):
        """Send callback notification"""
        try:
            callback_data = {
                'message_id': message_id,
                'status': status.value,
                'delivery_details': delivery_details,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(callback_url, json=callback_data, timeout=10.0)
                
        except Exception as e:
            logger.error(f"Callback sending failed: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        # Check all registered services
        service_health = {}
        for channel, service_info in self.service_registry.services.items():
            if isinstance(channel, CommunicationChannel):
                service_health[channel.value] = await self.service_registry.check_service_health(channel)
            else:
                # For non-channel services like notification_service
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{service_info['url']}{service_info['health_endpoint']}",
                            timeout=5.0
                        )
                        service_health[channel] = response.status_code == 200
                except:
                    service_health[channel] = False
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'communication-gateway',
            'version': '1.0.0',
            'services': service_health,
            'redis_connected': self.redis_client is not None
        }

# Rate Limiter
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def is_allowed(self, key: str, redis_client) -> bool:
        """Check if request is allowed under rate limit"""
        if not redis_client:
            return True
        
        try:
            current_time = int(datetime.utcnow().timestamp())
            window_start = current_time - self.window_seconds
            
            # Remove old entries
            await redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            current_count = await redis_client.zcard(key)
            
            if current_count >= self.max_requests:
                return False
            
            # Add current request
            await redis_client.zadd(key, {str(current_time): current_time})
            await redis_client.expire(key, self.window_seconds)
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiting check failed: {e}")
            return True  # Allow on error

# Celery Tasks
@celery_app.task
def send_notification_task(message_data: Dict[str, Any]):
    """Celery task for sending notifications"""
    # This would be implemented to handle async notification sending
    logger.info(f"Processing notification task: {message_data}")

@celery_app.task
def send_bulk_notifications_task(messages_data: List[Dict[str, Any]]):
    """Celery task for sending bulk notifications"""
    logger.info(f"Processing bulk notifications task: {len(messages_data)} messages")

@celery_app.task
def send_scheduled_message_task(message_id: str):
    """Celery task for sending scheduled messages"""
    logger.info(f"Processing scheduled message: {message_id}")
    # This would retrieve the message and process it

@celery_app.task
def process_scheduled_notifications():
    """Celery periodic task for processing scheduled notifications"""
    logger.info("Processing scheduled notifications")

# FastAPI application
app = FastAPI(title="Communication Gateway", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global gateway instance
communication_gateway = CommunicationGateway()

# Pydantic models for API
class CommunicationRequestModel(BaseModel):
    recipient_id: str
    message_type: MessageType
    priority: MessagePriority
    subject: str
    content: str
    channels: List[CommunicationChannel]
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    scheduled_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    callback_url: Optional[str] = None
    idempotency_key: Optional[str] = None

class BulkCommunicationRequestModel(BaseModel):
    messages: List[CommunicationRequestModel]

@app.on_event("startup")
async def startup_event():
    """Initialize gateway on startup"""
    await communication_gateway.initialize()

@app.post("/send-message")
async def send_message(request: CommunicationRequestModel):
    """Send message through communication gateway"""
    comm_request = CommunicationRequest(
        recipient_id=request.recipient_id,
        message_type=request.message_type,
        priority=request.priority,
        subject=request.subject,
        content=request.content,
        channels=request.channels,
        data=request.data,
        template_id=request.template_id,
        template_data=request.template_data,
        scheduled_time=request.scheduled_time,
        expiry_time=request.expiry_time,
        callback_url=request.callback_url,
        idempotency_key=request.idempotency_key
    )
    
    response = await communication_gateway.send_message(comm_request)
    return asdict(response)

@app.post("/send-bulk-messages")
async def send_bulk_messages(request: BulkCommunicationRequestModel):
    """Send multiple messages through communication gateway"""
    comm_requests = [
        CommunicationRequest(
            recipient_id=msg.recipient_id,
            message_type=msg.message_type,
            priority=msg.priority,
            subject=msg.subject,
            content=msg.content,
            channels=msg.channels,
            data=msg.data,
            template_id=msg.template_id,
            template_data=msg.template_data,
            scheduled_time=msg.scheduled_time,
            expiry_time=msg.expiry_time,
            callback_url=msg.callback_url,
            idempotency_key=msg.idempotency_key
        )
        for msg in request.messages
    ]
    
    responses = await communication_gateway.send_bulk_messages(comm_requests)
    return {'responses': [asdict(response) for response in responses]}

@app.get("/message-status/{message_id}")
async def get_message_status(message_id: str):
    """Get message status and delivery details"""
    status = await communication_gateway.get_message_status(message_id)
    if not status:
        raise HTTPException(status_code=404, detail="Message not found")
    return status

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await communication_gateway.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)
