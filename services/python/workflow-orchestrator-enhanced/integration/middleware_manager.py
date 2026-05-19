"""
Middleware Manager - Integration layer for all middleware services
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from middleware.kafka.client import KafkaClient, KafkaConfig, WorkflowEvent as KafkaEvent
from middleware.dapr.client import DaprClient, DaprConfig
from middleware.fluvio.client import FluvioClient, FluvioConfig, WorkflowEvent as FluvioEvent
from middleware.temporal.client import TemporalWorkflowClient, TemporalConfig, WorkflowInput
from middleware.keycloak.client import KeycloakClient, KeycloakConfig
from middleware.permify.client import PermifyClient, PermifyConfig
from middleware.redis.client import RedisClient, RedisConfig
from middleware.tigerbeetle.client import TigerBeetleClient, TigerBeetleConfig
from middleware.lakehouse.client import LakehouseClient, LakehouseConfig, WorkflowEvent as LakehouseEvent
from middleware.apisix.client import APISIXClient, APISIXConfig
from middleware.postgres.client import PostgreSQLClient, PostgreSQLConfig

import os
logger = logging.getLogger(__name__)


@dataclass
class MiddlewareConfig:
    """Configuration for all middleware services"""
    kafka: KafkaConfig
    dapr: DaprConfig
    fluvio: FluvioConfig
    temporal: TemporalConfig
    keycloak: KeycloakConfig
    permify: PermifyConfig
    redis: RedisConfig
    tigerbeetle: TigerBeetleConfig
    lakehouse: LakehouseConfig
    apisix: APISIXConfig
    postgres: PostgreSQLConfig


class MiddlewareManager:
    """Manages all middleware integrations for workflow orchestration"""

    def __init__(self, config: MiddlewareConfig):
        logger.info("Initializing middleware manager")
        
        # Initialize all middleware clients
        self.kafka = KafkaClient(config.kafka)
        self.dapr = DaprClient(config.dapr)
        self.fluvio = FluvioClient(config.fluvio)
        self.temporal = TemporalWorkflowClient(config.temporal)
        self.keycloak = KeycloakClient(config.keycloak)
        self.permify = PermifyClient(config.permify)
        self.redis = RedisClient(config.redis)
        self.tigerbeetle = TigerBeetleClient(config.tigerbeetle)
        self.lakehouse = LakehouseClient(config.lakehouse)
        self.apisix = APISIXClient(config.apisix)
        self.postgres = PostgreSQLClient(config.postgres)
        
        logger.info("All middleware services initialized successfully")

    def publish_workflow_event(self, event: KafkaEvent) -> None:
        """Publish a workflow event to Kafka, Fluvio, and Lakehouse"""
        logger.info(f"Publishing workflow event: {event.workflow_id} - {event.event_type}")
        
        # Publish to Kafka for asynchronous processing
        try:
            self.kafka.publish_workflow_event(event)
        except Exception as e:
            logger.error(f"Failed to publish event to Kafka: {e}")
            raise
        
        # Publish to Fluvio for real-time streaming
        try:
            fluvio_event = FluvioEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                workflow_id=event.workflow_id,
                workflow_type=event.workflow_type,
                status=event.status,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                data=event.data,
            )
            self.fluvio.publish_workflow_event(fluvio_event)
        except Exception as e:
            logger.warning(f"Failed to publish event to Fluvio: {e}")
            # Don't raise - Fluvio is optional for real-time updates
        
        # Stream to Lakehouse for analytics
        try:
            lakehouse_event = LakehouseEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                workflow_id=event.workflow_id,
                workflow_type=event.workflow_type,
                status=event.status,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                entity_id="",
                duration=0.0,
                step_count=0,
                metadata=event.data,
            )
            self.lakehouse.stream_workflow_event(lakehouse_event)
        except Exception as e:
            logger.warning(f"Failed to stream event to Lakehouse: {e}")
            # Don't raise - Lakehouse is optional for analytics

    def cache_workflow_state(self, workflow_id: str, state: Dict[str, Any], ttl: int = 3600) -> None:
        """Cache workflow state in Redis"""
        logger.info(f"Caching workflow state: {workflow_id}")
        self.redis.cache_workflow_state(workflow_id, state, ttl)

    def get_cached_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get cached workflow state from Redis"""
        logger.info(f"Getting cached workflow state: {workflow_id}")
        return self.redis.get_workflow_state(workflow_id)

    def save_workflow_to_db(
        self,
        workflow_id: str,
        workflow_type: str,
        status: str,
        input_data: Dict[str, Any],
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Save workflow to PostgreSQL"""
        logger.info(f"Saving workflow to database: {workflow_id}")
        self.postgres.save_workflow(workflow_id, workflow_type, status, input_data, tenant_id, user_id)

    def get_workflow_from_db(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow from PostgreSQL"""
        logger.info(f"Getting workflow from database: {workflow_id}")
        return self.postgres.get_workflow(workflow_id)

    def update_workflow_status(self, workflow_id: str, status: str) -> None:
        """Update workflow status in PostgreSQL"""
        logger.info(f"Updating workflow status: {workflow_id} - {status}")
        self.postgres.update_workflow_status(workflow_id, status)

    def validate_user_token(self, access_token: str):
        """Validate JWT token with Keycloak"""
        logger.info("Validating user token with Keycloak")
        return self.keycloak.validate_token(access_token)

    def check_workflow_permission(self, user_id: str, workflow_id: str, action: str) -> bool:
        """Check if user has permission to access workflow"""
        logger.info(f"Checking workflow permission: {user_id} - {workflow_id} - {action}")
        return self.permify.check_workflow_permission(user_id, workflow_id, action)

    def grant_workflow_access(self, workflow_id: str, user_id: str, role: str) -> None:
        """Grant user access to workflow"""
        logger.info(f"Granting workflow access: {workflow_id} - {user_id} - {role}")
        self.permify.grant_workflow_access(workflow_id, user_id, role)

    def invoke_service(self, app_id: str, method: str, data: Any) -> Dict[str, Any]:
        """Invoke a service via Dapr"""
        logger.info(f"Invoking service via Dapr: {app_id}/{method}")
        return self.dapr.invoke_service(app_id, method, data)

    def save_state_to_dapr(self, store_name: str, key: str, value: Any) -> None:
        """Save state to Dapr state store"""
        logger.info(f"Saving state to Dapr: {store_name}/{key}")
        self.dapr.save_state(store_name, key, value)

    def get_state_from_dapr(self, store_name: str, key: str) -> Optional[Any]:
        """Get state from Dapr state store"""
        logger.info(f"Getting state from Dapr: {store_name}/{key}")
        return self.dapr.get_state(store_name, key)

    async def delegate_to_temporal(self, workflow_type: str, input_data: WorkflowInput) -> str:
        """Delegate a long-running workflow to Temporal"""
        logger.info(f"Delegating workflow to Temporal: {workflow_type} - {input_data.workflow_id}")
        await self.temporal.connect()
        return await self.temporal.start_workflow(workflow_type, input_data)

    async def get_temporal_workflow_status(self, workflow_id: str):
        """Get status of a Temporal workflow"""
        logger.info(f"Getting Temporal workflow status: {workflow_id}")
        return await self.temporal.get_workflow_status(workflow_id)

    def process_payment(self, payment_id: str, from_account_id: bytes, to_account_id: bytes, amount: int) -> None:
        """Process a payment via TigerBeetle"""
        logger.info(f"Processing payment: {payment_id} - Amount: {amount}")
        self.tigerbeetle.process_payment(payment_id, from_account_id, to_account_id, amount)

    def acquire_distributed_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """Acquire a distributed lock via Redis"""
        logger.info(f"Acquiring distributed lock: {lock_name}")
        return self.redis.acquire_lock(lock_name, timeout)

    def release_distributed_lock(self, lock_name: str) -> None:
        """Release a distributed lock via Redis"""
        logger.info(f"Releasing distributed lock: {lock_name}")
        self.redis.release_lock(lock_name)

    def close(self) -> None:
        """Close all middleware connections"""
        logger.info("Closing all middleware connections")
        
        try:
            self.kafka.close()
            self.dapr.close()
            self.fluvio.close()
            self.keycloak.close()
            self.permify.close()
            self.redis.close()
            self.tigerbeetle.close()
            self.lakehouse.close()
            self.apisix.close()
            self.postgres.close()
            logger.info("All middleware connections closed successfully")
        except Exception as e:
            logger.error(f"Error closing middleware connections: {e}")
            raise


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create configuration
    config = MiddlewareConfig(
        kafka=KafkaConfig(brokers=["localhost:9092"]),
        dapr=DaprConfig(),
        fluvio=FluvioConfig(sc_addr="localhost:9003", topic_workflow_events="workflow-events"),
        temporal=TemporalConfig(),
        keycloak=KeycloakConfig(
            url=os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
            realm=os.getenv("KEYCLOAK_REALM", "remittance"),
            client_id=os.getenv("KEYCLOAK_CLIENT_ID", "workflow-orchestrator"),
            client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET", ""),
            admin_user=os.getenv("KEYCLOAK_ADMIN_USER", "admin"),
            admin_pass=os.getenv("KEYCLOAK_ADMIN_PASSWORD", ""),
        ),
        permify=PermifyConfig(grpc_addr=os.getenv("PERMIFY_GRPC_ADDR", "localhost:3476"), tenant_id=os.getenv("PERMIFY_TENANT_ID", "default")),
        redis=RedisConfig(),
        tigerbeetle=TigerBeetleConfig(cluster_id=int(os.getenv("TIGERBEETLE_CLUSTER_ID", "1")), addresses=os.getenv("TIGERBEETLE_ADDRESSES", "localhost:3000").split(",")),
        lakehouse=LakehouseConfig(api_url=os.getenv("LAKEHOUSE_API_URL", "http://localhost:8000"), s3_bucket=os.getenv("LAKEHOUSE_S3_BUCKET", "workflows"), api_key=os.getenv("LAKEHOUSE_API_KEY", "")),
        apisix=APISIXConfig(admin_url=os.getenv("APISIX_ADMIN_URL", "http://localhost:9180"), gateway_url=os.getenv("APISIX_GATEWAY_URL", "http://localhost:9080"), api_key=os.getenv("APISIX_API_KEY", "")),
        postgres=PostgreSQLConfig(host=os.getenv("DB_HOST", "localhost"), port=5432, database=os.getenv("DB_NAME", "workflows"), user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", "")),
    )
    
    # Create middleware manager
    manager = MiddlewareManager(config)
    
    # Example: Publish workflow event
    from datetime import datetime
    event = KafkaEvent(
        event_id="evt-123",
        event_type="workflow.started",
        workflow_id="wf-123",
        workflow_type="payment",
        status="in_progress",
        tenant_id="tenant-1",
        user_id="user-1",
        data={"amount": 1000},
        timestamp=datetime.utcnow(),
    )
    manager.publish_workflow_event(event)
    
    # Close connections
    manager.close()

