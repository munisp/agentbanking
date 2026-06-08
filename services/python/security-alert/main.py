"""
Security Alert Service
Real-time security monitoring and alerting system for Remittance Platform

Features:
- Real-time threat detection
- Multi-channel alert delivery (SMS, Email, Push, WhatsApp)
- Alert severity classification
- Alert acknowledgment and resolution tracking
- Integration with SIEM systems
- Automated incident response
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import httpx
import redis
import json
import os
from jose import jwt, JWTError
import asyncpg
import logging

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/security_alerts")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "remittance")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/security_alert")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Security Alert Service",
    description="Real-time security monitoring and alerting",
    version="1.0.0"
)

security = HTTPBearer()

# Database connection pool
db_pool = None
redis_client = None

# Enums
class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertType(str, Enum):
    FRAUD_DETECTION = "fraud_detection"
    SUSPICIOUS_LOGIN = "suspicious_login"
    UNUSUAL_TRANSACTION = "unusual_transaction"
    ACCOUNT_TAKEOVER = "account_takeover"
    DATA_BREACH = "data_breach"
    SYSTEM_ANOMALY = "system_anomaly"
    COMPLIANCE_VIOLATION = "compliance_violation"

class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"

class AlertChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    WHATSAPP = "whatsapp"
    WEBHOOK = "webhook"

# Models
class AlertCreate(BaseModel):
    alert_type: AlertType
    severity: AlertSeverity
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    entity_type: str = Field(..., description="Type of entity (user, transaction, agent, etc.)")
    entity_id: str = Field(..., description="ID of the affected entity")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    channels: List[AlertChannel] = Field(default=[AlertChannel.EMAIL])
    recipients: List[str] = Field(..., min_items=1, description="List of recipient IDs or contact info")

class AlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None

class AlertResponse(BaseModel):
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    entity_type: str
    entity_id: str
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    assigned_to: Optional[str]
    created_by: str
    metadata: Dict[str, Any]
    channels: List[AlertChannel]
    recipients: List[str]

class AlertStats(BaseModel):
    total_alerts: int
    open_alerts: int
    acknowledged_alerts: int
    resolved_alerts: int
    critical_alerts: int
    high_alerts: int
    medium_alerts: int
    low_alerts: int
    avg_resolution_time_hours: float

# Startup/Shutdown
@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    
    # Initialize database pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    
    # Initialize Redis
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    # Create tables
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS security_alerts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                alert_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                acknowledged_at TIMESTAMP,
                resolved_at TIMESTAMP,
                assigned_to VARCHAR(100),
                created_by VARCHAR(100) NOT NULL,
                metadata JSONB DEFAULT '{}',
                channels JSONB DEFAULT '[]',
                recipients JSONB DEFAULT '[]',
                resolution_notes TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON security_alerts(status);
            CREATE INDEX IF NOT EXISTS idx_alerts_severity ON security_alerts(severity);
            CREATE INDEX IF NOT EXISTS idx_alerts_entity ON security_alerts(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON security_alerts(created_at DESC);
        """)
    
    logger.info("Security Alert Service started successfully")

@app.on_event("shutdown")
async def shutdown():
    global db_pool, redis_client
    
    if db_pool:
        await db_pool.close()
    
    if redis_client:
        redis_client.close()
    
    logger.info("Security Alert Service shut down")

# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify Keycloak JWT token"""
    token = credentials.credentials
    
    try:
        # Get JWKS from Keycloak
        jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            jwks = response.json()
        
        # Decode and verify token
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        payload = jwt.decode(token, key, algorithms=["RS256"], audience="account")
        return payload
    
    except JWTError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

# Helper functions
async def send_sms_alert(phone: str, message: str):
    """Send SMS alert via Twilio"""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not configured")
        return
    
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        logger.info(f"SMS sent to {phone}")
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")

async def send_email_alert(email: str, subject: str, body: str):
    """Send email alert via SMTP"""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured")
        return
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

async def send_push_notification(user_id: str, title: str, body: str):
    """Send push notification"""
    # Implement push notification logic (Firebase, OneSignal, etc.)
    logger.info(f"Push notification sent to user {user_id}")

async def publish_to_kafka(topic: str, message: Dict[str, Any]):
    """Publish event to Kafka"""
    try:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
        await producer.start()
        try:
            await producer.send_and_wait(topic, json.dumps(message).encode())
        finally:
            await producer.stop()
    except Exception as e:
        logger.error(f"Failed to publish to Kafka: {e}")

# API Endpoints
@app.post("/alerts", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert: AlertCreate,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Create a new security alert"""
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO security_alerts (
                alert_type, severity, title, description, entity_type, entity_id,
                created_by, metadata, channels, recipients
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """, alert.alert_type.value, alert.severity.value, alert.title, alert.description,
            alert.entity_type, alert.entity_id, user.get("sub"),
            json.dumps(alert.metadata), json.dumps([c.value for c in alert.channels]),
            json.dumps(alert.recipients))
        
        alert_id = str(row['id'])
        
        # Send alerts via configured channels
        message = f"🚨 {alert.severity.upper()}: {alert.title}\n\n{alert.description}"
        
        for channel in alert.channels:
            for recipient in alert.recipients:
                if channel == AlertChannel.SMS:
                    background_tasks.add_task(send_sms_alert, recipient, message)
                elif channel == AlertChannel.EMAIL:
                    background_tasks.add_task(send_email_alert, recipient, alert.title, alert.description)
                elif channel == AlertChannel.PUSH:
                    background_tasks.add_task(send_push_notification, recipient, alert.title, alert.description)
        
        # Publish to Kafka
        background_tasks.add_task(publish_to_kafka, "security.alerts.created", {
            "alert_id": alert_id,
            "alert_type": alert.alert_type.value,
            "severity": alert.severity.value,
            "entity_type": alert.entity_type,
            "entity_id": alert.entity_id,
            "created_at": datetime.utcnow().isoformat()
        })
        
        # Cache alert for quick access
        redis_client.setex(f"alert:{alert_id}", 3600, json.dumps(dict(row), default=str))
        
        return AlertResponse(**dict(row))

@app.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[AlertStatus] = None,
    severity: Optional[AlertSeverity] = None,
    entity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: Dict[str, Any] = Depends(verify_token)
):
    """List security alerts with filters"""
    
    query = "SELECT * FROM security_alerts WHERE 1=1"
    params = []
    param_count = 1
    
    if status:
        query += f" AND status = ${param_count}"
        params.append(status.value)
        param_count += 1
    
    if severity:
        query += f" AND severity = ${param_count}"
        params.append(severity.value)
        param_count += 1
    
    if entity_type:
        query += f" AND entity_type = ${param_count}"
        params.append(entity_type)
        param_count += 1
    
    query += f" ORDER BY created_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, offset])
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [AlertResponse(**dict(row)) for row in rows]

@app.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get alert by ID"""
    
    # Try cache first
    cached = redis_client.get(f"alert:{alert_id}")
    if cached:
        return AlertResponse(**json.loads(cached))
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM security_alerts WHERE id = $1", alert_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Update cache
        redis_client.setex(f"alert:{alert_id}", 3600, json.dumps(dict(row), default=str))
        
        return AlertResponse(**dict(row))

@app.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    update: AlertUpdate,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Update alert status"""
    
    updates = []
    params = [alert_id]
    param_count = 2
    
    if update.status:
        updates.append(f"status = ${param_count}")
        params.append(update.status.value)
        param_count += 1
        
        if update.status == AlertStatus.ACKNOWLEDGED:
            updates.append(f"acknowledged_at = NOW()")
        elif update.status == AlertStatus.RESOLVED:
            updates.append(f"resolved_at = NOW()")
    
    if update.assigned_to:
        updates.append(f"assigned_to = ${param_count}")
        params.append(update.assigned_to)
        param_count += 1
    
    if update.resolution_notes:
        updates.append(f"resolution_notes = ${param_count}")
        params.append(update.resolution_notes)
        param_count += 1
    
    updates.append("updated_at = NOW()")
    
    query = f"UPDATE security_alerts SET {', '.join(updates)} WHERE id = $1 RETURNING *"
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Invalidate cache
        redis_client.delete(f"alert:{alert_id}")
        
        return AlertResponse(**dict(row))

@app.get("/alerts/stats/summary", response_model=AlertStats)
async def get_alert_stats(
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get alert statistics"""
    
    async with db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_alerts,
                COUNT(*) FILTER (WHERE status = 'open') as open_alerts,
                COUNT(*) FILTER (WHERE status = 'acknowledged') as acknowledged_alerts,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_alerts,
                COUNT(*) FILTER (WHERE severity = 'critical') as critical_alerts,
                COUNT(*) FILTER (WHERE severity = 'high') as high_alerts,
                COUNT(*) FILTER (WHERE severity = 'medium') as medium_alerts,
                COUNT(*) FILTER (WHERE severity = 'low') as low_alerts,
                AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) FILTER (WHERE resolved_at IS NOT NULL) as avg_resolution_time_hours
            FROM security_alerts
        """)
        
        return AlertStats(**dict(stats))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        redis_client.ping()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8101)
