import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Security Monitoring Service
Integrates Wazuh, OpenCTI, and OpenAppSec for complete security monitoring
Port: 8022
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("comprehensive-security-monitoring-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import asyncio
import httpx
import os
from enum import Enum

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID, JSONB
import redis

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agent_user:agent_password@localhost/security_monitoring_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis for caching
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=2,
    decode_responses=True
)

# Wazuh Configuration
WAZUH_API_URL = os.getenv("WAZUH_API_URL", "https://wazuh-manager:55000")
WAZUH_USERNAME = os.getenv("WAZUH_USERNAME", "admin")
WAZUH_PASSWORD = os.getenv("WAZUH_PASSWORD", "admin")

# OpenCTI Configuration
OPENCTI_URL = os.getenv("OPENCTI_URL", "http://opencti:8080/graphql")
OPENCTI_TOKEN = os.getenv("OPENCTI_TOKEN", "")

# OpenAppSec Configuration
OPENAPPSEC_URL = os.getenv("OPENAPPSEC_URL", "http://openappsec:8080")
OPENAPPSEC_API_KEY = os.getenv("OPENAPPSEC_API_KEY", "")

# ==================== ENUMS ====================

class ThreatLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"

class AttackPattern(str, Enum):
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    DDOS = "ddos"
    MALWARE = "malware"
    PHISHING = "phishing"
    INSIDER_THREAT = "insider_threat"
    RANSOMWARE = "ransomware"
    DATA_EXFILTRATION = "data_exfiltration"

# ==================== DATABASE MODELS ====================

class SecurityAlert(Base):
    __tablename__ = "security_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(String(100), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    source_alert_id = Column(String(200))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    threat_level = Column(String(20), nullable=False, index=True)
    attack_pattern = Column(String(50), index=True)
    target_ip = Column(String(45))
    target_hostname = Column(String(255))
    source_ip = Column(String(45), index=True)
    source_country = Column(String(2))
    raw_data = Column(JSONB)
    indicators = Column(JSONB)
    mitre_tactics = Column(JSONB)
    is_false_positive = Column(Boolean, default=False)
    is_acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by = Column(String(100))
    acknowledged_at = Column(DateTime)
    detected_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_alert_source_level', 'source', 'threat_level'),
    )

class SecurityIncident(Base):
    __tablename__ = "security_incidents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), default="open", nullable=False, index=True)
    incident_type = Column(String(50))
    attack_patterns = Column(JSONB)
    affected_systems = Column(JSONB)
    assigned_to = Column(String(100))
    response_actions = Column(JSONB)
    containment_actions = Column(JSONB)
    impact_score = Column(Float)
    affected_users = Column(Integer, default=0)
    data_compromised = Column(Boolean, default=False)
    related_alert_ids = Column(JSONB)
    detected_at = Column(DateTime, nullable=False)
    started_investigation_at = Column(DateTime)
    contained_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ThreatIntelligence(Base):
    __tablename__ = "threat_intelligence"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator_id = Column(String(100), unique=True, nullable=False, index=True)
    indicator_type = Column(String(50), nullable=False, index=True)
    indicator_value = Column(String(500), nullable=False, index=True)
    threat_type = Column(String(100))
    threat_actor = Column(String(200))
    malware_family = Column(String(200))
    confidence_score = Column(Float)
    is_active = Column(Boolean, default=True, index=True)
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    source = Column(String(100))
    tags = Column(JSONB)
    description = Column(Text)
    references = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, index=True)

class SystemHealth(Base):
    __tablename__ = "system_health"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    last_check = Column(DateTime, nullable=False, index=True)
    response_time = Column(Float)
    error_message = Column(Text)
    metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== PYDANTIC MODELS ====================

class AlertCreate(BaseModel):
    title: str
    description: Optional[str] = None
    threat_level: ThreatLevel
    attack_pattern: Optional[AttackPattern] = None
    target_ip: Optional[str] = None
    source_ip: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = {}

class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: ThreatLevel
    incident_type: Optional[str] = None
    affected_systems: Optional[List[str]] = []

# ==================== HELPER FUNCTIONS ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_wazuh_token() -> Optional[str]:
    """Get Wazuh authentication token"""
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                f"{WAZUH_API_URL}/security/user/authenticate",
                auth=(WAZUH_USERNAME, WAZUH_PASSWORD),
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()["data"]["token"]
    except Exception as e:
        print(f"Wazuh authentication failed: {e}")
        return None

async def fetch_wazuh_alerts(token: str, hours: int = 1) -> List[Dict]:
    """Fetch alerts from Wazuh"""
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f"{WAZUH_API_URL}/alerts",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 100, "sort": "-timestamp"},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json().get("data", {}).get("affected_items", [])
    except Exception as e:
        print(f"Failed to fetch Wazuh alerts: {e}")
        return []

async def fetch_opencti_indicators() -> List[Dict]:
    """Fetch threat indicators from OpenCTI using GraphQL"""
    try:
        query = """
        query GetIndicators {
            indicators(first: 100, orderBy: created_at, orderMode: desc) {
                edges {
                    node {
                        id
                        pattern
                        pattern_type
                        valid_from
                        valid_until
                        x_opencti_score
                        description
                    }
                }
            }
        }
        """
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENCTI_URL,
                json={"query": query},
                headers={"Authorization": f"Bearer {OPENCTI_TOKEN}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return [edge["node"] for edge in data.get("data", {}).get("indicators", {}).get("edges", [])]
    except Exception as e:
        print(f"Failed to fetch OpenCTI indicators: {e}")
        return []

async def fetch_openappsec_events() -> List[Dict]:
    """Fetch security events from OpenAppSec"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OPENAPPSEC_URL}/api/v1/events",
                headers={"X-API-Key": OPENAPPSEC_API_KEY},
                params={"limit": 100, "since": "1h"},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json().get("events", [])
    except Exception as e:
        print(f"Failed to fetch OpenAppSec events: {e}")
        return []

def map_wazuh_level(level: int) -> str:
    """Map Wazuh alert level to threat level"""
    if level >= 12:
        return "critical"
    elif level >= 9:
        return "high"
    elif level >= 6:
        return "medium"
    elif level >= 3:
        return "low"
    else:
        return "info"

# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Comprehensive Security Monitoring Service",
    description="Integrates Wazuh, OpenCTI, and OpenAppSec",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections: List[WebSocket] = []

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check with component status"""
    
    wazuh_status = "healthy"
    try:
        token = await get_wazuh_token()
        if not token:
            wazuh_status = "degraded"
    except:
        wazuh_status = "down"
    
    opencti_status = "healthy" if OPENCTI_TOKEN else "not_configured"
    openappsec_status = "healthy" if OPENAPPSEC_API_KEY else "not_configured"
    
    for component, status in [("wazuh", wazuh_status), ("opencti", opencti_status), ("openappsec", openappsec_status)]:
        health = SystemHealth(
            component=component,
            status=status,
            last_check=datetime.utcnow()
        )
        db.add(health)
    db.commit()
    
    return {
        "status": "healthy",
        "service": "security-monitoring",
        "version": "1.0.0",
        "port": 8022,
        "components": {
            "wazuh": wazuh_status,
            "opencti": opencti_status,
            "openappsec": openappsec_status
        },
        "features": [
            "wazuh_integration",
            "opencti_integration",
            "openappsec_integration",
            "real_time_alerts",
            "incident_management",
            "threat_intelligence",
            "websocket_updates"
        ]
    }

@app.post("/alerts")
async def create_alert(alert_data: AlertCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Create security alert"""
    
    alert = SecurityAlert(
        alert_id=f"ALT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        source="manual",
        title=alert_data.title,
        description=alert_data.description,
        threat_level=alert_data.threat_level.value,
        attack_pattern=alert_data.attack_pattern.value if alert_data.attack_pattern else None,
        target_ip=alert_data.target_ip,
        source_ip=alert_data.source_ip,
        raw_data=alert_data.raw_data,
        detected_at=datetime.utcnow()
    )
    
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    background_tasks.add_task(broadcast_alert, alert)
    
    return {
        "id": str(alert.id),
        "alert_id": alert.alert_id,
        "title": alert.title,
        "threat_level": alert.threat_level,
        "source": alert.source,
        "detected_at": alert.detected_at.isoformat()
    }

@app.get("/alerts")
async def get_alerts(
    threat_level: Optional[ThreatLevel] = None,
    source: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get security alerts with filtering"""
    
    query = db.query(SecurityAlert)
    
    if threat_level:
        query = query.filter(SecurityAlert.threat_level == threat_level.value)
    if source:
        query = query.filter(SecurityAlert.source == source)
    if acknowledged is not None:
        query = query.filter(SecurityAlert.is_acknowledged == acknowledged)
    
    alerts = query.order_by(SecurityAlert.detected_at.desc()).limit(limit).all()
    
    return {
        "alerts": [
            {
                "id": str(a.id),
                "alert_id": a.alert_id,
                "title": a.title,
                "threat_level": a.threat_level,
                "source": a.source,
                "detected_at": a.detected_at.isoformat(),
                "is_acknowledged": a.is_acknowledged
            }
            for a in alerts
        ],
        "total": len(alerts)
    }

@app.post("/incidents")
async def create_incident(incident_data: IncidentCreate, db: Session = Depends(get_db)):
    """Create security incident"""
    
    incident = SecurityIncident(
        incident_id=f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        title=incident_data.title,
        description=incident_data.description,
        severity=incident_data.severity.value,
        status="open",
        incident_type=incident_data.incident_type,
        affected_systems=incident_data.affected_systems,
        detected_at=datetime.utcnow()
    )
    
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    return {
        "id": str(incident.id),
        "incident_id": incident.incident_id,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "detected_at": incident.detected_at.isoformat()
    }

@app.get("/incidents")
async def get_incidents(
    status: Optional[IncidentStatus] = None,
    severity: Optional[ThreatLevel] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get security incidents"""
    
    query = db.query(SecurityIncident)
    
    if status:
        query = query.filter(SecurityIncident.status == status.value)
    if severity:
        query = query.filter(SecurityIncident.severity == severity.value)
    
    incidents = query.order_by(SecurityIncident.detected_at.desc()).limit(limit).all()
    
    return {
        "incidents": [
            {
                "id": str(i.id),
                "incident_id": i.incident_id,
                "title": i.title,
                "severity": i.severity,
                "status": i.status,
                "detected_at": i.detected_at.isoformat()
            }
            for i in incidents
        ],
        "total": len(incidents)
    }

@app.post("/sync/wazuh")
async def sync_wazuh_alerts(db: Session = Depends(get_db)):
    """Sync alerts from Wazuh"""
    
    token = await get_wazuh_token()
    if not token:
        raise HTTPException(status_code=503, detail="Wazuh not available")
    
    alerts = await fetch_wazuh_alerts(token)
    
    created_count = 0
    for wazuh_alert in alerts:
        existing = db.query(SecurityAlert).filter(
            SecurityAlert.source == "wazuh",
            SecurityAlert.source_alert_id == wazuh_alert.get("id")
        ).first()
        
        if not existing:
            alert = SecurityAlert(
                alert_id=f"ALT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
                source="wazuh",
                source_alert_id=wazuh_alert.get("id"),
                title=wazuh_alert.get("rule", {}).get("description", "Wazuh Alert"),
                description=wazuh_alert.get("full_log"),
                threat_level=map_wazuh_level(wazuh_alert.get("rule", {}).get("level", 0)),
                target_ip=wazuh_alert.get("agent", {}).get("ip"),
                target_hostname=wazuh_alert.get("agent", {}).get("name"),
                source_ip=wazuh_alert.get("data", {}).get("srcip"),
                raw_data=wazuh_alert,
                detected_at=datetime.utcnow()
            )
            db.add(alert)
            created_count += 1
    
    db.commit()
    
    return {"synced": created_count, "source": "wazuh"}

@app.post("/sync/opencti")
async def sync_opencti_indicators(db: Session = Depends(get_db)):
    """Sync threat indicators from OpenCTI"""
    
    indicators = await fetch_opencti_indicators()
    
    created_count = 0
    for indicator in indicators:
        existing = db.query(ThreatIntelligence).filter(
            ThreatIntelligence.indicator_value == indicator.get("pattern")
        ).first()
        
        if not existing:
            threat_intel = ThreatIntelligence(
                indicator_id=indicator.get("id"),
                indicator_type=indicator.get("pattern_type", "unknown"),
                indicator_value=indicator.get("pattern"),
                confidence_score=indicator.get("x_opencti_score", 50) / 100.0,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                source="opencti",
                description=indicator.get("description")
            )
            db.add(threat_intel)
            created_count += 1
    
    db.commit()
    
    return {"synced": created_count, "source": "opencti"}

@app.post("/sync/openappsec")
async def sync_openappsec_events(db: Session = Depends(get_db)):
    """Sync security events from OpenAppSec"""
    
    events = await fetch_openappsec_events()
    
    created_count = 0
    for event in events:
        alert = SecurityAlert(
            alert_id=f"ALT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            source="openappsec",
            source_alert_id=event.get("id"),
            title=event.get("title", "OpenAppSec Event"),
            description=event.get("description"),
            threat_level=event.get("severity", "medium"),
            target_ip=event.get("target_ip"),
            source_ip=event.get("source_ip"),
            raw_data=event,
            detected_at=datetime.utcnow()
        )
        db.add(alert)
        created_count += 1
    
    db.commit()
    
    return {"synced": created_count, "source": "openappsec"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time security updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast_alert(alert: SecurityAlert):
    """Broadcast alert to all WebSocket clients"""
    message = {
        "type": "alert",
        "data": {
            "alert_id": alert.alert_id,
            "title": alert.title,
            "threat_level": alert.threat_level,
            "detected_at": alert.detected_at.isoformat()
        }
    }
    
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8022)
