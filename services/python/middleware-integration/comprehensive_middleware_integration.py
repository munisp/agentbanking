import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Middleware Integration Layer
Integrates Kafka, Dapr, Fluvio, Temporal, Keycloak, Permify, Redis, APISIX
Port: 8026
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("comprehensive-middleware-integration-layer")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio
import httpx
import json
import os

# Kafka
try:
    from kafka import KafkaProducer, KafkaConsumer
    KAFKA_AVAILABLE = True
except:
    KAFKA_AVAILABLE = False

# Redis
import redis

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
FLUVIO_CLUSTER = os.getenv("FLUVIO_CLUSTER", "localhost:9003")
DAPR_HTTP_PORT = os.getenv("DAPR_HTTP_PORT", "3500")
DAPR_GRPC_PORT = os.getenv("DAPR_GRPC_PORT", "50001")
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "remittance")
PERMIFY_URL = os.getenv("PERMIFY_URL", "http://localhost:3476")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://localhost:9180")
APISIX_ADMIN_KEY = os.getenv("APISIX_ADMIN_KEY", "")

# Initialize Redis
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=4,
    decode_responses=True
)

# Initialize Kafka Producer
kafka_producer = None
if KAFKA_AVAILABLE:
    try:
        kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    except:
        pass

# ==================== PYDANTIC MODELS ====================

class EventPublish(BaseModel):
    topic: str
    event_type: str
    data: Dict[str, Any]
    middleware: str = "kafka"  # kafka, fluvio, dapr

class PermissionCheck(BaseModel):
    user_id: str
    resource: str
    action: str

class CacheSet(BaseModel):
    key: str
    value: Any
    ttl: Optional[int] = 3600

# ==================== HELPER FUNCTIONS ====================

async def publish_to_kafka(topic: str, message: Dict) -> bool:
    """Publish message to Kafka"""
    if not kafka_producer:
        return False
    
    try:
        kafka_producer.send(topic, message)
        kafka_producer.flush()
        return True
    except Exception as e:
        print(f"Kafka publish failed: {e}")
        return False

async def publish_to_dapr(topic: str, message: Dict) -> bool:
    """Publish message via Dapr pub/sub"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/pubsub/{topic}",
                json=message,
                timeout=10.0
            )
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"Dapr publish failed: {e}")
        return False

async def publish_to_fluvio(topic: str, message: Dict) -> bool:
    """Publish message to Fluvio"""
    try:
        # Fluvio CLI-based publishing (in production, use Python client)
        import subprocess
        result = subprocess.run(
            ["fluvio", "produce", topic],
            input=json.dumps(message).encode(),
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Fluvio publish failed: {e}")
        return False

async def verify_keycloak_token(token: str) -> Optional[Dict]:
    """Verify JWT token with Keycloak"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token/introspect",
                data={"token": token},
                timeout=10.0
            )
            response.raise_for_status()
            token_info = response.json()
            
            if token_info.get("active"):
                return token_info
            return None
    except Exception as e:
        print(f"Keycloak verification failed: {e}")
        return None

async def check_permission_permify(user_id: str, resource: str, action: str) -> bool:
    """Check permission using Permify"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PERMIFY_URL}/v1/permissions/check",
                json={
                    "entity": {
                        "type": "user",
                        "id": user_id
                    },
                    "permission": action,
                    "subject": {
                        "type": "resource",
                        "id": resource
                    }
                },
                timeout=10.0
            )
            response.raise_for_status()
            result = response.json()
            return result.get("can", False)
    except Exception as e:
        print(f"Permify check failed: {e}")
        return False

async def register_apisix_route(route_config: Dict) -> bool:
    """Register route in APISIX"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{APISIX_ADMIN_URL}/apisix/admin/routes/{route_config['id']}",
                json=route_config,
                headers={"X-API-KEY": APISIX_ADMIN_KEY},
                timeout=10.0
            )
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"APISIX route registration failed: {e}")
        return False

# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Comprehensive Middleware Integration Layer",
    description="Integrates Kafka, Dapr, Fluvio, Temporal, Keycloak, Permify, Redis, APISIX",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check with middleware status"""
    
    # Check Redis
    redis_healthy = False
    try:
        redis_client.ping()
        redis_healthy = True
    except:
        pass
    
    # Check Kafka
    kafka_healthy = kafka_producer is not None
    
    # Check Dapr
    dapr_healthy = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{DAPR_HTTP_PORT}/v1.0/healthz", timeout=5.0)
            dapr_healthy = response.status_code == 200
    except:
        pass
    
    return {
        "status": "healthy",
        "service": "middleware-integration",
        "version": "1.0.0",
        "port": 8026,
        "middleware_status": {
            "kafka": kafka_healthy,
            "redis": redis_healthy,
            "dapr": dapr_healthy,
            "fluvio": "configured",
            "temporal": "configured",
            "keycloak": bool(KEYCLOAK_URL),
            "permify": bool(PERMIFY_URL),
            "apisix": bool(APISIX_ADMIN_KEY)
        },
        "features": [
            "event_streaming",
            "pub_sub",
            "caching",
            "authentication",
            "authorization",
            "api_gateway",
            "workflow_orchestration"
        ]
    }

@app.post("/events/publish")
async def publish_event(event: EventPublish):
    """Publish event to middleware"""
    
    message = {
        "event_id": str(uuid.uuid4()),
        "event_type": event.event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": event.data
    }
    
    success = False
    
    if event.middleware == "kafka":
        success = await publish_to_kafka(event.topic, message)
    elif event.middleware == "dapr":
        success = await publish_to_dapr(event.topic, message)
    elif event.middleware == "fluvio":
        success = await publish_to_fluvio(event.topic, message)
    else:
        raise HTTPException(status_code=400, detail="Invalid middleware")
    
    if not success:
        raise HTTPException(status_code=500, detail="Event publish failed")
    
    return {
        "event_id": message["event_id"],
        "status": "published",
        "middleware": event.middleware,
        "topic": event.topic
    }

@app.post("/cache/set")
async def cache_set(cache_data: CacheSet):
    """Set cache value in Redis"""
    
    try:
        redis_client.setex(
            cache_data.key,
            cache_data.ttl,
            json.dumps(cache_data.value)
        )
        return {"key": cache_data.key, "status": "cached", "ttl": cache_data.ttl}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache set failed: {str(e)}")

@app.get("/cache/get/{key}")
async def cache_get(key: str):
    """Get cache value from Redis"""
    
    try:
        value = redis_client.get(key)
        if value:
            return {"key": key, "value": json.loads(value), "found": True}
        return {"key": key, "found": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache get failed: {str(e)}")

@app.delete("/cache/delete/{key}")
async def cache_delete(key: str):
    """Delete cache value from Redis"""
    
    try:
        deleted = redis_client.delete(key)
        return {"key": key, "deleted": bool(deleted)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache delete failed: {str(e)}")

@app.post("/auth/verify")
async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify JWT token with Keycloak"""
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    token_info = await verify_keycloak_token(token)
    
    if not token_info:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return {
        "valid": True,
        "user_id": token_info.get("sub"),
        "username": token_info.get("preferred_username"),
        "email": token_info.get("email"),
        "roles": token_info.get("realm_access", {}).get("roles", [])
    }

@app.post("/permissions/check")
async def check_permission(permission: PermissionCheck):
    """Check permission using Permify"""
    
    allowed = await check_permission_permify(
        permission.user_id,
        permission.resource,
        permission.action
    )
    
    return {
        "user_id": permission.user_id,
        "resource": permission.resource,
        "action": permission.action,
        "allowed": allowed
    }

@app.post("/gateway/routes")
async def create_gateway_route(
    route_id: str,
    upstream_url: str,
    path: str,
    methods: List[str] = ["GET", "POST"]
):
    """Create API Gateway route in APISIX"""
    
    route_config = {
        "id": route_id,
        "uri": path,
        "methods": methods,
        "upstream": {
            "type": "roundrobin",
            "nodes": {
                upstream_url: 1
            }
        }
    }
    
    success = await register_apisix_route(route_config)
    
    if not success:
        raise HTTPException(status_code=500, detail="Route registration failed")
    
    return {
        "route_id": route_id,
        "path": path,
        "upstream": upstream_url,
        "status": "registered"
    }

@app.get("/dapr/state/{store}/{key}")
async def get_dapr_state(store: str, key: str):
    """Get state from Dapr state store"""
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{DAPR_HTTP_PORT}/v1.0/state/{store}/{key}",
                timeout=10.0
            )
            response.raise_for_status()
            return {"key": key, "value": response.json(), "found": True}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"key": key, "found": False}
        raise HTTPException(status_code=500, detail="Dapr state get failed")

@app.post("/dapr/state/{store}")
async def save_dapr_state(store: str, key: str, value: Any):
    """Save state to Dapr state store"""
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:{DAPR_HTTP_PORT}/v1.0/state/{store}",
                json=[{"key": key, "value": value}],
                timeout=10.0
            )
            response.raise_for_status()
            return {"key": key, "status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dapr state save failed: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """Get middleware metrics"""
    
    # Redis metrics
    redis_info = {}
    try:
        info = redis_client.info()
        redis_info = {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory": info.get("used_memory_human", "0"),
            "total_commands": info.get("total_commands_processed", 0)
        }
    except:
        pass
    
    return {
        "redis": redis_info,
        "kafka": {
            "producer_available": kafka_producer is not None
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8026)
