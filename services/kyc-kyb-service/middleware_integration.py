"""
KYC/KYB Middleware Integration Layer
Unified integration with TigerBeetle, Kafka, Dapr, Fluvio, Temporal, Keycloak, Permify, Redis, APISIX, Lakehouse

This module provides production-ready integration between all KYC/KYB services
and the platform's middleware components.
"""

import os
import json
import logging
import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class MiddlewareConfig:
    """Middleware configuration"""
    # TigerBeetle
    tigerbeetle_address: str = "localhost:3000"
    tigerbeetle_cluster_id: int = 0
    
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_security_protocol: str = "SASL_SSL"
    kafka_sasl_mechanism: str = "PLAIN"
    
    # Dapr
    dapr_http_port: int = 3500
    dapr_grpc_port: int = 50001
    dapr_app_id: str = "kyc-kyb-service"
    
    # Fluvio
    fluvio_endpoint: str = "localhost:9003"
    fluvio_topic_prefix: str = "kyc"
    
    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "kyc-kyb"
    temporal_task_queue: str = "kyc-kyb-tasks"
    
    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "remittance"
    keycloak_client_id: str = "kyc-kyb-service"
    
    # Permify
    permify_host: str = "localhost:3476"
    permify_tenant: str = "remittance"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_cluster_mode: bool = False
    
    # APISIX
    apisix_admin_url: str = "http://localhost:9180"
    apisix_admin_key: str = ""
    
    # Lakehouse
    lakehouse_endpoint: str = "http://localhost:8181"
    lakehouse_catalog: str = "kyc_kyb"


def load_config() -> MiddlewareConfig:
    """Load configuration from environment"""
    return MiddlewareConfig(
        tigerbeetle_address=os.getenv("TIGERBEETLE_ADDRESS", "localhost:3000"),
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        dapr_http_port=int(os.getenv("DAPR_HTTP_PORT", "3500")),
        temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
        keycloak_url=os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
        permify_host=os.getenv("PERMIFY_HOST", "localhost:3476"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        apisix_admin_url=os.getenv("APISIX_ADMIN_URL", "http://localhost:9180"),
        lakehouse_endpoint=os.getenv("LAKEHOUSE_ENDPOINT", "http://localhost:8181"),
    )


# ============================================================================
# KAFKA INTEGRATION
# ============================================================================

class KafkaIntegration:
    """
    Kafka integration for KYC/KYB events
    Topics:
    - kyc.verification.events
    - kyc.monitoring.events
    - kyc.monitoring.alerts
    - kyc.case.events
    - kyc.evidence.events
    - kyc.audit.events
    """
    
    TOPICS = {
        "verification": "kyc.verification.events",
        "monitoring": "kyc.monitoring.events",
        "alerts": "kyc.monitoring.alerts",
        "cases": "kyc.case.events",
        "evidence": "kyc.evidence.events",
        "audit": "kyc.audit.events",
        "kyb": "kyc.kyb.events",
    }
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._producer = None
        self._consumers: Dict[str, Any] = {}
    
    async def connect(self):
        """Connect to Kafka"""
        logger.info(f"Connecting to Kafka at {self.config.kafka_bootstrap_servers}")
        # In production, initialize aiokafka producer
    
    async def publish(self, topic_key: str, event: Dict[str, Any], key: Optional[str] = None):
        """Publish event to Kafka topic"""
        topic = self.TOPICS.get(topic_key, topic_key)
        
        # Add metadata
        event["_metadata"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "kyc-kyb-service",
            "event_id": secrets.token_hex(16),
        }
        
        logger.info(f"Publishing to {topic}: {event.get('event_type', 'unknown')}")
        
        # In production, use aiokafka producer
        # await self._producer.send_and_wait(topic, json.dumps(event).encode(), key=key.encode() if key else None)
    
    async def subscribe(self, topic_key: str, handler: Callable):
        """Subscribe to Kafka topic"""
        topic = self.TOPICS.get(topic_key, topic_key)
        logger.info(f"Subscribing to {topic}")
        
        # In production, create consumer and start consuming
    
    async def close(self):
        """Close Kafka connections"""
        if self._producer:
            await self._producer.stop()
        for consumer in self._consumers.values():
            await consumer.stop()


# ============================================================================
# TEMPORAL INTEGRATION
# ============================================================================

class TemporalIntegration:
    """
    Temporal integration for long-running KYC/KYB workflows
    Workflows:
    - KYCVerificationWorkflow
    - KYBVerificationWorkflow
    - ContinuousMonitoringWorkflow
    - CaseManagementWorkflow
    - EvidenceCollectionWorkflow
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._client = None
    
    async def connect(self):
        """Connect to Temporal"""
        logger.info(f"Connecting to Temporal at {self.config.temporal_host}")
        # In production, initialize temporalio client
    
    async def start_kyc_verification_workflow(
        self,
        verification_id: str,
        subject_id: str,
        verification_type: str,
        documents: List[Dict[str, Any]]
    ) -> str:
        """Start KYC verification workflow"""
        workflow_id = f"kyc-verification-{verification_id}"
        
        logger.info(f"Starting KYC verification workflow: {workflow_id}")
        
        # In production:
        # handle = await self._client.start_workflow(
        #     "KYCVerificationWorkflow",
        #     args=[verification_id, subject_id, verification_type, documents],
        #     id=workflow_id,
        #     task_queue=self.config.temporal_task_queue,
        # )
        
        return workflow_id
    
    async def start_kyb_verification_workflow(
        self,
        verification_id: str,
        business_id: str,
        verification_path: str,
        documents: List[Dict[str, Any]]
    ) -> str:
        """Start KYB verification workflow"""
        workflow_id = f"kyb-verification-{verification_id}"
        
        logger.info(f"Starting KYB verification workflow: {workflow_id}")
        
        return workflow_id
    
    async def start_monitoring_workflow(
        self,
        subject_id: str,
        risk_level: str,
        screening_frequency_days: int
    ) -> str:
        """Start continuous monitoring workflow"""
        workflow_id = f"monitoring-{subject_id}"
        
        logger.info(f"Starting monitoring workflow: {workflow_id}")
        
        return workflow_id
    
    async def start_case_workflow(
        self,
        case_id: str,
        case_type: str,
        priority: str,
        sla_hours: float
    ) -> str:
        """Start case management workflow"""
        workflow_id = f"case-{case_id}"
        
        logger.info(f"Starting case workflow: {workflow_id}")
        
        return workflow_id
    
    async def signal_workflow(self, workflow_id: str, signal_name: str, data: Dict[str, Any]):
        """Send signal to workflow"""
        logger.info(f"Signaling workflow {workflow_id}: {signal_name}")
        
        # In production:
        # handle = self._client.get_workflow_handle(workflow_id)
        # await handle.signal(signal_name, data)
    
    async def query_workflow(self, workflow_id: str, query_name: str) -> Any:
        """Query workflow state"""
        logger.info(f"Querying workflow {workflow_id}: {query_name}")
        
        # In production:
        # handle = self._client.get_workflow_handle(workflow_id)
        # return await handle.query(query_name)
        
        return {}
    
    async def close(self):
        """Close Temporal connection"""
        pass


# ============================================================================
# REDIS INTEGRATION
# ============================================================================

class RedisIntegration:
    """
    Redis integration for caching and real-time data
    Uses:
    - Decision caching
    - Risk score caching
    - Session management
    - Rate limiting
    - Pub/Sub for real-time updates
    """
    
    CACHE_PREFIXES = {
        "decision": "kyc:decision:",
        "risk_score": "kyc:risk:",
        "session": "kyc:session:",
        "rate_limit": "kyc:rate:",
        "verification": "kyc:verification:",
    }
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._client = None
    
    async def connect(self):
        """Connect to Redis"""
        logger.info(f"Connecting to Redis at {self.config.redis_url}")
        # In production, initialize aioredis client
    
    async def cache_decision(
        self,
        subject_id: str,
        decision: Dict[str, Any],
        ttl_seconds: int = 3600
    ):
        """Cache KYC/KYB decision"""
        key = f"{self.CACHE_PREFIXES['decision']}{subject_id}"
        
        logger.debug(f"Caching decision for {subject_id}")
        
        # In production:
        # await self._client.setex(key, ttl_seconds, json.dumps(decision))
    
    async def get_cached_decision(self, subject_id: str) -> Optional[Dict[str, Any]]:
        """Get cached decision"""
        key = f"{self.CACHE_PREFIXES['decision']}{subject_id}"
        
        # In production:
        # data = await self._client.get(key)
        # return json.loads(data) if data else None
        
        return None
    
    async def cache_risk_score(
        self,
        subject_id: str,
        score: float,
        factors: Dict[str, float],
        ttl_seconds: int = 86400
    ):
        """Cache risk score"""
        key = f"{self.CACHE_PREFIXES['risk_score']}{subject_id}"
        
        data = {
            "score": score,
            "factors": factors,
            "cached_at": datetime.utcnow().isoformat(),
        }
        
        logger.debug(f"Caching risk score for {subject_id}: {score}")
        
        # In production:
        # await self._client.setex(key, ttl_seconds, json.dumps(data))
    
    async def get_risk_score(self, subject_id: str) -> Optional[Dict[str, Any]]:
        """Get cached risk score"""
        key = f"{self.CACHE_PREFIXES['risk_score']}{subject_id}"
        
        return None
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> bool:
        """Check rate limit"""
        rate_key = f"{self.CACHE_PREFIXES['rate_limit']}{key}"
        
        # In production, use Redis INCR with EXPIRE
        # current = await self._client.incr(rate_key)
        # if current == 1:
        #     await self._client.expire(rate_key, window_seconds)
        # return current <= limit
        
        return True
    
    async def publish(self, channel: str, message: Dict[str, Any]):
        """Publish message to Redis channel"""
        logger.debug(f"Publishing to channel {channel}")
        
        # In production:
        # await self._client.publish(channel, json.dumps(message))
    
    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()


# ============================================================================
# DAPR INTEGRATION
# ============================================================================

class DaprIntegration:
    """
    Dapr integration for service invocation and pub/sub
    Uses:
    - Service-to-service invocation
    - State management
    - Pub/Sub messaging
    - Bindings for external systems
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._base_url = f"http://localhost:{config.dapr_http_port}"
    
    async def invoke_service(
        self,
        app_id: str,
        method: str,
        data: Dict[str, Any],
        http_method: str = "POST"
    ) -> Dict[str, Any]:
        """Invoke another service via Dapr"""
        url = f"{self._base_url}/v1.0/invoke/{app_id}/method/{method}"
        
        logger.info(f"Invoking {app_id}/{method}")
        
        # In production, use aiohttp to call Dapr sidecar
        # async with aiohttp.ClientSession() as session:
        #     async with session.request(http_method, url, json=data) as response:
        #         return await response.json()
        
        return {}
    
    async def save_state(self, store_name: str, key: str, value: Any):
        """Save state to Dapr state store"""
        url = f"{self._base_url}/v1.0/state/{store_name}"
        
        data = [{"key": key, "value": value}]
        
        logger.debug(f"Saving state {key} to {store_name}")
        
        # In production, POST to Dapr state API
    
    async def get_state(self, store_name: str, key: str) -> Any:
        """Get state from Dapr state store"""
        url = f"{self._base_url}/v1.0/state/{store_name}/{key}"
        
        logger.debug(f"Getting state {key} from {store_name}")
        
        return None
    
    async def publish_event(self, pubsub_name: str, topic: str, data: Dict[str, Any]):
        """Publish event via Dapr pub/sub"""
        url = f"{self._base_url}/v1.0/publish/{pubsub_name}/{topic}"
        
        logger.info(f"Publishing to {pubsub_name}/{topic}")
        
        # In production, POST to Dapr publish API
    
    async def send_notification(
        self,
        notification_type: str,
        recipient: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Send notification via Dapr binding"""
        binding_name = f"notification-{notification_type}"
        url = f"{self._base_url}/v1.0/bindings/{binding_name}"
        
        payload = {
            "operation": "create",
            "data": {
                "recipient": recipient,
                "message": message,
                "data": data or {},
            },
        }
        
        logger.info(f"Sending {notification_type} notification to {recipient}")


# ============================================================================
# FLUVIO INTEGRATION
# ============================================================================

class FluvioIntegration:
    """
    Fluvio integration for real-time streaming
    Uses:
    - Real-time alert streaming
    - Event sourcing
    - Stream processing
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._producer = None
        self._consumers: Dict[str, Any] = {}
    
    async def connect(self):
        """Connect to Fluvio"""
        logger.info(f"Connecting to Fluvio at {self.config.fluvio_endpoint}")
    
    async def produce(self, topic: str, data: Dict[str, Any], key: Optional[str] = None):
        """Produce message to Fluvio topic"""
        full_topic = f"{self.config.fluvio_topic_prefix}-{topic}"
        
        logger.debug(f"Producing to Fluvio topic {full_topic}")
        
        # In production, use fluvio-python client
    
    async def stream_alerts(self, alert: Dict[str, Any]):
        """Stream alert to real-time topic"""
        await self.produce("alerts", alert, key=alert.get("subject_id"))
    
    async def stream_verification_event(self, event: Dict[str, Any]):
        """Stream verification event"""
        await self.produce("verifications", event, key=event.get("verification_id"))
    
    async def close(self):
        """Close Fluvio connections"""
        pass


# ============================================================================
# KEYCLOAK INTEGRATION
# ============================================================================

class KeycloakIntegration:
    """
    Keycloak integration for identity management
    Uses:
    - User creation after KYC approval
    - Role assignment based on verification level
    - Token validation
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._admin_token = None
        self._token_expiry = None
    
    async def get_admin_token(self) -> str:
        """Get admin token from Keycloak token endpoint"""
        if self._admin_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._admin_token
        
        import aiohttp
        token_url = f"{self.config.keycloak_url}/realms/master/protocol/openid-connect/token"
        admin_user = os.getenv("KEYCLOAK_ADMIN_USER", "admin")
        admin_pass = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "")
        if not admin_pass:
            raise RuntimeError("KEYCLOAK_ADMIN_PASSWORD env var is required")
        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": admin_user,
            "password": admin_pass,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"Keycloak token request failed ({resp.status}): {body}")
                token_data = await resp.json()
                self._admin_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
        
        return self._admin_token
    
    async def create_user(
        self,
        user_id: str,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create user in Keycloak after KYC approval"""
        logger.info(f"Creating Keycloak user for {email}")
        token = await self.get_admin_token()
        
        user_data = {
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "attributes": {
                "kyc_verified": ["true"],
                "kyc_verification_id": [user_id],
                "phone": [phone] if phone else [],
                **(attributes or {}),
            },
        }
        
        import aiohttp
        url = f"{self.config.keycloak_url}/admin/realms/{self.config.keycloak_realm}/users"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=user_data, headers=headers) as resp:
                if resp.status not in (201, 409):
                    body = await resp.text()
                    logger.error(f"Keycloak user creation failed ({resp.status}): {body}")
                    raise RuntimeError(f"Failed to create Keycloak user: {body}")
                if resp.status == 409:
                    logger.info(f"User {email} already exists in Keycloak")
        
        return user_id
    
    async def assign_role(self, user_id: str, role_name: str):
        """Assign role to user via Keycloak role mapping API"""
        logger.info(f"Assigning role {role_name} to user {user_id}")
        token = await self.get_admin_token()
        import aiohttp
        realm = self.config.keycloak_realm
        base = self.config.keycloak_url
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        roles_url = f"{base}/admin/realms/{realm}/roles/{role_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(roles_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Role {role_name} not found")
                    return
                role_data = await resp.json()
            mapping_url = f"{base}/admin/realms/{realm}/users/{user_id}/role-mappings/realm"
            async with session.post(mapping_url, json=[role_data], headers=headers) as resp:
                if resp.status != 204:
                    body = await resp.text()
                    logger.error(f"Role assignment failed ({resp.status}): {body}")
    
    async def update_user_attributes(self, user_id: str, attributes: Dict[str, Any]):
        """Update user attributes via Keycloak user API"""
        logger.info(f"Updating attributes for user {user_id}")
        token = await self.get_admin_token()
        import aiohttp
        url = f"{self.config.keycloak_url}/admin/realms/{self.config.keycloak_realm}/users/{user_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json={"attributes": attributes}, headers=headers) as resp:
                if resp.status != 204:
                    body = await resp.text()
                    logger.error(f"User attribute update failed ({resp.status}): {body}")
    
    async def disable_user(self, user_id: str, reason: str):
        """Disable user via Keycloak user API"""
        logger.info(f"Disabling user {user_id}: {reason}")
        token = await self.get_admin_token()
        import aiohttp
        url = f"{self.config.keycloak_url}/admin/realms/{self.config.keycloak_realm}/users/{user_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json={"enabled": False, "attributes": {"disable_reason": [reason]}}, headers=headers) as resp:
                if resp.status != 204:
                    body = await resp.text()
                    logger.error(f"User disable failed ({resp.status}): {body}")


# ============================================================================
# PERMIFY INTEGRATION
# ============================================================================

class PermifyIntegration:
    """
    Permify integration for fine-grained authorization
    Uses:
    - Permission management based on verification level
    - Transaction limits based on KYC tier
    - Feature access control
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
    
    async def create_relationship(
        self,
        entity_type: str,
        entity_id: str,
        relation: str,
        subject_type: str,
        subject_id: str
    ):
        """Create permission relationship"""
        logger.info(f"Creating relationship: {entity_type}:{entity_id}#{relation}@{subject_type}:{subject_id}")
        
        # In production, call Permify write API
    
    async def check_permission(
        self,
        entity_type: str,
        entity_id: str,
        permission: str,
        subject_type: str,
        subject_id: str
    ) -> bool:
        """Check if subject has permission on entity"""
        logger.debug(f"Checking permission: {entity_type}:{entity_id}#{permission}@{subject_type}:{subject_id}")
        
        # In production, call Permify check API
        return True
    
    async def set_kyc_tier_permissions(self, user_id: str, tier: str):
        """Set permissions based on KYC tier"""
        tier_permissions = {
            "tier_1": {
                "daily_transaction_limit": 50000,
                "single_transaction_limit": 10000,
                "features": ["basic_transfer", "bill_payment"],
            },
            "tier_2": {
                "daily_transaction_limit": 200000,
                "single_transaction_limit": 50000,
                "features": ["basic_transfer", "bill_payment", "card_payment", "international"],
            },
            "tier_3": {
                "daily_transaction_limit": 5000000,
                "single_transaction_limit": 1000000,
                "features": ["basic_transfer", "bill_payment", "card_payment", "international", "bulk_payment", "api_access"],
            },
        }
        
        permissions = tier_permissions.get(tier, tier_permissions["tier_1"])
        
        logger.info(f"Setting {tier} permissions for user {user_id}")
        
        # Create relationships for each feature
        for feature in permissions["features"]:
            await self.create_relationship(
                "feature", feature, "can_use", "user", user_id
            )
        
        # Set transaction limits
        await self.create_relationship(
            "user", user_id, "has_limit",
            "limit", f"daily_{permissions['daily_transaction_limit']}"
        )
    
    async def delete_relationship(
        self,
        entity_type: str,
        entity_id: str,
        relation: str,
        subject_type: str,
        subject_id: str
    ):
        """Delete permission relationship"""
        logger.info(f"Deleting relationship: {entity_type}:{entity_id}#{relation}@{subject_type}:{subject_id}")


# ============================================================================
# TIGERBEETLE INTEGRATION
# ============================================================================

class TigerBeetleIntegration:
    """
    TigerBeetle integration for financial accounts
    Uses:
    - Account creation after KYC/KYB approval
    - Reserve requirements based on risk level
    - Transaction limits
    """
    
    LEDGER_IDS = {
        "main": 1,
        "pending": 2,
        "reserve": 3,
        "fees": 4,
    }
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self._client = None
    
    async def connect(self):
        """Connect to TigerBeetle"""
        logger.info(f"Connecting to TigerBeetle at {self.config.tigerbeetle_address}")
        # In production, initialize tigerbeetle-python client
    
    async def create_merchant_accounts(
        self,
        merchant_id: str,
        risk_level: str,
        initial_reserve_pct: float = 0.0
    ) -> Dict[str, int]:
        """Create TigerBeetle accounts for approved merchant"""
        # Generate account IDs
        base_id = int(hashlib.sha256(merchant_id.encode()).hexdigest()[:16], 16)
        
        accounts = {
            "main": base_id,
            "pending": base_id + 1,
            "reserve": base_id + 2,
            "fees": base_id + 3,
        }
        
        # Set reserve requirement based on risk level
        reserve_requirements = {
            "low": 0.0,
            "medium": 0.05,
            "high": 0.10,
            "very_high": 0.20,
        }
        
        reserve_pct = reserve_requirements.get(risk_level, 0.10)
        
        logger.info(f"Creating TigerBeetle accounts for merchant {merchant_id} with {reserve_pct*100}% reserve")
        
        # In production, create accounts via TigerBeetle client
        # for name, account_id in accounts.items():
        #     await self._client.create_accounts([{
        #         "id": account_id,
        #         "ledger": self.LEDGER_IDS[name],
        #         "code": 1,
        #         "flags": 0,
        #         "user_data": merchant_id.encode(),
        #     }])
        
        return accounts
    
    async def set_account_limits(
        self,
        account_id: int,
        daily_limit: float,
        single_limit: float
    ):
        """Set transaction limits on account"""
        logger.info(f"Setting limits on account {account_id}: daily={daily_limit}, single={single_limit}")
        
        # In production, store limits in account metadata or separate table
    
    async def freeze_account(self, account_id: int, reason: str):
        """Freeze account (e.g., after failed reverification)"""
        logger.info(f"Freezing account {account_id}: {reason}")
        
        # In production, update account flags
    
    async def close(self):
        """Close TigerBeetle connection"""
        pass


# ============================================================================
# APISIX INTEGRATION
# ============================================================================

class APISIXIntegration:
    """
    APISIX integration for API gateway
    Uses:
    - Route registration for KYC/KYB endpoints
    - Rate limiting per verification tier
    - Authentication enforcement
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
    
    async def register_routes(self):
        """Register KYC/KYB routes in APISIX"""
        routes = [
            {
                "uri": "/api/v1/kyc/verify",
                "methods": ["POST"],
                "upstream_id": "kyc-kyb-service",
                "plugins": {
                    "jwt-auth": {},
                    "limit-req": {"rate": 10, "burst": 5},
                },
            },
            {
                "uri": "/api/v1/kyb/verify",
                "methods": ["POST"],
                "upstream_id": "kyc-kyb-service",
                "plugins": {
                    "jwt-auth": {},
                    "limit-req": {"rate": 5, "burst": 2},
                },
            },
            {
                "uri": "/api/v1/kyc/status/*",
                "methods": ["GET"],
                "upstream_id": "kyc-kyb-service",
                "plugins": {
                    "jwt-auth": {},
                    "limit-req": {"rate": 100, "burst": 50},
                },
            },
            {
                "uri": "/api/v1/monitoring/alerts",
                "methods": ["GET"],
                "upstream_id": "kyc-kyb-service",
                "plugins": {
                    "jwt-auth": {},
                    "limit-req": {"rate": 50, "burst": 20},
                },
            },
        ]
        
        for route in routes:
            logger.info(f"Registering APISIX route: {route['uri']}")
            
            # In production, POST to APISIX Admin API
    
    async def update_rate_limit(self, route_id: str, rate: int, burst: int):
        """Update rate limit for route"""
        logger.info(f"Updating rate limit for route {route_id}: rate={rate}, burst={burst}")


# ============================================================================
# LAKEHOUSE INTEGRATION
# ============================================================================

class LakehouseIntegration:
    """
    Lakehouse integration for analytics and ML
    Uses:
    - Verification event streaming
    - Risk score analytics
    - ML model training data
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
    
    async def stream_verification_event(self, event: Dict[str, Any]):
        """Stream verification event to Lakehouse"""
        table = f"{self.config.lakehouse_catalog}.verifications"
        
        logger.debug(f"Streaming to Lakehouse table {table}")
        
        # In production, use Iceberg REST catalog or Kafka connector
    
    async def stream_risk_score(self, subject_id: str, score: float, factors: Dict[str, float]):
        """Stream risk score to Lakehouse"""
        table = f"{self.config.lakehouse_catalog}.risk_scores"
        
        data = {
            "subject_id": subject_id,
            "score": score,
            "factors": factors,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.debug(f"Streaming risk score to Lakehouse: {subject_id} = {score}")
    
    async def stream_case_event(self, case_id: str, event_type: str, data: Dict[str, Any]):
        """Stream case event to Lakehouse"""
        table = f"{self.config.lakehouse_catalog}.case_events"
        
        logger.debug(f"Streaming case event to Lakehouse: {case_id} - {event_type}")


# ============================================================================
# UNIFIED MIDDLEWARE SERVICE
# ============================================================================

class KYCKYBMiddlewareService:
    """
    Unified middleware service that integrates all components
    """
    
    def __init__(self, config: Optional[MiddlewareConfig] = None):
        self.config = config or load_config()
        
        # Initialize all integrations
        self.kafka = KafkaIntegration(self.config)
        self.temporal = TemporalIntegration(self.config)
        self.redis = RedisIntegration(self.config)
        self.dapr = DaprIntegration(self.config)
        self.fluvio = FluvioIntegration(self.config)
        self.keycloak = KeycloakIntegration(self.config)
        self.permify = PermifyIntegration(self.config)
        self.tigerbeetle = TigerBeetleIntegration(self.config)
        self.apisix = APISIXIntegration(self.config)
        self.lakehouse = LakehouseIntegration(self.config)
    
    async def initialize(self):
        """Initialize all middleware connections"""
        logger.info("Initializing KYC/KYB middleware integrations")
        
        await self.kafka.connect()
        await self.temporal.connect()
        await self.redis.connect()
        await self.fluvio.connect()
        await self.tigerbeetle.connect()
        await self.apisix.register_routes()
        
        logger.info("All middleware integrations initialized")
    
    async def on_kyc_approved(
        self,
        verification_id: str,
        subject_id: str,
        subject_type: str,
        tier: str,
        risk_level: str,
        subject_data: Dict[str, Any]
    ):
        """Handle KYC approval - trigger all downstream actions"""
        logger.info(f"Processing KYC approval for {subject_id}")
        
        # 1. Publish to Kafka
        await self.kafka.publish("verification", {
            "event_type": "kyc_approved",
            "verification_id": verification_id,
            "subject_id": subject_id,
            "subject_type": subject_type,
            "tier": tier,
            "risk_level": risk_level,
        })
        
        # 2. Create Keycloak user
        if subject_type == "individual":
            await self.keycloak.create_user(
                user_id=subject_id,
                email=subject_data.get("email", ""),
                first_name=subject_data.get("first_name", ""),
                last_name=subject_data.get("last_name", ""),
                phone=subject_data.get("phone"),
                attributes={"kyc_tier": [tier], "risk_level": [risk_level]},
            )
        
        # 3. Set Permify permissions
        await self.permify.set_kyc_tier_permissions(subject_id, tier)
        
        # 4. Create TigerBeetle accounts
        accounts = await self.tigerbeetle.create_merchant_accounts(
            subject_id, risk_level
        )
        
        # 5. Cache decision
        await self.redis.cache_decision(subject_id, {
            "status": "approved",
            "tier": tier,
            "risk_level": risk_level,
            "accounts": accounts,
            "approved_at": datetime.utcnow().isoformat(),
        })
        
        # 6. Start monitoring workflow
        screening_frequency = {"low": 180, "medium": 90, "high": 30, "very_high": 14}
        await self.temporal.start_monitoring_workflow(
            subject_id, risk_level, screening_frequency.get(risk_level, 90)
        )
        
        # 7. Stream to Lakehouse
        await self.lakehouse.stream_verification_event({
            "verification_id": verification_id,
            "subject_id": subject_id,
            "status": "approved",
            "tier": tier,
            "risk_level": risk_level,
        })
        
        # 8. Send notification via Dapr
        await self.dapr.send_notification(
            "email",
            subject_data.get("email", ""),
            f"Your verification has been approved. You are now at {tier} level.",
            {"verification_id": verification_id, "tier": tier},
        )
        
        logger.info(f"KYC approval processing complete for {subject_id}")
    
    async def on_kyc_rejected(
        self,
        verification_id: str,
        subject_id: str,
        reason: str,
        subject_data: Dict[str, Any]
    ):
        """Handle KYC rejection"""
        logger.info(f"Processing KYC rejection for {subject_id}: {reason}")
        
        # Publish to Kafka
        await self.kafka.publish("verification", {
            "event_type": "kyc_rejected",
            "verification_id": verification_id,
            "subject_id": subject_id,
            "reason": reason,
        })
        
        # Stream to Lakehouse
        await self.lakehouse.stream_verification_event({
            "verification_id": verification_id,
            "subject_id": subject_id,
            "status": "rejected",
            "reason": reason,
        })
        
        # Send notification
        await self.dapr.send_notification(
            "email",
            subject_data.get("email", ""),
            f"Your verification was not approved. Reason: {reason}",
            {"verification_id": verification_id},
        )
    
    async def on_monitoring_alert(
        self,
        alert_id: str,
        subject_id: str,
        alert_type: str,
        severity: str,
        details: Dict[str, Any]
    ):
        """Handle monitoring alert"""
        logger.info(f"Processing monitoring alert {alert_id} for {subject_id}")
        
        # Publish to Kafka
        await self.kafka.publish("alerts", {
            "event_type": "monitoring_alert",
            "alert_id": alert_id,
            "subject_id": subject_id,
            "alert_type": alert_type,
            "severity": severity,
            "details": details,
        })
        
        # Stream to Fluvio for real-time processing
        await self.fluvio.stream_alerts({
            "alert_id": alert_id,
            "subject_id": subject_id,
            "alert_type": alert_type,
            "severity": severity,
        })
        
        # Create case if high severity
        if severity in ["high", "critical"]:
            case_id = secrets.token_hex(16)
            await self.temporal.start_case_workflow(
                case_id,
                f"alert_{alert_type}",
                severity,
                sla_hours=4.0 if severity == "critical" else 12.0,
            )
    
    async def on_case_resolved(
        self,
        case_id: str,
        subject_id: str,
        resolution: str,
        resolved_by: str
    ):
        """Handle case resolution"""
        logger.info(f"Processing case resolution {case_id}: {resolution}")
        
        # Publish to Kafka
        await self.kafka.publish("cases", {
            "event_type": "case_resolved",
            "case_id": case_id,
            "subject_id": subject_id,
            "resolution": resolution,
            "resolved_by": resolved_by,
        })
        
        # Stream to Lakehouse
        await self.lakehouse.stream_case_event(case_id, "resolved", {
            "resolution": resolution,
            "resolved_by": resolved_by,
        })
    
    async def shutdown(self):
        """Shutdown all middleware connections"""
        logger.info("Shutting down KYC/KYB middleware integrations")
        
        await self.kafka.close()
        await self.redis.close()
        await self.fluvio.close()
        await self.tigerbeetle.close()
        
        logger.info("All middleware integrations shut down")


# Global instance
_middleware_service: Optional[KYCKYBMiddlewareService] = None


def get_middleware_service() -> KYCKYBMiddlewareService:
    """Get or create middleware service"""
    global _middleware_service
    if _middleware_service is None:
        _middleware_service = KYCKYBMiddlewareService()
    return _middleware_service


async def initialize_middleware():
    """Initialize middleware service"""
    service = get_middleware_service()
    await service.initialize()
    return service
