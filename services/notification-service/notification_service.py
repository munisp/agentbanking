import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Notification Service for Remittance Platform
Handles multi-channel notifications including email, SMS, push notifications, and WebSocket
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
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
import ssl

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("notification-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, EmailStr
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import aioredis
from jinja2 import Environment, FileSystemLoader
import boto3
from twilio.rest import Client as TwilioClient
import firebase_admin
from firebase_admin import credentials, messaging
from websockets.exceptions import ConnectionClosed
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/notifications")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBSOCKET = "websocket"
    IN_APP = "in_app"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NotificationCategory(str, Enum):
    TRANSACTION = "transaction"
    SECURITY = "security"
    FRAUD_ALERT = "fraud_alert"
    ACCOUNT = "account"
    MARKETING = "marketing"
    SYSTEM = "system"
    COMPLIANCE = "compliance"

@dataclass
class NotificationRequest:
    recipient_id: str
    notification_type: NotificationType
    category: NotificationCategory
    priority: NotificationPriority
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    scheduled_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    channels: Optional[List[NotificationType]] = None

@dataclass
class NotificationResponse:
    notification_id: str
    recipient_id: str
    status: NotificationStatus
    channels_sent: List[NotificationType]
    delivery_details: Dict[NotificationType, Dict[str, Any]]
    timestamp: datetime

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_id = Column(String, nullable=False)
    notification_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON)
    template_id = Column(String)
    template_data = Column(JSON)
    status = Column(String, default=NotificationStatus.PENDING.value)
    channels_sent = Column(JSON)
    delivery_details = Column(JSON)
    scheduled_time = Column(DateTime)
    expiry_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    notification_type = Column(String, nullable=False)
    subject_template = Column(String)
    body_template = Column(Text, nullable=False)
    variables = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)
    websocket_enabled = Column(Boolean, default=True)
    in_app_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserContact(Base):
    __tablename__ = "user_contacts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    email = Column(String)
    phone_number = Column(String)
    push_tokens = Column(JSON)  # FCM tokens for push notifications
    preferred_language = Column(String, default="en")
    timezone = Column(String, default="UTC")
    is_verified_email = Column(Boolean, default=False)
    is_verified_phone = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# WebSocket Connection Manager
class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user: {user_id}")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user: {user_id}")
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
                return True
            except (ConnectionClosed, WebSocketDisconnect):
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast(self, message: str):
        disconnected_users = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except (ConnectionClosed, WebSocketDisconnect):
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)

# Email Service
class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@remittance-platform.com")
        
        # AWS SES configuration (alternative to SMTP)
        self.use_ses = os.getenv("USE_SES", "false").lower() == "true"
        if self.use_ses:
            self.ses_client = boto3.client(
                'ses',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
    
    async def send_email(self, to_email: str, subject: str, body: str, 
                        is_html: bool = True, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email using SMTP or AWS SES"""
        try:
            if self.use_ses:
                return await self.send_email_ses(to_email, subject, body, is_html)
            else:
                return await self.send_email_smtp(to_email, subject, body, is_html, attachments)
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message_id': None
            }
    
    async def send_email_smtp(self, to_email: str, subject: str, body: str, 
                             is_html: bool = True, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email using SMTP"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            body_type = 'html' if is_html else 'plain'
            msg.attach(MimeText(body, body_type))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MimeBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                text = msg.as_string()
                server.sendmail(self.from_email, to_email, text)
            
            return {
                'success': True,
                'message_id': f"smtp_{uuid.uuid4()}",
                'provider': 'smtp'
            }
            
        except Exception as e:
            logger.error(f"SMTP email sending failed: {e}")
            raise
    
    async def send_email_ses(self, to_email: str, subject: str, body: str, is_html: bool = True) -> Dict[str, Any]:
        """Send email using AWS SES"""
        try:
            body_key = 'Html' if is_html else 'Text'
            
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {body_key: {'Data': body}}
                }
            )
            
            return {
                'success': True,
                'message_id': response['MessageId'],
                'provider': 'ses'
            }
            
        except Exception as e:
            logger.error(f"SES email sending failed: {e}")
            raise

# SMS Service
class SMSService:
    def __init__(self):
        # Twilio configuration
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER", "")
        
        if self.twilio_account_sid and self.twilio_auth_token:
            self.twilio_client = TwilioClient(self.twilio_account_sid, self.twilio_auth_token)
        else:
            self.twilio_client = None
        
        # AWS SNS configuration (alternative to Twilio)
        self.use_sns = os.getenv("USE_SNS", "false").lower() == "true"
        if self.use_sns:
            self.sns_client = boto3.client(
                'sns',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
    
    async def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS using Twilio or AWS SNS"""
        try:
            if self.use_sns:
                return await self.send_sms_sns(phone_number, message)
            elif self.twilio_client:
                return await self.send_sms_twilio(phone_number, message)
            else:
                raise ValueError("No SMS service configured")
                
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message_id': None
            }
    
    async def send_sms_twilio(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS using Twilio"""
        try:
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=phone_number
            )
            
            return {
                'success': True,
                'message_id': message_obj.sid,
                'provider': 'twilio'
            }
            
        except Exception as e:
            logger.error(f"Twilio SMS sending failed: {e}")
            raise
    
    async def send_sms_sns(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS using AWS SNS"""
        try:
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message
            )
            
            return {
                'success': True,
                'message_id': response['MessageId'],
                'provider': 'sns'
            }
            
        except Exception as e:
            logger.error(f"SNS SMS sending failed: {e}")
            raise

# Push Notification Service
class PushNotificationService:
    def __init__(self):
        # Firebase configuration
        firebase_config_path = os.getenv("FIREBASE_CONFIG_PATH", "")
        if firebase_config_path and os.path.exists(firebase_config_path):
            try:
                cred = credentials.Certificate(firebase_config_path)
                firebase_admin.initialize_app(cred)
                self.firebase_enabled = True
            except Exception as e:
                logger.error(f"Firebase initialization failed: {e}")
                self.firebase_enabled = False
        else:
            self.firebase_enabled = False
    
    async def send_push_notification(self, tokens: List[str], title: str, body: str, 
                                   data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send push notification using Firebase Cloud Messaging"""
        if not self.firebase_enabled:
            return {
                'success': False,
                'error': 'Firebase not configured',
                'results': []
            }
        
        try:
            # Create message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                tokens=tokens
            )
            
            # Send message
            response = messaging.send_multicast(message)
            
            results = []
            for i, result in enumerate(response.responses):
                results.append({
                    'token': tokens[i],
                    'success': result.success,
                    'message_id': result.message_id if result.success else None,
                    'error': str(result.exception) if not result.success else None
                })
            
            return {
                'success': response.success_count > 0,
                'success_count': response.success_count,
                'failure_count': response.failure_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Push notification sending failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

# Template Engine
class TemplateEngine:
    def __init__(self):
        # Initialize Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(template_dir, exist_ok=True)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
        
        # Create default templates
        self.create_default_templates()
    
    def create_default_templates(self):
        """Create default notification templates"""
        templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        
        # Transaction alert template
        transaction_template = """
        <html>
        <body>
            <h2>Transaction Alert</h2>
            <p>Dear {{ customer_name }},</p>
            <p>A transaction of <strong>${{ amount }}</strong> was {{ action }} on your account ending in {{ account_suffix }}.</p>
            <p><strong>Details:</strong></p>
            <ul>
                <li>Amount: ${{ amount }}</li>
                <li>Date: {{ transaction_date }}</li>
                <li>Merchant: {{ merchant_name }}</li>
                <li>Reference: {{ transaction_id }}</li>
            </ul>
            <p>If you did not authorize this transaction, please contact us immediately.</p>
            <p>Best regards,<br>Remittance Platform Team</p>
        </body>
        </html>
        """
        
        # Fraud alert template
        fraud_template = """
        <html>
        <body>
            <h2 style="color: red;">FRAUD ALERT</h2>
            <p>Dear {{ customer_name }},</p>
            <p><strong>Suspicious activity detected on your account!</strong></p>
            <p>We have detected potentially fraudulent activity on your account ending in {{ account_suffix }}.</p>
            <p><strong>Suspicious Transaction Details:</strong></p>
            <ul>
                <li>Amount: ${{ amount }}</li>
                <li>Date: {{ transaction_date }}</li>
                <li>Location: {{ location }}</li>
                <li>Risk Level: {{ risk_level }}</li>
            </ul>
            <p><strong>Immediate Action Required:</strong></p>
            <ul>
                <li>Review your recent transactions</li>
                <li>Change your account password</li>
                <li>Contact us immediately at {{ support_phone }}</li>
            </ul>
            <p>Your account has been temporarily secured as a precautionary measure.</p>
            <p>Remittance Platform Security Team</p>
        </body>
        </html>
        """
        
        # Save templates to files
        os.makedirs(templates_dir, exist_ok=True)
        
        with open(os.path.join(templates_dir, 'transaction_alert.html'), 'w') as f:
            f.write(transaction_template)
        
        with open(os.path.join(templates_dir, 'fraud_alert.html'), 'w') as f:
            f.write(fraud_template)
    
    def render_template(self, template_id: str, template_data: Dict[str, Any]) -> str:
        """Render template with data"""
        try:
            # First try to load from database
            db = SessionLocal()
            try:
                template_obj = db.query(NotificationTemplate).filter(
                    NotificationTemplate.template_id == template_id,
                    NotificationTemplate.is_active == True
                ).first()
                
                if template_obj:
                    template = self.jinja_env.from_string(template_obj.body_template)
                    return template.render(**template_data)
            finally:
                db.close()
            
            # Fallback to file-based templates
            template_file = f"{template_id}.html"
            template = self.jinja_env.get_template(template_file)
            return template.render(**template_data)
            
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            # Return plain text fallback
            return f"Notification: {template_data.get('message', 'No message available')}"

# Main Notification Service
class NotificationService:
    def __init__(self):
        self.email_service = EmailService()
        self.sms_service = SMSService()
        self.push_service = PushNotificationService()
        self.template_engine = TemplateEngine()
        self.websocket_manager = WebSocketManager()
        self.redis_client = None
        
    async def initialize(self):
        """Initialize notification service"""
        try:
            # Initialize Redis for caching and queuing
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            logger.info("Notification Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Notification Service: {e}")
            # Continue without Redis if not available
            self.redis_client = None
    
    async def send_notification(self, request: NotificationRequest) -> NotificationResponse:
        """Send notification through specified channels"""
        try:
            notification_id = str(uuid.uuid4())
            
            # Save notification to database
            await self.save_notification(notification_id, request)
            
            # Get user contact information and preferences
            user_contacts = await self.get_user_contacts(request.recipient_id)
            user_preferences = await self.get_user_preferences(request.recipient_id, request.category)
            
            # Determine channels to use
            channels_to_use = self.determine_channels(request, user_preferences)
            
            # Prepare message content
            message_content = await self.prepare_message_content(request)
            
            # Send through each channel
            delivery_details = {}
            channels_sent = []
            
            for channel in channels_to_use:
                try:
                    if channel == NotificationType.EMAIL and user_contacts.get('email'):
                        result = await self.send_email_notification(
                            user_contacts['email'], message_content, request
                        )
                        delivery_details[channel] = result
                        if result.get('success'):
                            channels_sent.append(channel)
                    
                    elif channel == NotificationType.SMS and user_contacts.get('phone_number'):
                        result = await self.send_sms_notification(
                            user_contacts['phone_number'], message_content, request
                        )
                        delivery_details[channel] = result
                        if result.get('success'):
                            channels_sent.append(channel)
                    
                    elif channel == NotificationType.PUSH and user_contacts.get('push_tokens'):
                        result = await self.send_push_notification_to_user(
                            user_contacts['push_tokens'], message_content, request
                        )
                        delivery_details[channel] = result
                        if result.get('success'):
                            channels_sent.append(channel)
                    
                    elif channel == NotificationType.WEBSOCKET:
                        result = await self.send_websocket_notification(
                            request.recipient_id, message_content, request
                        )
                        delivery_details[channel] = result
                        if result.get('success'):
                            channels_sent.append(channel)
                    
                    elif channel == NotificationType.IN_APP:
                        result = await self.send_in_app_notification(
                            request.recipient_id, message_content, request
                        )
                        delivery_details[channel] = result
                        if result.get('success'):
                            channels_sent.append(channel)
                
                except Exception as e:
                    logger.error(f"Failed to send notification via {channel}: {e}")
                    delivery_details[channel] = {
                        'success': False,
                        'error': str(e)
                    }
            
            # Update notification status
            status = NotificationStatus.SENT if channels_sent else NotificationStatus.FAILED
            await self.update_notification_status(notification_id, status, channels_sent, delivery_details)
            
            return NotificationResponse(
                notification_id=notification_id,
                recipient_id=request.recipient_id,
                status=status,
                channels_sent=channels_sent,
                delivery_details=delivery_details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Notification sending failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def prepare_message_content(self, request: NotificationRequest) -> Dict[str, str]:
        """Prepare message content using templates if specified"""
        if request.template_id and request.template_data:
            # Render template
            rendered_content = self.template_engine.render_template(
                request.template_id, request.template_data
            )
            
            return {
                'title': request.title,
                'body': rendered_content,
                'plain_text': request.message
            }
        else:
            return {
                'title': request.title,
                'body': request.message,
                'plain_text': request.message
            }
    
    def determine_channels(self, request: NotificationRequest, 
                          user_preferences: Dict[str, bool]) -> List[NotificationType]:
        """Determine which channels to use for notification"""
        if request.channels:
            # Use explicitly specified channels
            channels = request.channels
        else:
            # Use default channels based on priority and category
            channels = [request.notification_type]
            
            # Add additional channels for high priority notifications
            if request.priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL]:
                if request.notification_type != NotificationType.EMAIL:
                    channels.append(NotificationType.EMAIL)
                if request.notification_type != NotificationType.SMS:
                    channels.append(NotificationType.SMS)
                if request.notification_type != NotificationType.PUSH:
                    channels.append(NotificationType.PUSH)
        
        # Filter based on user preferences
        filtered_channels = []
        for channel in channels:
            preference_key = f"{channel.value}_enabled"
            if user_preferences.get(preference_key, True):
                filtered_channels.append(channel)
        
        return filtered_channels
    
    async def send_email_notification(self, email: str, content: Dict[str, str], 
                                    request: NotificationRequest) -> Dict[str, Any]:
        """Send email notification"""
        return await self.email_service.send_email(
            to_email=email,
            subject=content['title'],
            body=content['body'],
            is_html=True
        )
    
    async def send_sms_notification(self, phone_number: str, content: Dict[str, str], 
                                  request: NotificationRequest) -> Dict[str, Any]:
        """Send SMS notification"""
        # Use plain text for SMS
        sms_message = f"{content['title']}: {content['plain_text']}"
        return await self.sms_service.send_sms(phone_number, sms_message)
    
    async def send_push_notification_to_user(self, push_tokens: List[str], content: Dict[str, str], 
                                           request: NotificationRequest) -> Dict[str, Any]:
        """Send push notification"""
        data = request.data or {}
        data.update({
            'notification_id': str(uuid.uuid4()),
            'category': request.category.value,
            'priority': request.priority.value
        })
        
        return await self.push_service.send_push_notification(
            tokens=push_tokens,
            title=content['title'],
            body=content['plain_text'],
            data=data
        )
    
    async def send_websocket_notification(self, user_id: str, content: Dict[str, str], 
                                        request: NotificationRequest) -> Dict[str, Any]:
        """Send WebSocket notification"""
        message_data = {
            'type': 'notification',
            'category': request.category.value,
            'priority': request.priority.value,
            'title': content['title'],
            'message': content['plain_text'],
            'data': request.data or {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        success = await self.websocket_manager.send_personal_message(
            json.dumps(message_data), user_id
        )
        
        return {
            'success': success,
            'channel': 'websocket'
        }
    
    async def send_in_app_notification(self, user_id: str, content: Dict[str, str], 
                                     request: NotificationRequest) -> Dict[str, Any]:
        """Send in-app notification (stored for later retrieval)"""
        try:
            # Store in Redis for quick retrieval
            if self.redis_client:
                notification_data = {
                    'title': content['title'],
                    'message': content['plain_text'],
                    'category': request.category.value,
                    'priority': request.priority.value,
                    'data': request.data or {},
                    'timestamp': datetime.utcnow().isoformat(),
                    'read': False
                }
                
                # Store in user's notification list
                await self.redis_client.lpush(
                    f"in_app_notifications:{user_id}",
                    json.dumps(notification_data)
                )
                
                # Keep only last 100 notifications
                await self.redis_client.ltrim(f"in_app_notifications:{user_id}", 0, 99)
            
            return {
                'success': True,
                'channel': 'in_app'
            }
            
        except Exception as e:
            logger.error(f"In-app notification failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_user_contacts(self, user_id: str) -> Dict[str, Any]:
        """Get user contact information"""
        db = SessionLocal()
        try:
            contact = db.query(UserContact).filter(UserContact.user_id == user_id).first()
            if contact:
                return {
                    'email': contact.email,
                    'phone_number': contact.phone_number,
                    'push_tokens': contact.push_tokens or [],
                    'preferred_language': contact.preferred_language,
                    'timezone': contact.timezone
                }
            else:
                return {}
        finally:
            db.close()
    
    async def get_user_preferences(self, user_id: str, category: NotificationCategory) -> Dict[str, bool]:
        """Get user notification preferences"""
        db = SessionLocal()
        try:
            preference = db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category.value
            ).first()
            
            if preference:
                return {
                    'email_enabled': preference.email_enabled,
                    'sms_enabled': preference.sms_enabled,
                    'push_enabled': preference.push_enabled,
                    'websocket_enabled': preference.websocket_enabled,
                    'in_app_enabled': preference.in_app_enabled
                }
            else:
                # Default preferences
                return {
                    'email_enabled': True,
                    'sms_enabled': True,
                    'push_enabled': True,
                    'websocket_enabled': True,
                    'in_app_enabled': True
                }
        finally:
            db.close()
    
    async def save_notification(self, notification_id: str, request: NotificationRequest):
        """Save notification to database"""
        db = SessionLocal()
        try:
            notification = Notification(
                id=notification_id,
                recipient_id=request.recipient_id,
                notification_type=request.notification_type.value,
                category=request.category.value,
                priority=request.priority.value,
                title=request.title,
                message=request.message,
                data=request.data,
                template_id=request.template_id,
                template_data=request.template_data,
                scheduled_time=request.scheduled_time,
                expiry_time=request.expiry_time
            )
            
            db.add(notification)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to save notification: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    async def update_notification_status(self, notification_id: str, status: NotificationStatus,
                                       channels_sent: List[NotificationType],
                                       delivery_details: Dict[NotificationType, Dict[str, Any]]):
        """Update notification status in database"""
        db = SessionLocal()
        try:
            notification = db.query(Notification).filter(Notification.id == notification_id).first()
            if notification:
                notification.status = status.value
                notification.channels_sent = [channel.value for channel in channels_sent]
                notification.delivery_details = {k.value: v for k, v in delivery_details.items()}
                notification.sent_at = datetime.utcnow()
                
                if status == NotificationStatus.DELIVERED:
                    notification.delivered_at = datetime.utcnow()
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update notification status: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def get_notifications(self, user_id: str, category: Optional[NotificationCategory] = None,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Get notifications for user"""
        db = SessionLocal()
        try:
            query = db.query(Notification).filter(Notification.recipient_id == user_id)
            
            if category:
                query = query.filter(Notification.category == category.value)
            
            notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
            
            return [
                {
                    'id': notif.id,
                    'category': notif.category,
                    'priority': notif.priority,
                    'title': notif.title,
                    'message': notif.message,
                    'data': notif.data,
                    'status': notif.status,
                    'channels_sent': notif.channels_sent,
                    'created_at': notif.created_at.isoformat(),
                    'sent_at': notif.sent_at.isoformat() if notif.sent_at else None
                }
                for notif in notifications
            ]
            
        finally:
            db.close()
    
    async def get_in_app_notifications(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get in-app notifications for user"""
        if not self.redis_client:
            return []
        
        try:
            notifications_json = await self.redis_client.lrange(
                f"in_app_notifications:{user_id}", 0, limit - 1
            )
            
            notifications = []
            for notif_json in notifications_json:
                notification = json.loads(notif_json)
                notifications.append(notification)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Failed to get in-app notifications: {e}")
            return []
    
    async def mark_notification_read(self, user_id: str, notification_index: int):
        """Mark in-app notification as read"""
        if not self.redis_client:
            return False
        
        try:
            # Get the notification
            notif_json = await self.redis_client.lindex(
                f"in_app_notifications:{user_id}", notification_index
            )
            
            if notif_json:
                notification = json.loads(notif_json)
                notification['read'] = True
                
                # Update the notification
                await self.redis_client.lset(
                    f"in_app_notifications:{user_id}",
                    notification_index,
                    json.dumps(notification)
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'notification-service',
            'version': '1.0.0',
            'components': {
                'email_service': True,
                'sms_service': self.sms_service.twilio_client is not None or self.sms_service.use_sns,
                'push_service': self.push_service.firebase_enabled,
                'redis': self.redis_client is not None,
                'websocket_manager': True
            }
        }

# FastAPI application
app = FastAPI(title="Notification Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
notification_service = NotificationService()

# Pydantic models for API
class NotificationRequestModel(BaseModel):
    recipient_id: str
    notification_type: NotificationType
    category: NotificationCategory
    priority: NotificationPriority
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    scheduled_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    channels: Optional[List[NotificationType]] = None

class UserContactModel(BaseModel):
    user_id: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    push_tokens: Optional[List[str]] = None
    preferred_language: str = "en"
    timezone: str = "UTC"

class NotificationPreferenceModel(BaseModel):
    user_id: str
    category: NotificationCategory
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    websocket_enabled: bool = True
    in_app_enabled: bool = True

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await notification_service.initialize()

@app.post("/send-notification")
async def send_notification(request: NotificationRequestModel):
    """Send notification"""
    notification_request = NotificationRequest(
        recipient_id=request.recipient_id,
        notification_type=request.notification_type,
        category=request.category,
        priority=request.priority,
        title=request.title,
        message=request.message,
        data=request.data,
        template_id=request.template_id,
        template_data=request.template_data,
        scheduled_time=request.scheduled_time,
        expiry_time=request.expiry_time,
        channels=request.channels
    )
    
    response = await notification_service.send_notification(notification_request)
    return asdict(response)

@app.get("/notifications/{user_id}")
async def get_notifications(user_id: str, category: Optional[NotificationCategory] = None, limit: int = 50):
    """Get notifications for user"""
    notifications = await notification_service.get_notifications(user_id, category, limit)
    return {'notifications': notifications}

@app.get("/in-app-notifications/{user_id}")
async def get_in_app_notifications(user_id: str, limit: int = 20):
    """Get in-app notifications for user"""
    notifications = await notification_service.get_in_app_notifications(user_id, limit)
    return {'notifications': notifications}

@app.post("/in-app-notifications/{user_id}/{notification_index}/read")
async def mark_notification_read(user_id: str, notification_index: int):
    """Mark in-app notification as read"""
    success = await notification_service.mark_notification_read(user_id, notification_index)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {'message': 'Notification marked as read'}

@app.post("/user-contacts")
async def update_user_contacts(contact: UserContactModel):
    """Update user contact information"""
    db = SessionLocal()
    try:
        existing_contact = db.query(UserContact).filter(UserContact.user_id == contact.user_id).first()
        
        if existing_contact:
            existing_contact.email = contact.email
            existing_contact.phone_number = contact.phone_number
            existing_contact.push_tokens = contact.push_tokens
            existing_contact.preferred_language = contact.preferred_language
            existing_contact.timezone = contact.timezone
            existing_contact.updated_at = datetime.utcnow()
        else:
            new_contact = UserContact(
                user_id=contact.user_id,
                email=contact.email,
                phone_number=contact.phone_number,
                push_tokens=contact.push_tokens,
                preferred_language=contact.preferred_language,
                timezone=contact.timezone
            )
            db.add(new_contact)
        
        db.commit()
        return {'message': 'User contacts updated successfully'}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/notification-preferences")
async def update_notification_preferences(preference: NotificationPreferenceModel):
    """Update user notification preferences"""
    db = SessionLocal()
    try:
        existing_pref = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == preference.user_id,
            NotificationPreference.category == preference.category.value
        ).first()
        
        if existing_pref:
            existing_pref.email_enabled = preference.email_enabled
            existing_pref.sms_enabled = preference.sms_enabled
            existing_pref.push_enabled = preference.push_enabled
            existing_pref.websocket_enabled = preference.websocket_enabled
            existing_pref.in_app_enabled = preference.in_app_enabled
            existing_pref.updated_at = datetime.utcnow()
        else:
            new_pref = NotificationPreference(
                user_id=preference.user_id,
                category=preference.category.value,
                email_enabled=preference.email_enabled,
                sms_enabled=preference.sms_enabled,
                push_enabled=preference.push_enabled,
                websocket_enabled=preference.websocket_enabled,
                in_app_enabled=preference.in_app_enabled
            )
            db.add(new_pref)
        
        db.commit()
        return {'message': 'Notification preferences updated successfully'}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time notifications"""
    await notification_service.websocket_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        notification_service.websocket_manager.disconnect(user_id)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await notification_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
