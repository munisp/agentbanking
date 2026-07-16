"""
Real-time Notification Service
Handles:
- POS device geolocation tracking with geofencing
- Transaction notifications (ping on money received)
- Support for both WebSocket and MQTT protocols
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Union
from geopy.distance import geodesic
import httpx

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Header,
    Depends,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid

# MQTT support
try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.warning("MQTT not available. Install with: pip install paho-mqtt")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", ""
)
MQTT_BROKER = os.getenv("MQTT_BROKER", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
REDIS_URL = os.getenv("REDIS_URL", "")
DEFAULT_GEOFENCE_RADIUS_KM = float(
    os.getenv("DEFAULT_GEOFENCE_RADIUS_KM", "5.0")
)  # 5km default
ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "https://54agent.upi.dev/account")
AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")
DEFAULT_TENANT_ID = os.getenv("TENANT_ID", "54agent")

# Database setup
Base = declarative_base()
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections are alive before using them
    pool_size=10,  # Number of connections to keep in the pool
    max_overflow=20,  # Number of connections to allow in overflow
    pool_timeout=30,  # Time to wait before giving up on getting a connection from the pool
    pool_recycle=1800,  # Recycle connections after this many seconds (30 minutes)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# =====================================================
# DATABASE MODELS
# =====================================================


class POSDeviceLocation(Base):
    """Tracks POS device location history"""

    __tablename__ = "pos_device_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float)  # GPS accuracy in meters
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_within_geofence = Column(Boolean, default=True)
    speed = Column(Float)  # km/h
    battery_level = Column(Integer)


class POSGeofence(Base):
    """Defines geofence boundaries for POS devices"""

    __tablename__ = "pos_geofences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False, default=DEFAULT_GEOFENCE_RADIUS_KM)
    name = Column(String(255))  # e.g., "Main Store", "Branch Office"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TransactionNotification(Base):
    """Stores transaction notifications sent to POS devices"""

    __tablename__ = "transaction_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        String(100), nullable=False, index=True, unique=True
    )  # Add unique constraint
    agent_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False)
    device_id = Column(String(100))  # Target device
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # credit, debit
    sender_name = Column(String(255))
    account_number = Column(String(50))
    notification_sent_at = Column(DateTime, default=datetime.utcnow)
    was_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime)


class GeofenceViolation(Base):
    """Stores geofence violations for admin monitoring"""

    __tablename__ = "geofence_violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    geofence_id = Column(UUID(as_uuid=True), index=True)
    geofence_name = Column(String(255))
    current_latitude = Column(Float, nullable=False)
    current_longitude = Column(Float, nullable=False)
    geofence_center_lat = Column(Float, nullable=False)
    geofence_center_lng = Column(Float, nullable=False)
    distance_from_center_km = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    violation_time = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    was_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    admin_notes = Column(String(1000))


# Create tables
Base.metadata.create_all(bind=engine)


# =====================================================
# PYDANTIC MODELS
# =====================================================


class LocationUpdate(BaseModel):
    """Location update from POS device"""

    device_id: str
    agent_id: str
    tenant_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    battery_level: Optional[int] = None


class GeofenceConfig(BaseModel):
    """Geofence configuration"""

    agent_id: str
    tenant_id: str
    center_latitude: float
    center_longitude: float
    radius_km: float = DEFAULT_GEOFENCE_RADIUS_KM
    name: Optional[str] = None


class TransactionPing(BaseModel):
    """Transaction notification payload"""

    transaction_id: str
    agent_id: str
    tenant_id: str
    amount: float
    transaction_type: str
    sender_name: Optional[str] = None
    account_number: Optional[str] = None


class GeofenceViolationAlert(BaseModel):
    """Alert when device exits geofence"""

    device_id: str
    agent_id: str
    current_latitude: float
    current_longitude: float
    geofence_center_lat: float
    geofence_center_lng: float
    distance_from_center_km: float
    radius_km: float
    timestamp: datetime


# =====================================================
# CONNECTION MANAGERS
# =====================================================


class WebSocketConnectionManager:
    def __init__(self):
        # agent_id -> { device_id -> WebSocket }
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, agent_id: str, device_id: Optional[str] = None):
        await websocket.accept()
        if agent_id not in self.active_connections:
            self.active_connections[agent_id] = {}

        key = device_id or str(id(websocket))  # fallback key if no device_id

        # Close old socket for this device if it exists
        old_ws = self.active_connections[agent_id].get(key)
        if old_ws and old_ws != websocket:
            try:
                await old_ws.close()
            except Exception:
                pass

        self.active_connections[agent_id][key] = websocket
        logger.info(f"WebSocket connected: agent={agent_id}, device={device_id}")

    def disconnect(self, websocket: WebSocket, agent_id: str):
        if agent_id in self.active_connections:
            # Find and remove this specific websocket
            keys_to_remove = [
                k for k, v in self.active_connections[agent_id].items()
                if v == websocket
            ]
            for k in keys_to_remove:
                del self.active_connections[agent_id][k]

            if not self.active_connections[agent_id]:
                del self.active_connections[agent_id]

    async def send_to_agent(self, agent_id: str, message: dict):
        if agent_id in self.active_connections:
            disconnected = []
            for device_id, connection in self.active_connections[agent_id].items():
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to agent {agent_id} device {device_id}: {e}")
                    disconnected.append(device_id)

            for key in disconnected:
                del self.active_connections[agent_id][key]

    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        for agent_id, devices in self.active_connections.items():
            for device_id, connection in devices.items():
                try:
                    await connection.send_json(message)
                except:
                    pass

class MQTTManager:
    """Manages MQTT connections"""

    def __init__(self):
        self.client = None
        self.connected = False

        if not MQTT_AVAILABLE:
            logger.warning("MQTT not available")
            return

        self.client = mqtt.Client(client_id=f"realtime-service-{uuid.uuid4()}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.connected = True
            # Subscribe to location updates topic
            client.subscribe("54agent/pos/+/location")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker: {rc}")
        self.connected = False

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            logger.info(f"MQTT message received: {topic}")

            # Handle location updates
            if "/location" in topic:
                # Extract device_id from topic: 54agent/pos/{device_id}/location
                device_id = topic.split("/")[2]
                # Process location update asynchronously
                asyncio.create_task(self._process_location_update(device_id, payload))

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    async def _process_location_update(self, device_id: str, payload: dict):
        """Process location update from MQTT — persist location, check geofences, emit violations."""
        try:
            lat = float(payload.get("latitude", 0))
            lng = float(payload.get("longitude", 0))
            if lat == 0 and lng == 0:
                return

            agent_id = payload.get("agent_id", "unknown")
            tenant_id = payload.get("tenant_id", DEFAULT_TENANT_ID)

            db: Session = SessionLocal()
            try:
                # 1. Persist location history
                location = POSDeviceLocation(
                    device_id=device_id,
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                    latitude=lat,
                    longitude=lng,
                    accuracy=payload.get("accuracy"),
                    speed=payload.get("speed"),
                    battery_level=payload.get("battery_level"),
                    timestamp=datetime.utcnow(),
                    is_within_geofence=True,  # updated below
                )

                # 2. Check all active geofences for this agent
                geofences = GeofenceService.get_agent_geofences(db, agent_id, tenant_id)
                any_violation = False

                for geofence in geofences:
                    is_within, distance_km = GeofenceService.check_geofence(
                        lat, lng,
                        geofence.center_latitude,
                        geofence.center_longitude,
                        geofence.radius_km,
                    )

                    if not is_within:
                        any_violation = True

                        # Record violation
                        violation = GeofenceViolation(
                            device_id=device_id,
                            agent_id=agent_id,
                            tenant_id=tenant_id,
                            geofence_id=geofence.id,
                            geofence_name=geofence.name or "Unnamed",
                            current_latitude=lat,
                            current_longitude=lng,
                            geofence_center_lat=geofence.center_latitude,
                            geofence_center_lng=geofence.center_longitude,
                            distance_from_center_km=distance_km,
                            radius_km=geofence.radius_km,
                            violation_time=datetime.utcnow(),
                        )
                        db.add(violation)

                        # Publish MQTT alert to device
                        alert = {
                            "type": "geofence_violation",
                            "device_id": device_id,
                            "agent_id": agent_id,
                            "geofence_id": str(geofence.id),
                            "geofence_name": geofence.name or "Unnamed",
                            "distance_km": round(distance_km, 4),
                            "radius_km": geofence.radius_km,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        self.publish_geofence_alert(device_id, alert)

                        # Push to WebSocket subscribers
                        await ws_manager.broadcast_to_tenant(tenant_id, {
                            "event": "geofence_violation",
                            **alert,
                        })

                location.is_within_geofence = not any_violation
                db.add(location)
                db.commit()

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error processing location update for {device_id}: {e}")

    def publish_transaction_ping(
        self, agent_id: str, device_id: str, transaction: dict
    ):
        """Publish transaction notification via MQTT"""
        if not self.connected:
            logger.warning("MQTT not connected, cannot publish")
            return False

        topic = f"54agent/pos/{device_id}/transaction"
        payload = json.dumps(transaction)

        result = self.client.publish(topic, payload, qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def publish_geofence_alert(self, device_id: str, alert: dict):
        """Publish geofence violation alert"""
        if not self.connected:
            return False

        topic = f"54agent/pos/{device_id}/geofence-alert"
        payload = json.dumps(alert)

        result = self.client.publish(topic, payload, qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS


# =====================================================
# SERVICE LAYER
# =====================================================


class GeofenceService:
    """Handles geofencing logic"""

    @staticmethod
    def check_geofence(
        current_lat: float,
        current_lng: float,
        geofence_lat: float,
        geofence_lng: float,
        radius_km: float,
    ) -> tuple[bool, float]:
        """
        Check if location is within geofence
        Returns: (is_within, distance_km)
        """
        distance_km = geodesic(
            (current_lat, current_lng), (geofence_lat, geofence_lng)
        ).kilometers

        is_within = distance_km <= radius_km
        return is_within, distance_km

    @staticmethod
    def get_agent_geofences(
        db: Session, agent_id: str, tenant_id: str
    ) -> List[POSGeofence]:
        """Get all active geofences for an agent"""
        return (
            db.query(POSGeofence)
            .filter(
                POSGeofence.agent_id == agent_id,
                POSGeofence.tenant_id == tenant_id,
                POSGeofence.is_active == True,
            )
            .all()
        )

    @staticmethod
    def create_geofence(db: Session, config: GeofenceConfig) -> POSGeofence:
        """Create new geofence"""
        geofence = POSGeofence(
            agent_id=config.agent_id,
            tenant_id=config.tenant_id,
            center_latitude=config.center_latitude,
            center_longitude=config.center_longitude,
            radius_km=config.radius_km,
            name=config.name,
        )
        db.add(geofence)
        db.commit()
        db.refresh(geofence)
        return geofence

    @staticmethod
    def get_geofence_by_id(db: Session, geofence_id: str) -> Optional[POSGeofence]:
        """Get a single geofence by ID"""
        return db.query(POSGeofence).filter(POSGeofence.id == geofence_id).first()

    @staticmethod
    def update_geofence(db: Session, geofence_id: str, data: dict) -> Optional[POSGeofence]:
        """Update an existing geofence"""
        geofence = db.query(POSGeofence).filter(POSGeofence.id == geofence_id).first()
        if not geofence:
            return None
        allowed = {"name", "center_latitude", "center_longitude", "radius_km", "is_active"}
        for key, value in data.items():
            if key in allowed:
                setattr(geofence, key, value)
        geofence.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(geofence)
        return geofence

    @staticmethod
    def delete_geofence(db: Session, geofence_id: str) -> bool:
        """Soft-delete (deactivate) a geofence"""
        geofence = db.query(POSGeofence).filter(POSGeofence.id == geofence_id).first()
        if not geofence:
            return False
        geofence.is_active = False
        geofence.updated_at = datetime.utcnow()
        db.commit()
        return True


# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(title="Real-time Notification Service")

# CORS
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
            "service": "realtime-notification-service",
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

# Connection managers
ws_manager = WebSocketConnectionManager()
mqtt_manager = MQTTManager()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# ENDPOINTS
# =====================================================


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "realtime-notification-service",
        "mqtt_connected": mqtt_manager.connected if mqtt_manager.client else False,
        "websocket_connections": sum(
    len(devices) for devices in ws_manager.active_connections.values()
),
    }


# =====================================================
# WEBSOCKET ENDPOINTS
# =====================================================


@app.websocket("/ws/{agent_id}")
async def websocket_endpoint(
    websocket: WebSocket, agent_id: str, device_id: Optional[str] = None
):
    """
    WebSocket endpoint for real-time communication
    Receives: location updates
    Sends: transaction pings, geofence alerts
    """
    await ws_manager.connect(websocket, agent_id, device_id)
    db = SessionLocal()

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "location_update":
                # Process location update
                location = LocationUpdate(**data.get("payload", {}))
                await handle_location_update(db, location, ws_manager)

            elif message_type == "ping":
                # Keep-alive ping
                await websocket.send_json(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                )

            elif message_type == "ack":
                # Acknowledgment of received message
                msg_id = data.get("message_id")
                logger.info(f"Received ack for message: {msg_id}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, agent_id)
        logger.info(f"WebSocket disconnected: agent={agent_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, agent_id)
    finally:
        db.close()


# =====================================================
# HTTP ENDPOINTS
# =====================================================


@app.post("/api/v1/location/update")
async def update_location(location: LocationUpdate, db: Session = Depends(get_db)):
    """HTTP endpoint for location updates (fallback if WebSocket unavailable)"""
    await handle_location_update(db, location, ws_manager)
    return {"status": "success", "message": "Location updated"}


@app.post("/api/v1/transaction/notify")
async def notify_transaction(
    transaction: TransactionPing,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None, alias="x-tenant-id"),
):
    """
    Webhook endpoint for transaction notifications
    Called by ledger/account service when money is received
    """
    logger.info(
        f"Transaction notification: {transaction.transaction_id} for agent {transaction.agent_id}"
    )

    # Save notification
    notification = TransactionNotification(
        transaction_id=transaction.transaction_id,
        agent_id=transaction.agent_id,
        tenant_id=transaction.tenant_id,
        amount=transaction.amount,
        transaction_type=transaction.transaction_type,
        sender_name=transaction.sender_name,
        account_number=transaction.account_number,
    )
    db.add(notification)
    db.commit()

    # Prepare ping message
    ping_message = {
        "type": "transaction_ping",
        "message_id": str(notification.id),
        "payload": {
            "transaction_id": transaction.transaction_id,
            "amount": transaction.amount,
            "transaction_type": transaction.transaction_type,
            "sender_name": transaction.sender_name,
            "account_number": transaction.account_number,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }

    # Send via WebSocket
    await ws_manager.send_to_agent(transaction.agent_id, ping_message)

    # Send via MQTT (if available)
    if mqtt_manager.connected:
        # Get all devices for this agent
        devices = (
            db.query(POSDeviceLocation.device_id)
            .filter(POSDeviceLocation.agent_id == transaction.agent_id)
            .distinct()
            .all()
        )

        for (device_id,) in devices:
            mqtt_manager.publish_transaction_ping(
                transaction.agent_id, device_id, ping_message["payload"]
            )

    # Update notification as delivered
    notification.was_delivered = True
    notification.delivered_at = datetime.utcnow()
    db.commit()

    return {
        "status": "success",
        "message": "Transaction notification sent",
        "notification_id": str(notification.id),
    }


class ApkUpdateNotification(BaseModel):
    """APK update notification sent from MDM service to agents"""
    agent_id: str
    tenant_id: str
    terminal_id: str
    model_id: str
    apk_variant: str
    new_version: str
    download_url: Optional[str] = None
    deployment_id: str


@app.post("/api/v1/apk/notify")
async def notify_apk_update(payload: ApkUpdateNotification):
    """
    Called by MDM service after queuing an APK deployment.
    Pushes an apk_update_available message to the agent via WebSocket.
    """
    message = {
        "type": "apk_update_available",
        "message_id": str(uuid.uuid4()),
        "payload": {
            "terminal_id": payload.terminal_id,
            "model_id": payload.model_id,
            "apk_variant": payload.apk_variant,
            "new_version": payload.new_version,
            "download_url": payload.download_url,
            "deployment_id": payload.deployment_id,
            "message": "A new update is available for your POS device",
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
    await ws_manager.send_to_agent(payload.agent_id, message)
    logger.info(
        f"APK update notification sent: agent={payload.agent_id}, "
        f"terminal={payload.terminal_id}, variant={payload.apk_variant}"
    )
    return {"status": "success", "message": "APK update notification sent"}


@app.post("/api/v1/geofence/create")
async def create_geofence(config: GeofenceConfig, db: Session = Depends(get_db)):
    """Create a new geofence for an agent"""
    geofence = GeofenceService.create_geofence(db, config)
    return {
        "status": "success",
        "geofence_id": str(geofence.id),
        "message": f"Geofence created with {config.radius_km}km radius",
    }


@app.get("/api/v1/geofence/list/{agent_id}")
async def list_geofences(agent_id: str, tenant_id: str, db: Session = Depends(get_db)):
    """List all geofences for an agent"""
    geofences = GeofenceService.get_agent_geofences(db, agent_id, tenant_id)
    return {
        "status": "success",
        "count": len(geofences),
        "geofences": [
            {
                "id": str(g.id),
                "name": g.name,
                "center_latitude": g.center_latitude,
                "center_longitude": g.center_longitude,
                "radius_km": g.radius_km,
                "is_active": g.is_active,
            }
            for g in geofences
        ],
    }


@app.get("/api/v1/geofence/{geofence_id}")
async def get_geofence(geofence_id: str, db: Session = Depends(get_db)):
    """Get a single geofence by ID"""
    geofence = GeofenceService.get_geofence_by_id(db, geofence_id)
    if not geofence:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {
        "id": str(geofence.id),
        "agent_id": geofence.agent_id,
        "tenant_id": geofence.tenant_id,
        "name": geofence.name,
        "center_latitude": geofence.center_latitude,
        "center_longitude": geofence.center_longitude,
        "radius_km": geofence.radius_km,
        "is_active": geofence.is_active,
        "created_at": geofence.created_at.isoformat(),
        "updated_at": geofence.updated_at.isoformat() if geofence.updated_at else None,
    }


@app.put("/api/v1/geofence/{geofence_id}")
async def update_geofence(geofence_id: str, data: dict, db: Session = Depends(get_db)):
    """Update geofence radius, center, name, or active state"""
    geofence = GeofenceService.update_geofence(db, geofence_id, data)
    if not geofence:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {
        "status": "success",
        "id": str(geofence.id),
        "name": geofence.name,
        "center_latitude": geofence.center_latitude,
        "center_longitude": geofence.center_longitude,
        "radius_km": geofence.radius_km,
        "is_active": geofence.is_active,
        "updated_at": geofence.updated_at.isoformat() if geofence.updated_at else None,
    }


@app.delete("/api/v1/geofence/{geofence_id}")
async def delete_geofence(geofence_id: str, db: Session = Depends(get_db)):
    """Deactivate a geofence (soft delete)"""
    deleted = GeofenceService.delete_geofence(db, geofence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {"status": "success", "message": "Geofence deactivated"}


@app.get("/api/v1/location/history/{device_id}")
async def get_location_history(
    device_id: str, hours: int = 24, limit: int = 100, db: Session = Depends(get_db)
):
    """Get location history for a device"""
    since = datetime.utcnow() - timedelta(hours=hours)
    locations = (
        db.query(POSDeviceLocation)
        .filter(
            POSDeviceLocation.device_id == device_id,
            POSDeviceLocation.timestamp >= since,
        )
        .order_by(POSDeviceLocation.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(loc.id),
            "device_id": loc.device_id,
            "agent_id": loc.agent_id,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "accuracy": loc.accuracy,
            "speed": loc.speed,
            "battery_level": loc.battery_level,
            "is_within_geofence": loc.is_within_geofence,
            "timestamp": loc.timestamp.isoformat(),
        }
        for loc in locations
    ]


# =====================================================
# ADMIN ENDPOINTS (Geofence Violation Monitoring)
# =====================================================


@app.get("/api/v1/admin/violations/active")
async def get_active_violations(
    tenant_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    hours: int = 24,
    limit: int = 100,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None, alias="x-tenant-id"),
):
    """
    Get active (unresolved) geofence violations
    Used by admin dashboard to monitor POS device movements
    """
    tenant_filter = tenant_id or x_tenant_id
    since = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(GeofenceViolation).filter(
        GeofenceViolation.was_resolved == False,
        GeofenceViolation.violation_time >= since,
    )

    if tenant_filter:
        query = query.filter(GeofenceViolation.tenant_id == tenant_filter)
    if agent_id:
        query = query.filter(GeofenceViolation.agent_id == agent_id)

    violations = (
        query.order_by(GeofenceViolation.violation_time.desc()).limit(limit).all()
    )

    return {
        "total": len(violations),
        "filters": {
            "hours": hours,
            "tenant_id": tenant_filter,
            "agent_id": agent_id,
        },
        "violations": [
            {
                "id": str(v.id),
                "device_id": v.device_id,
                "agent_id": v.agent_id,
                "tenant_id": v.tenant_id,
                "geofence_name": v.geofence_name,
                "current_latitude": v.current_latitude,
                "current_longitude": v.current_longitude,
                "geofence_center_lat": v.geofence_center_lat,
                "geofence_center_lng": v.geofence_center_lng,
                "distance_from_center_km": v.distance_from_center_km,
                "radius_km": v.radius_km,
                "violation_time": v.violation_time.isoformat(),
                "was_resolved": v.was_resolved,
                "admin_notes": v.admin_notes,
            }
            for v in violations
        ],
    }


@app.get("/api/v1/admin/violations/all")
async def get_all_violations(
    tenant_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    device_id: Optional[str] = None,
    days: int = 7,
    resolved: Optional[bool] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None, alias="x-tenant-id"),
):
    """Get all violations with filters (for admin reports)"""
    tenant_filter = tenant_id or x_tenant_id
    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(GeofenceViolation).filter(
        GeofenceViolation.violation_time >= since
    )

    if tenant_filter:
        query = query.filter(GeofenceViolation.tenant_id == tenant_filter)
    if agent_id:
        query = query.filter(GeofenceViolation.agent_id == agent_id)
    if device_id:
        query = query.filter(GeofenceViolation.device_id == device_id)
    if resolved is not None:
        query = query.filter(GeofenceViolation.was_resolved == resolved)

    violations = (
        query.order_by(GeofenceViolation.violation_time.desc()).limit(limit).all()
    )

    return {
        "total": len(violations),
        "filters": {
            "days": days,
            "tenant_id": tenant_filter,
            "resolved": resolved,
            "agent_id": agent_id,
            "device_id": device_id,
        },
        "violations": [
            {
                "id": str(v.id),
                "device_id": v.device_id,
                "agent_id": v.agent_id,
                "tenant_id": v.tenant_id,
                "geofence_name": v.geofence_name,
                "current_latitude": v.current_latitude,
                "current_longitude": v.current_longitude,
                "distance_from_center_km": v.distance_from_center_km,
                "radius_km": v.radius_km,
                "violation_time": v.violation_time.isoformat(),
                "was_resolved": v.was_resolved,
                "resolved_at": v.resolved_at.isoformat() if v.resolved_at else None,
                "admin_notes": v.admin_notes,
            }
            for v in violations
        ],
    }


@app.put("/api/v1/admin/violations/{violation_id}/resolve")
async def resolve_violation(
    violation_id: str, notes: Optional[str] = None, db: Session = Depends(get_db)
):
    """Mark a violation as resolved (admin action)"""
    try:
        violation = (
            db.query(GeofenceViolation)
            .filter(GeofenceViolation.id == uuid.UUID(violation_id))
            .first()
        )

        if not violation:
            raise HTTPException(status_code=404, detail="Violation not found")

        violation.was_resolved = True
        violation.resolved_at = datetime.utcnow()
        if notes:
            violation.admin_notes = notes

        db.commit()

        return {
            "status": "success",
            "violation_id": violation_id,
            "resolved_at": violation.resolved_at.isoformat(),
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid violation ID format")


@app.get("/api/v1/admin/violations/stats")
async def get_violation_stats(
    tenant_id: Optional[str] = None,
    days: int = 7,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(None, alias="x-tenant-id"),
):
    """Get violation statistics for admin dashboard"""
    tenant_filter = tenant_id or x_tenant_id
    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(GeofenceViolation).filter(
        GeofenceViolation.violation_time >= since
    )

    if tenant_filter:
        query = query.filter(GeofenceViolation.tenant_id == tenant_filter)

    total_violations = query.count()
    active_violations = query.filter(GeofenceViolation.was_resolved == False).count()
    resolved_violations = query.filter(GeofenceViolation.was_resolved == True).count()

    # Get violations per agent
    from sqlalchemy import func

    violations_by_agent = (
        db.query(
            GeofenceViolation.agent_id, func.count(GeofenceViolation.id).label("count")
        )
        .filter(GeofenceViolation.violation_time >= since)
        .group_by(GeofenceViolation.agent_id)
        .order_by(func.count(GeofenceViolation.id).desc())
        .limit(10)
        .all()
    )

    return {
        "period_days": days,
        "total_violations": total_violations,
        "active_violations": active_violations,
        "resolved_violations": resolved_violations,
        "top_agents": [
            {"agent_id": agent_id, "violation_count": count}
            for agent_id, count in violations_by_agent
        ],
    }


# =====================================================
# BUSINESS LOGIC
# =====================================================


async def handle_location_update(
    db: Session, location: LocationUpdate, ws_manager: WebSocketConnectionManager
):
    """Process location update and check geofences"""

    # Save location
    location_record = POSDeviceLocation(
        device_id=location.device_id,
        agent_id=location.agent_id,
        tenant_id=location.tenant_id,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy=location.accuracy,
        speed=location.speed,
        battery_level=location.battery_level,
    )

    # Check geofences
    geofences = GeofenceService.get_agent_geofences(
        db, location.agent_id, location.tenant_id
    )

    is_within_any = False
    alerts = []

    for geofence in geofences:
        is_within, distance_km = GeofenceService.check_geofence(
            location.latitude,
            location.longitude,
            geofence.center_latitude,
            geofence.center_longitude,
            geofence.radius_km,
        )

        if is_within:
            is_within_any = True
            break
        else:
            # Generate alert
            alert = GeofenceViolationAlert(
                device_id=location.device_id,
                agent_id=location.agent_id,
                current_latitude=location.latitude,
                current_longitude=location.longitude,
                geofence_center_lat=geofence.center_latitude,
                geofence_center_lng=geofence.center_longitude,
                distance_from_center_km=distance_km,
                radius_km=geofence.radius_km,
                timestamp=datetime.utcnow(),
            )
            alerts.append(alert)

    location_record.is_within_geofence = is_within_any
    db.add(location_record)
    db.commit()

    # Send alerts if outside geofence
    if not is_within_any and alerts:
        for alert in alerts:
            # Save violation to database for admin monitoring
            violation_record = GeofenceViolation(
                device_id=alert.device_id,
                agent_id=alert.agent_id,
                tenant_id=location.tenant_id,
                geofence_name=f"Geofence at {alert.geofence_center_lat:.4f}, {alert.geofence_center_lng:.4f}",
                current_latitude=alert.current_latitude,
                current_longitude=alert.current_longitude,
                geofence_center_lat=alert.geofence_center_lat,
                geofence_center_lng=alert.geofence_center_lng,
                distance_from_center_km=alert.distance_from_center_km,
                radius_km=alert.radius_km,
                violation_time=datetime.utcnow(),
            )
            db.add(violation_record)
            db.commit()

            alert_message = {
                "type": "geofence_violation",
                "payload": {**alert.dict(), "violation_id": str(violation_record.id)},
            }

            # Send via WebSocket to agent
            await ws_manager.send_to_agent(location.agent_id, alert_message)

            # Send via WebSocket to all connected admins (broadcast)
            await ws_manager.broadcast_to_tenant(
                location.tenant_id,
                {
                    "type": "admin_geofence_violation",
                    "payload": {
                        "violation_id": str(violation_record.id),
                        "device_id": alert.device_id,
                        "agent_id": alert.agent_id,
                        "distance_km": alert.distance_from_center_km,
                        "radius_km": alert.radius_km,
                        "timestamp": alert.timestamp.isoformat(),
                    },
                },
            )

            # Send via MQTT
            if mqtt_manager.connected:
                mqtt_manager.publish_geofence_alert(
                    location.device_id, alert_message["payload"]
                )

            logger.warning(
                f"Geofence violation: device={location.device_id}, "
                f"distance={alert.distance_from_center_km:.2f}km, "
                f"allowed={alert.radius_km}km, violation_id={violation_record.id}"
            )

    return location_record


# =====================================================
# ACCOUNT SERVICE INTEGRATION
# =====================================================


async def get_account_by_id(
    account_id: str, tenant_id: str, headers: Optional[Dict[str, str]] = None
) -> Optional[Dict]:
    """
    Fetch account details from the account service to get keycloak_id

    Args:
        account_id: The account ID to fetch
        tenant_id: The tenant ID for the request headers
        headers: Optional headers to pass to the account service

    Returns:
        Account data if found, None otherwise
    """
    try:
        url = f"{ACCOUNT_SERVICE_URL}/account/{account_id}"

        # Prepare headers
        request_headers = {"x-tenant-id": tenant_id, "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=request_headers)

            if response.status_code == 200:
                data = response.json()
                account = data.get("account")
                if account:
                    logger.info(
                        f"Retrieved account {account_id}: keycloak_id={account.get('keycloak_id')}"
                    )
                    return account
                else:
                    logger.warning(
                        f"No account data in response for account_id={account_id}"
                    )
                    return None
            else:
                logger.warning(
                    f"Failed to fetch account {account_id}: status={response.status_code}"
                )
                return None

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching account {account_id} from account service")
        return None
    except Exception as e:
        logger.error(f"Error fetching account {account_id}: {e}", exc_info=True)
        return None


# =====================================================
# DAPR PUBSUB SUBSCRIBERS
# =====================================================


@app.get("/dapr/subscribe")
async def dapr_subscribe():
    """
    Dapr pubsub subscription endpoint
    Tells Dapr which topics this service wants to subscribe to
    """
    subscriptions = [
        {
            "pubsubname": os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
            "topic": "transaction_initiated",
            "route": "/events/transaction-initiated",
        }
    ]
    logger.info(f"Dapr subscriptions registered: {subscriptions}")
    return subscriptions


@app.post("/events/transaction-initiated")
async def handle_transaction_event(request: dict, db: Session = Depends(get_db)):
    """
    Dapr pubsub event handler for new transactions
    Automatically called by Dapr when a transaction event is published
    """
    try:
        # Extract event data from Dapr CloudEvent format
        event_data = request.get("data", {})

        # Parse if it's a JSON string
        if isinstance(event_data, str):
            event_data = json.loads(event_data)

        logger.info(f"Received transaction event: {event_data}")

        # Extract transaction details
        transaction_id = event_data.get("transaction_id")
        amount = float(event_data.get("amount", 0))
        payee = event_data.get("payee")
        payer = event_data.get("payer")
        tenant_id = event_data.get("tenant_id")
        transaction_type = "credit"  # Money received

        # Skip if there's no recipient to notify
        if not payee:
            logger.info(
                f"Skipping notification - no payee for transaction: {transaction_id}"
            )
            return {
                "status": "success",
                "message": "No payee to notify",
            }

        # Fetch account details to get keycloak_id
        account = await get_account_by_id(payee, tenant_id)

        if not account:
            logger.warning(
                f"Could not fetch account details for payee {payee}, skipping notification"
            )
            return {
                "status": "success",
                "message": "Account not found",
            }

        # Extract keycloak_id from account
        agent_id = account.get("keycloak_id")

        if not agent_id:
            logger.warning(
                f"No keycloak_id found for account {payee}, skipping notification"
            )
            return {
                "status": "success",
                "message": "No keycloak_id for account",
            }

        # Note: We DO send notifications for deposits (MINT_ACCOUNT -> Agent)
        # Agents should know when money is deposited into their account!

        # Check if notification already exists for this transaction_id (deduplication)
        existing_notification = (
            db.query(TransactionNotification)
            .filter(TransactionNotification.transaction_id == transaction_id)
            .first()
        )

        if existing_notification:
            logger.info(
                f"Notification already exists for transaction {transaction_id}, skipping duplicate"
            )
            return {
                "status": "success",
                "message": "Notification already processed (duplicate)",
                "notification_id": str(existing_notification.id),
            }

        # Create notification payload
        transaction_ping = TransactionPing(
            transaction_id=transaction_id,
            agent_id=agent_id,  # Using keycloak_id from account service
            tenant_id=tenant_id,
            amount=amount,
            transaction_type=transaction_type,
            sender_name=payer,
            account_number=payee,
        )

        # Save notification to database
        notification = TransactionNotification(
            transaction_id=transaction_ping.transaction_id,
            agent_id=transaction_ping.agent_id,
            tenant_id=transaction_ping.tenant_id,
            amount=transaction_ping.amount,
            transaction_type=transaction_ping.transaction_type,
            sender_name=transaction_ping.sender_name,
            account_number=transaction_ping.account_number,
        )
        db.add(notification)
        db.commit()

        # Prepare ping message for WebSocket
        ping_message = {
            "type": "transaction_ping",
            "message_id": str(notification.id),
            "payload": {
                "transaction_id": transaction_ping.transaction_id,
                "amount": transaction_ping.amount,
                "transaction_type": transaction_ping.transaction_type,
                "sender_name": transaction_ping.sender_name,
                "account_number": transaction_ping.account_number,
                "timestamp": datetime.utcnow().isoformat(),
                "currency": "NGN",
            },
        }

        # Send via WebSocket to agent
        await ws_manager.send_to_agent(transaction_ping.agent_id, ping_message)
        logger.info(
            f"Transaction notification sent to agent {transaction_ping.agent_id}"
        )

        # Send via MQTT (if available) to all agent's devices
        if mqtt_manager.connected:
            devices = (
                db.query(POSDeviceLocation.device_id)
                .filter(POSDeviceLocation.agent_id == transaction_ping.agent_id)
                .distinct()
                .all()
            )

            for (device_id,) in devices:
                mqtt_manager.publish_transaction_ping(
                    transaction_ping.agent_id, device_id, ping_message["payload"]
                )

        # Mark as delivered
        notification.was_delivered = True
        notification.delivered_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "message": "Transaction notification processed",
            "notification_id": str(notification.id),
        }

    except Exception as e:
        logger.error(f"Error processing transaction event: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


# =====================================================
# EMAIL SERVICE ROUTES
# =====================================================

from email_service import (
    send_email as _send_email,
    send_batch_email as _send_batch_email,
    get_provider_status,
    build_welcome_email,
    build_password_reset_email,
    build_rate_alert_email,
    build_digest_email,
    extract_email_from_string,
    EmailMessage,
)


class SendEmailRequest(BaseModel):
    to: Union[str, List[str]]
    subject: str
    html: str
    text: Optional[str] = ""


class BatchEmailRequest(BaseModel):
    recipients: List[str]
    subject: str
    html: str
    batch_size: int = 50
    delay_ms: int = 0


class WelcomeEmailRequest(BaseModel):
    recipient: str
    name: str
    tenant_name: str = "54agent"


class PasswordResetEmailRequest(BaseModel):
    recipient: str
    otp: str
    expiry_minutes: int = 15


class RateAlertEmailRequest(BaseModel):
    recipient: str
    currency_pair: str
    direction: str
    current_rate: float
    threshold: float


class DigestEmailRequest(BaseModel):
    recipient: str
    period: str
    tx_count: int
    items: List[dict] = []


@app.post("/api/v1/email/send")
def route_send_email(req: SendEmailRequest):
    msg = EmailMessage(to=req.to, subject=req.subject, html=req.html, text=req.text or "")
    return _send_email(msg)


@app.post("/api/v1/email/send-batch")
def route_send_batch(req: BatchEmailRequest):
    results = _send_batch_email(
        req.recipients, subject=req.subject, html=req.html,
        batch_size=req.batch_size, delay_ms=req.delay_ms,
    )
    return {"sent": len(results), "results": results}


@app.get("/api/v1/email/providers")
def route_provider_status():
    return {"providers": get_provider_status()}


@app.post("/api/v1/email/send-welcome")
def route_send_welcome(req: WelcomeEmailRequest):
    msg = build_welcome_email(req.recipient, req.name, req.tenant_name)
    return _send_email(msg)


@app.post("/api/v1/email/send-password-reset")
def route_send_password_reset(req: PasswordResetEmailRequest):
    msg = build_password_reset_email(req.recipient, req.otp, req.expiry_minutes)
    return _send_email(msg)


@app.post("/api/v1/email/send-rate-alert")
def route_send_rate_alert(req: RateAlertEmailRequest):
    msg = build_rate_alert_email(
        req.recipient, req.currency_pair, req.direction, req.current_rate, req.threshold
    )
    return _send_email(msg)


@app.post("/api/v1/email/send-digest")
def route_send_digest(req: DigestEmailRequest):
    msg = build_digest_email(req.recipient, req.period, req.tx_count, req.items)
    return _send_email(msg)


@app.get("/api/v1/email/extract")
def route_extract_email(text: str):
    return {"email": extract_email_from_string(text)}


# =====================================================
# STARTUP
# =====================================================


@app.on_event("startup")
async def startup_event():
    logger.info("Real-time Notification Service starting...")
    logger.info(f"MQTT: {'Connected' if mqtt_manager.connected else 'Not available'}")
    logger.info(
        f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'configured'}"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8094)
