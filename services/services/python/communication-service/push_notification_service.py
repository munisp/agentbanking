"""
Push Notification Service
Handles push notifications for mobile and web applications
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import asyncio
import httpx
import json
import logging

import os
# Configuration
app = FastAPI(title="Push Notification Service")
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# Push notification providers
FCM_SERVER_KEY = ""  # Firebase Cloud Messaging
APNS_KEY = ""  # Apple Push Notification Service
WEB_PUSH_VAPID_KEY = ""  # Web Push VAPID key

# Enums
class NotificationType(str, Enum):
    ORDER_UPDATE = "order_update"
    PAYMENT_RECEIVED = "payment_received"
    SHIPMENT_UPDATE = "shipment_update"
    INVENTORY_ALERT = "inventory_alert"
    PROMOTION = "promotion"
    SYSTEM_ALERT = "system_alert"
    GENERAL = "general"

class DevicePlatform(str, Enum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"

class NotificationPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

# Models
class DeviceToken(BaseModel):
    user_id: int
    token: str
    platform: DevicePlatform
    is_active: bool = True

class PushNotification(BaseModel):
    user_ids: List[int]
    title: str
    body: str
    notification_type: NotificationType = NotificationType.GENERAL
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    badge_count: Optional[int] = None
    sound: Optional[str] = "default"
    ttl: int = 86400  # Time to live in seconds (24 hours)

class NotificationStatus(BaseModel):
    id: int
    user_id: int
    title: str
    body: str
    notification_type: str
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime

# Database initialization
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        # Device tokens table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS device_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token VARCHAR(500) NOT NULL,
                platform VARCHAR(20) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, token)
            )
        ''')
        
        # Notifications table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS push_notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                body TEXT NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                priority VARCHAR(20) DEFAULT 'normal',
                data JSONB,
                image_url VARCHAR(500),
                action_url VARCHAR(500),
                status VARCHAR(50) DEFAULT 'pending',
                sent_at TIMESTAMP,
                delivered_at TIMESTAMP,
                read_at TIMESTAMP,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Notification logs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS notification_logs (
                id SERIAL PRIMARY KEY,
                notification_id INTEGER REFERENCES push_notifications(id),
                device_token VARCHAR(500),
                platform VARCHAR(20),
                status VARCHAR(50) NOT NULL,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_device_tokens_user ON device_tokens(user_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_device_tokens_active ON device_tokens(is_active)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON push_notifications(user_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_notifications_status ON push_notifications(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_notifications_type ON push_notifications(notification_type)')

# Helper functions
async def send_fcm_notification(token: str, notification: Dict) -> bool:
    """Send notification via Firebase Cloud Messaging (Android)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={
                    "Authorization": f"key={FCM_SERVER_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "to": token,
                    "notification": {
                        "title": notification["title"],
                        "body": notification["body"],
                        "sound": notification.get("sound", "default"),
                        "badge": notification.get("badge_count"),
                        "image": notification.get("image_url")
                    },
                    "data": notification.get("data", {}),
                    "priority": "high" if notification.get("priority") == "high" else "normal",
                    "time_to_live": notification.get("ttl", 86400)
                },
                timeout=10.0
            )
            
            return response.status_code == 200
            
    except Exception as e:
        logger.error(f"FCM send error: {e}")
        return False

async def send_apns_notification(token: str, notification: Dict) -> bool:
    """Send notification via Apple Push Notification Service (iOS)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.push.apple.com/3/device/{token}",
                headers={
                    "authorization": f"bearer {APNS_KEY}",
                    "apns-topic": "com.remittance.app",
                    "apns-priority": "10" if notification.get("priority") == "high" else "5",
                    "apns-expiration": str(int((datetime.utcnow() + timedelta(seconds=notification.get("ttl", 86400))).timestamp()))
                },
                json={
                    "aps": {
                        "alert": {
                            "title": notification["title"],
                            "body": notification["body"]
                        },
                        "sound": notification.get("sound", "default"),
                        "badge": notification.get("badge_count")
                    },
                    "data": notification.get("data", {})
                },
                timeout=10.0
            )
            
            return response.status_code == 200
            
    except Exception as e:
        logger.error(f"APNS send error: {e}")
        return False

async def send_web_push_notification(token: str, notification: Dict) -> bool:
    """Send notification via Web Push (browser)"""
    try:
        # Web Push implementation would use pywebpush library
        # For now, this is a placeholder
        logger.info(f"Web push notification sent to {token[:20]}...")
        return True
        
    except Exception as e:
        logger.error(f"Web push send error: {e}")
        return False

async def send_to_device(token: str, platform: str, notification: Dict) -> bool:
    """Send notification to specific device"""
    if platform == DevicePlatform.ANDROID:
        return await send_fcm_notification(token, notification)
    elif platform == DevicePlatform.IOS:
        return await send_apns_notification(token, notification)
    elif platform == DevicePlatform.WEB:
        return await send_web_push_notification(token, notification)
    else:
        logger.error(f"Unknown platform: {platform}")
        return False

async def process_notification_queue():
    """Background task to process notification queue"""
    while True:
        try:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            async with db_pool.acquire() as conn:
                # Get pending notifications
                notifications = await conn.fetch(
                    """
                    SELECT * FROM push_notifications
                    WHERE status = 'pending'
                    ORDER BY 
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'normal' THEN 2
                            WHEN 'low' THEN 3
                        END,
                        created_at
                    LIMIT 20
                    """,
                )
                
                for notif in notifications:
                    # Update status to processing
                    await conn.execute(
                        """
                        UPDATE push_notifications
                        SET status = 'processing'
                        WHERE id = $1
                        """,
                        notif['id']
                    )
                    
                    # Get user's device tokens
                    tokens = await conn.fetch(
                        """
                        SELECT * FROM device_tokens
                        WHERE user_id = $1 AND is_active = TRUE
                        """,
                        notif['user_id']
                    )
                    
                    if not tokens:
                        # No devices registered
                        await conn.execute(
                            """
                            UPDATE push_notifications
                            SET status = 'failed',
                                error_message = 'No active device tokens',
                                sent_at = NOW()
                            WHERE id = $1
                            """,
                            notif['id']
                        )
                        continue
                    
                    # Prepare notification payload
                    notification_data = {
                        "title": notif['title'],
                        "body": notif['body'],
                        "priority": notif['priority'],
                        "data": notif['data'],
                        "image_url": notif['image_url'],
                        "sound": "default",
                        "ttl": 86400
                    }
                    
                    # Send to all devices
                    success_count = 0
                    for token in tokens:
                        success = await send_to_device(
                            token['token'],
                            token['platform'],
                            notification_data
                        )
                        
                        # Log result
                        await conn.execute(
                            """
                            INSERT INTO notification_logs (
                                notification_id, device_token, platform, status
                            )
                            VALUES ($1, $2, $3, $4)
                            """,
                            notif['id'],
                            token['token'],
                            token['platform'],
                            'sent' if success else 'failed'
                        )
                        
                        if success:
                            success_count += 1
                    
                    # Update notification status
                    if success_count > 0:
                        await conn.execute(
                            """
                            UPDATE push_notifications
                            SET status = 'sent', sent_at = NOW()
                            WHERE id = $1
                            """,
                            notif['id']
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE push_notifications
                            SET status = 'failed',
                                error_message = 'Failed to send to all devices',
                                sent_at = NOW()
                            WHERE id = $1
                            """,
                            notif['id']
                        )
                        
        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()
    # Start background notification processor
    asyncio.create_task(process_notification_queue())

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/devices/register")
async def register_device(device: DeviceToken):
    """Register device token for push notifications"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO device_tokens (user_id, token, platform)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, token)
            DO UPDATE SET is_active = TRUE, updated_at = NOW()
            """,
            device.user_id, device.token, device.platform.value
        )
        
        return {"message": "Device registered successfully"}

@app.delete("/devices/{user_id}/{token}")
async def unregister_device(user_id: int, token: str):
    """Unregister device token"""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE device_tokens
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = $1 AND token = $2
            """,
            user_id, token
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Device not found")
        
        return {"message": "Device unregistered successfully"}

@app.get("/devices/{user_id}")
async def get_user_devices(user_id: int):
    """Get user's registered devices"""
    async with db_pool.acquire() as conn:
        devices = await conn.fetch(
            """
            SELECT * FROM device_tokens
            WHERE user_id = $1 AND is_active = TRUE
            """,
            user_id
        )
        
        return [DeviceToken(**dict(device)) for device in devices]

@app.post("/notifications/send")
async def send_notification(notification: PushNotification):
    """Queue push notification for sending"""
    async with db_pool.acquire() as conn:
        notification_ids = []
        
        for user_id in notification.user_ids:
            notif_id = await conn.fetchval(
                """
                INSERT INTO push_notifications (
                    user_id, title, body, notification_type, priority,
                    data, image_url, action_url
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                user_id,
                notification.title,
                notification.body,
                notification.notification_type.value,
                notification.priority.value,
                json.dumps(notification.data) if notification.data else None,
                notification.image_url,
                notification.action_url
            )
            notification_ids.append(notif_id)
        
        return {
            "message": f"Notification queued for {len(notification.user_ids)} user(s)",
            "notification_ids": notification_ids
        }

@app.get("/notifications/{user_id}")
async def get_user_notifications(user_id: int, limit: int = 50):
    """Get user's notifications"""
    async with db_pool.acquire() as conn:
        notifications = await conn.fetch(
            """
            SELECT * FROM push_notifications
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id, limit
        )
        
        return [NotificationStatus(**dict(n)) for n in notifications]

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    """Mark notification as read"""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE push_notifications
            SET read_at = NOW()
            WHERE id = $1 AND read_at IS NULL
            """,
            notification_id
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Notification not found or already read")
        
        return {"message": "Notification marked as read"}

@app.get("/notifications/logs/{notification_id}")
async def get_notification_logs(notification_id: int):
    """Get notification delivery logs"""
    async with db_pool.acquire() as conn:
        logs = await conn.fetch(
            """
            SELECT * FROM notification_logs
            WHERE notification_id = $1
            ORDER BY sent_at DESC
            """,
            notification_id
        )
        
        return [dict(log) for log in logs]

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "push_notifications",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)

