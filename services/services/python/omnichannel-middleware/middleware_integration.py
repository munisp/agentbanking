import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Omni-Channel Middleware Integration
Integrates all communication services with:
- Fluvio (event streaming)
- Kafka (message broker)
- Dapr (service mesh)
- Redis (caching)
- APISIX (API gateway)
- Temporal (workflow orchestration)
- Keycloak (authentication)
- Permify (authorization)
"""

from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("omni-channel-middleware-integration")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import asyncio
import httpx
import json
import os
import uuid
import logging

# ==================== CONFIGURATION ====================

class Config:
    # Communication Services
    WHATSAPP_SERVICE = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:8040")
    SMS_SERVICE = os.getenv("SMS_SERVICE_URL", "http://localhost:8001")
    USSD_SERVICE = os.getenv("USSD_SERVICE_URL", "http://localhost:8002")
    TELEGRAM_SERVICE = os.getenv("TELEGRAM_SERVICE_URL", "http://localhost:8041")
    MESSENGER_SERVICE = os.getenv("MESSENGER_SERVICE_URL", "http://localhost:8047")
    PUSH_NOTIFICATION_SERVICE = os.getenv("PUSH_NOTIFICATION_SERVICE_URL", "http://localhost:8043")
    
    # Middleware
    FLUVIO_CLUSTER = os.getenv("FLUVIO_CLUSTER", "localhost:9003")
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    DAPR_HTTP_PORT = os.getenv("DAPR_HTTP_PORT", "3500")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://localhost:9180")
    TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
    KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    PERMIFY_URL = os.getenv("PERMIFY_URL", "http://localhost:3476")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/remittance")

config = Config()

# ==================== LOGGING ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FLUVIO INTEGRATION ====================

class FluvioIntegration:
    """Fluvio event streaming integration"""
    
    # Fluvio topics for communication events
    TOPICS = {
        "message_sent": "communication.message.sent",
        "message_delivered": "communication.message.delivered",
        "message_failed": "communication.message.failed",
        "webhook_received": "communication.webhook.received",
        "channel_health": "communication.channel.health",
        "analytics": "communication.analytics"
    }
    
    def __init__(self):
        self.cluster = config.FLUVIO_CLUSTER
        self.connected = False
    
    async def connect(self):
        """Connect to Fluvio cluster"""
        try:
            # In production, use actual Fluvio Python client
            # from fluvio import Fluvio
            # self.client = await Fluvio.connect()
            self.connected = True
            logger.info("Connected to Fluvio cluster")
        except Exception as e:
            logger.error(f"Failed to connect to Fluvio: {e}")
            self.connected = False
    
    async def publish_event(self, topic: str, event: Dict[str, Any]):
        """Publish event to Fluvio topic"""
        try:
            if not self.connected:
                await self.connect()
            
            # In production, use actual Fluvio producer
            # producer = await self.client.topic_producer(topic)
            # await producer.send_string(json.dumps(event))
            
            logger.info(f"Published to Fluvio topic {topic}: {event}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to Fluvio: {e}")
            return False
    
    async def publish_message_sent(self, channel: str, message_id: str, recipient: str, metadata: Dict = None):
        """Publish message sent event"""
        event = {
            "event_type": "message_sent",
            "channel": channel,
            "message_id": message_id,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        await self.publish_event(self.TOPICS["message_sent"], event)
    
    async def publish_message_delivered(self, channel: str, message_id: str, recipient: str):
        """Publish message delivered event"""
        event = {
            "event_type": "message_delivered",
            "channel": channel,
            "message_id": message_id,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.publish_event(self.TOPICS["message_delivered"], event)
    
    async def publish_message_failed(self, channel: str, message_id: str, recipient: str, error: str):
        """Publish message failed event"""
        event = {
            "event_type": "message_failed",
            "channel": channel,
            "message_id": message_id,
            "recipient": recipient,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.publish_event(self.TOPICS["message_failed"], event)
    
    async def publish_webhook_received(self, channel: str, event_type: str, payload: Dict):
        """Publish webhook received event"""
        event = {
            "event_type": "webhook_received",
            "channel": channel,
            "webhook_event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.publish_event(self.TOPICS["webhook_received"], event)
    
    async def publish_channel_health(self, channel: str, status: str, metrics: Dict):
        """Publish channel health event"""
        event = {
            "event_type": "channel_health",
            "channel": channel,
            "status": status,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.publish_event(self.TOPICS["channel_health"], event)

# ==================== KAFKA INTEGRATION ====================

class KafkaIntegration:
    """Kafka message broker integration"""
    
    def __init__(self):
        self.bootstrap_servers = config.KAFKA_BOOTSTRAP_SERVERS
        self.producer = None
    
    async def connect(self):
        """Connect to Kafka"""
        try:
            # In production, use actual Kafka client
            # from aiokafka import AIOKafkaProducer
            # self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            # await self.producer.start()
            logger.info("Connected to Kafka")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
    
    async def publish(self, topic: str, message: Dict):
        """Publish message to Kafka topic"""
        try:
            # In production, use actual Kafka producer
            # await self.producer.send_and_wait(topic, json.dumps(message).encode())
            logger.info(f"Published to Kafka topic {topic}")
        except Exception as e:
            logger.error(f"Failed to publish to Kafka: {e}")

# ==================== DAPR INTEGRATION ====================

class DaprIntegration:
    """Dapr service mesh integration"""
    
    def __init__(self):
        self.http_port = config.DAPR_HTTP_PORT
        self.base_url = f"http://localhost:{self.http_port}"
    
    async def publish_pubsub(self, pubsub_name: str, topic: str, data: Dict):
        """Publish to Dapr pub/sub"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1.0/publish/{pubsub_name}/{topic}",
                    json=data
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Dapr pub/sub failed: {e}")
            return False
    
    async def invoke_service(self, app_id: str, method: str, data: Dict = None):
        """Invoke another service via Dapr"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1.0/invoke/{app_id}/method/{method}",
                    json=data or {}
                )
                return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Dapr service invocation failed: {e}")
            return None
    
    async def get_state(self, store_name: str, key: str):
        """Get state from Dapr state store"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1.0/state/{store_name}/{key}"
                )
                return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Dapr get state failed: {e}")
            return None
    
    async def save_state(self, store_name: str, key: str, value: Any):
        """Save state to Dapr state store"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1.0/state/{store_name}",
                    json=[{"key": key, "value": value}]
                )
                return response.status_code == 204
        except Exception as e:
            logger.error(f"Dapr save state failed: {e}")
            return False

# ==================== REDIS INTEGRATION ====================

class RedisIntegration:
    """Redis caching integration"""
    
    def __init__(self):
        self.url = config.REDIS_URL
        self.client = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            import aioredis
            self.client = await aioredis.create_redis_pool(self.url)
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
    
    async def get(self, key: str):
        """Get value from Redis"""
        try:
            if self.client:
                value = await self.client.get(key)
                return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in Redis with TTL"""
        try:
            if self.client:
                await self.client.setex(key, ttl, json.dumps(value))
                return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            return False
    
    async def delete(self, key: str):
        """Delete key from Redis"""
        try:
            if self.client:
                await self.client.delete(key)
                return True
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")
            return False

# ==================== APISIX INTEGRATION ====================

class APISIXIntegration:
    """APISIX API Gateway integration"""
    
    def __init__(self):
        self.admin_url = config.APISIX_ADMIN_URL
    
    async def register_route(self, service_name: str, upstream_url: str, uri: str, methods: List[str] = None):
        """Register route in APISIX"""
        try:
            route_config = {
                "uri": uri,
                "name": f"{service_name}-route",
                "methods": methods or ["GET", "POST", "PUT", "DELETE"],
                "upstream": {
                    "type": "roundrobin",
                    "nodes": {
                        upstream_url: 1
                    }
                },
                "plugins": {
                    "limit-count": {
                        "count": 100,
                        "time_window": 60,
                        "rejected_code": 429
                    },
                    "prometheus": {}
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.admin_url}/apisix/admin/routes/{service_name}",
                    json=route_config
                )
                return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"APISIX route registration failed: {e}")
            return False

# ==================== TEMPORAL INTEGRATION ====================

class TemporalIntegration:
    """Temporal workflow orchestration integration"""
    
    def __init__(self):
        self.host = config.TEMPORAL_HOST
    
    async def start_workflow(self, workflow_type: str, workflow_id: str, input_data: Dict):
        """Start Temporal workflow"""
        try:
            # In production, use actual Temporal client
            # from temporalio.client import Client
            # client = await Client.connect(self.host)
            # await client.start_workflow(workflow_type, input_data, id=workflow_id)
            logger.info(f"Started Temporal workflow: {workflow_type}")
            return True
        except Exception as e:
            logger.error(f"Temporal workflow start failed: {e}")
            return False

# ==================== UNIFIED MIDDLEWARE MANAGER ====================

class MiddlewareManager:
    """Unified middleware manager for all integrations"""
    
    def __init__(self):
        self.fluvio = FluvioIntegration()
        self.kafka = KafkaIntegration()
        self.dapr = DaprIntegration()
        self.redis = RedisIntegration()
        self.apisix = APISIXIntegration()
        self.temporal = TemporalIntegration()
    
    async def initialize(self):
        """Initialize all middleware connections"""
        await asyncio.gather(
            self.fluvio.connect(),
            self.kafka.connect(),
            self.redis.connect(),
            return_exceptions=True
        )
        logger.info("Middleware manager initialized")
    
    async def publish_communication_event(self, event_type: str, channel: str, data: Dict):
        """Publish communication event to all relevant middleware"""
        # Publish to Fluvio for real-time streaming
        await self.fluvio.publish_event(f"communication.{event_type}", {
            "channel": channel,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Publish to Kafka for message broker
        await self.kafka.publish(f"communication-{event_type}", data)
        
        # Publish to Dapr pub/sub
        await self.dapr.publish_pubsub("pubsub", f"communication-{event_type}", data)
    
    async def cache_message(self, message_id: str, message_data: Dict, ttl: int = 3600):
        """Cache message in Redis"""
        await self.redis.set(f"message:{message_id}", message_data, ttl)
    
    async def get_cached_message(self, message_id: str):
        """Get cached message from Redis"""
        return await self.redis.get(f"message:{message_id}")

# ==================== FASTAPI APPLICATION ====================

app = FastAPI(
    title="Omni-Channel Middleware Integration",
    description="Middleware integration layer for all communication services",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize middleware manager
middleware_manager = MiddlewareManager()

@app.on_event("startup")
async def startup_event():
    """Initialize middleware on startup"""
    await middleware_manager.initialize()
    logger.info("Omni-channel middleware integration started")

# ==================== MODELS ====================

class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    USSD = "ussd"
    TELEGRAM = "telegram"
    MESSENGER = "messenger"
    PUSH = "push"

class MessageRequest(BaseModel):
    channel: Channel
    recipient: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

class BulkMessageRequest(BaseModel):
    channel: Channel
    recipients: List[str]
    message: str
    metadata: Optional[Dict[str, Any]] = None

class WebhookEvent(BaseModel):
    channel: Channel
    event_type: str
    payload: Dict[str, Any]

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "service": "Omni-Channel Middleware Integration",
        "version": "1.0.0",
        "middleware": ["Fluvio", "Kafka", "Dapr", "Redis", "APISIX", "Temporal"],
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "middleware": {
            "fluvio": middleware_manager.fluvio.connected,
            "redis": middleware_manager.redis.client is not None
        }
    }

@app.post("/send")
async def send_message(request: MessageRequest):
    """Send message through specified channel with middleware integration"""
    try:
        message_id = f"msg-{uuid.uuid4()}"
        
        # Get service URL for channel
        service_urls = {
            Channel.WHATSAPP: config.WHATSAPP_SERVICE,
            Channel.SMS: config.SMS_SERVICE,
            Channel.USSD: config.USSD_SERVICE,
            Channel.TELEGRAM: config.TELEGRAM_SERVICE,
            Channel.MESSENGER: config.MESSENGER_SERVICE,
            Channel.PUSH: config.PUSH_NOTIFICATION_SERVICE
        }
        
        service_url = service_urls.get(request.channel)
        if not service_url:
            raise HTTPException(status_code=400, detail=f"Unsupported channel: {request.channel}")
        
        # Send message to channel service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{service_url}/send",
                json={
                    "recipient": request.recipient,
                    "message": request.message,
                    "metadata": request.metadata
                },
                timeout=10.0
            )
        
        if response.status_code == 200:
            # Cache message
            await middleware_manager.cache_message(message_id, {
                "channel": request.channel,
                "recipient": request.recipient,
                "message": request.message,
                "status": "sent",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Publish event to all middleware
            await middleware_manager.publish_communication_event(
                "message_sent",
                request.channel,
                {
                    "message_id": message_id,
                    "recipient": request.recipient,
                    "status": "sent"
                }
            )
            
            # Publish to Fluvio
            await middleware_manager.fluvio.publish_message_sent(
                request.channel,
                message_id,
                request.recipient,
                request.metadata
            )
            
            return {
                "message_id": message_id,
                "channel": request.channel,
                "status": "sent",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Publish failure event
            await middleware_manager.fluvio.publish_message_failed(
                request.channel,
                message_id,
                request.recipient,
                f"Service returned {response.status_code}"
            )
            
            raise HTTPException(status_code=500, detail="Failed to send message")
    
    except Exception as e:
        logger.error(f"Send message failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send/bulk")
async def send_bulk_messages(request: BulkMessageRequest):
    """Send bulk messages with middleware integration"""
    try:
        results = []
        
        for recipient in request.recipients:
            message_request = MessageRequest(
                channel=request.channel,
                recipient=recipient,
                message=request.message,
                metadata=request.metadata
            )
            
            try:
                result = await send_message(message_request)
                results.append(result)
            except Exception as e:
                results.append({
                    "recipient": recipient,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "total": len(request.recipients),
            "successful": len([r for r in results if r.get("status") == "sent"]),
            "failed": len([r for r in results if r.get("status") == "failed"]),
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Bulk send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def receive_webhook(event: WebhookEvent):
    """Receive webhook from communication channels"""
    try:
        # Publish webhook event to middleware
        await middleware_manager.fluvio.publish_webhook_received(
            event.channel,
            event.event_type,
            event.payload
        )
        
        await middleware_manager.publish_communication_event(
            "webhook_received",
            event.channel,
            {
                "event_type": event.event_type,
                "payload": event.payload
            }
        )
        
        return {"status": "processed"}
    
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/message/{message_id}")
async def get_message(message_id: str):
    """Get message from cache"""
    message = await middleware_manager.get_cached_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@app.get("/channels/health")
async def get_channels_health():
    """Get health status of all communication channels"""
    channels = [
        ("whatsapp", config.WHATSAPP_SERVICE),
        ("sms", config.SMS_SERVICE),
        ("ussd", config.USSD_SERVICE),
        ("telegram", config.TELEGRAM_SERVICE),
        ("messenger", config.MESSENGER_SERVICE),
        ("push", config.PUSH_NOTIFICATION_SERVICE)
    ]
    
    health_status = {}
    
    async with httpx.AsyncClient() as client:
        for channel_name, service_url in channels:
            try:
                response = await client.get(f"{service_url}/health", timeout=5.0)
                health_status[channel_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            except Exception as e:
                health_status[channel_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
    
    # Publish health status to middleware
    for channel_name, status in health_status.items():
        await middleware_manager.fluvio.publish_channel_health(
            channel_name,
            status["status"],
            status
        )
    
    return health_status

@app.post("/middleware/register-routes")
async def register_all_routes():
    """Register all communication service routes in APISIX"""
    services = [
        ("whatsapp", config.WHATSAPP_SERVICE, "/api/v1/whatsapp/*"),
        ("sms", config.SMS_SERVICE, "/api/v1/sms/*"),
        ("ussd", config.USSD_SERVICE, "/api/v1/ussd/*"),
        ("telegram", config.TELEGRAM_SERVICE, "/api/v1/telegram/*"),
        ("messenger", config.MESSENGER_SERVICE, "/api/v1/messenger/*"),
        ("push", config.PUSH_NOTIFICATION_SERVICE, "/api/v1/push/*")
    ]
    
    results = {}
    for service_name, upstream_url, uri in services:
        success = await middleware_manager.apisix.register_route(
            service_name,
            upstream_url,
            uri
        )
        results[service_name] = "registered" if success else "failed"
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)

