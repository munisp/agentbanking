"""
Dapr Client Library for Remittance Platform V11.0

Provides a reusable Dapr client for microservices integration.

Features:
- Service invocation with service discovery
- State management (get, save, delete)
- Pub/Sub messaging
- Bindings (input/output)
- Secret management
- Distributed lock
- Actor invocation

Author: Manus AI
Date: November 11, 2025
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
from dapr.clients import DaprClient
from dapr.clients.grpc._state import StateOptions, Consistency, Concurrency
from dapr.clients.grpc._request import TransactionalStateOperation, TransactionOperationType


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentBankingDaprClient:
    """
    Dapr client wrapper for Remittance Platform.
    
    Usage:
        client = AgentBankingDaprClient()
        
        # Service invocation
        response = await client.invoke_service(
            app_id="wallet-service",
            method="get-balance",
            data={"user_id": "agent-001"}
        )
        
        # State management
        await client.save_state("user-session-123", session_data)
        session = await client.get_state("user-session-123")
        
        # Pub/Sub
        await client.publish_event("transactions.created", transaction_data)
    """
    
    def __init__(
        self,
        dapr_http_port: Optional[int] = None,
        dapr_grpc_port: Optional[int] = None,
        state_store_name: str = "statestore",
        pubsub_name: str = "pubsub",
        secret_store_name: str = "secretstore"
    ):
        """
        Initialize Dapr client.
        
        Args:
            dapr_http_port: Dapr HTTP port (default: 3500)
            dapr_grpc_port: Dapr gRPC port (default: 50001)
            state_store_name: Name of state store component
            pubsub_name: Name of pub/sub component
            secret_store_name: Name of secret store component
        """
        self.dapr_http_port = dapr_http_port or int(os.getenv("DAPR_HTTP_PORT", "3500"))
        self.dapr_grpc_port = dapr_grpc_port or int(os.getenv("DAPR_GRPC_PORT", "50001"))
        self.state_store_name = state_store_name
        self.pubsub_name = pubsub_name
        self.secret_store_name = secret_store_name
        
        # Metrics
        self.service_invocations = 0
        self.state_operations = 0
        self.pubsub_operations = 0
    
    # ========================================================================
    # Service Invocation
    # ========================================================================
    
    async def invoke_service(
        self,
        app_id: str,
        method: str,
        data: Optional[Dict[str, Any]] = None,
        http_verb: str = "POST",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Invoke another service via Dapr.
        
        Args:
            app_id: Target service app ID
            method: Method name to invoke
            data: Request data
            http_verb: HTTP verb (GET, POST, PUT, DELETE)
            metadata: Optional metadata headers
            
        Returns:
            Response data from target service
        """
        async with DaprClient() as client:
            try:
                response = await client.invoke_method(
                    app_id=app_id,
                    method_name=method,
                    data=json.dumps(data) if data else None,
                    http_verb=http_verb,
                    metadata=metadata
                )
                
                self.service_invocations += 1
                
                logger.debug(f"✅ Service invocation: {app_id}/{method}")
                
                return json.loads(response.data) if response.data else {}
            
            except Exception as e:
                logger.error(f"❌ Service invocation failed: {app_id}/{method}: {e}")
                raise
    
    # ========================================================================
    # State Management
    # ========================================================================
    
    async def get_state(
        self,
        key: str,
        consistency: str = "eventual"
    ) -> Optional[Dict[str, Any]]:
        """
        Get state from state store.
        
        Args:
            key: State key
            consistency: Consistency level (eventual, strong)
            
        Returns:
            State value or None if not found
        """
        async with DaprClient() as client:
            try:
                state_options = StateOptions(
                    consistency=Consistency.strong if consistency == "strong" else Consistency.eventual
                )
                
                response = await client.get_state(
                    store_name=self.state_store_name,
                    key=key,
                    state_metadata={"consistency": consistency}
                )
                
                self.state_operations += 1
                
                if response.data:
                    logger.debug(f"✅ State retrieved: {key}")
                    return json.loads(response.data)
                else:
                    logger.debug(f"State not found: {key}")
                    return None
            
            except Exception as e:
                logger.error(f"❌ Get state failed: {key}: {e}")
                raise
    
    async def save_state(
        self,
        key: str,
        value: Dict[str, Any],
        etag: Optional[str] = None,
        consistency: str = "eventual",
        concurrency: str = "first-write"
    ) -> bool:
        """
        Save state to state store.
        
        Args:
            key: State key
            value: State value
            etag: Optional etag for optimistic concurrency
            consistency: Consistency level (eventual, strong)
            concurrency: Concurrency mode (first-write, last-write)
            
        Returns:
            True if successful
        """
        async with DaprClient() as client:
            try:
                state_options = StateOptions(
                    consistency=Consistency.strong if consistency == "strong" else Consistency.eventual,
                    concurrency=Concurrency.first_write if concurrency == "first-write" else Concurrency.last_write
                )
                
                await client.save_state(
                    store_name=self.state_store_name,
                    key=key,
                    value=json.dumps(value),
                    etag=etag,
                    options=state_options
                )
                
                self.state_operations += 1
                
                logger.debug(f"✅ State saved: {key}")
                return True
            
            except Exception as e:
                logger.error(f"❌ Save state failed: {key}: {e}")
                raise
    
    async def delete_state(
        self,
        key: str,
        etag: Optional[str] = None
    ) -> bool:
        """
        Delete state from state store.
        
        Args:
            key: State key
            etag: Optional etag for optimistic concurrency
            
        Returns:
            True if successful
        """
        async with DaprClient() as client:
            try:
                await client.delete_state(
                    store_name=self.state_store_name,
                    key=key,
                    etag=etag
                )
                
                self.state_operations += 1
                
                logger.debug(f"✅ State deleted: {key}")
                return True
            
            except Exception as e:
                logger.error(f"❌ Delete state failed: {key}: {e}")
                raise
    
    async def execute_state_transaction(
        self,
        operations: List[Dict[str, Any]]
    ) -> bool:
        """
        Execute multiple state operations in a transaction.
        
        Args:
            operations: List of operations
                [
                    {"operation": "upsert", "key": "key1", "value": {...}},
                    {"operation": "delete", "key": "key2"}
                ]
                
        Returns:
            True if successful
        """
        async with DaprClient() as client:
            try:
                dapr_operations = []
                
                for op in operations:
                    if op["operation"] == "upsert":
                        dapr_operations.append(
                            TransactionalStateOperation(
                                operation_type=TransactionOperationType.upsert,
                                key=op["key"],
                                data=json.dumps(op["value"])
                            )
                        )
                    elif op["operation"] == "delete":
                        dapr_operations.append(
                            TransactionalStateOperation(
                                operation_type=TransactionOperationType.delete,
                                key=op["key"]
                            )
                        )
                
                await client.execute_state_transaction(
                    store_name=self.state_store_name,
                    operations=dapr_operations
                )
                
                self.state_operations += len(operations)
                
                logger.debug(f"✅ State transaction executed: {len(operations)} operations")
                return True
            
            except Exception as e:
                logger.error(f"❌ State transaction failed: {e}")
                raise
    
    # ========================================================================
    # Pub/Sub
    # ========================================================================
    
    async def publish_event(
        self,
        topic: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Publish event to pub/sub topic.
        
        Args:
            topic: Topic name
            data: Event data
            metadata: Optional metadata
            
        Returns:
            True if successful
        """
        async with DaprClient() as client:
            try:
                await client.publish_event(
                    pubsub_name=self.pubsub_name,
                    topic_name=topic,
                    data=json.dumps(data),
                    metadata=metadata
                )
                
                self.pubsub_operations += 1
                
                logger.debug(f"✅ Event published: {topic}")
                return True
            
            except Exception as e:
                logger.error(f"❌ Publish event failed: {topic}: {e}")
                raise
    
    # ========================================================================
    # Bindings
    # ========================================================================
    
    async def invoke_binding(
        self,
        binding_name: str,
        operation: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Invoke output binding.
        
        Args:
            binding_name: Binding name
            operation: Operation (create, get, delete, list)
            data: Request data
            metadata: Optional metadata
            
        Returns:
            Response data
        """
        async with DaprClient() as client:
            try:
                response = await client.invoke_binding(
                    binding_name=binding_name,
                    operation=operation,
                    data=json.dumps(data),
                    metadata=metadata
                )
                
                logger.debug(f"✅ Binding invoked: {binding_name}/{operation}")
                
                return json.loads(response.data) if response.data else {}
            
            except Exception as e:
                logger.error(f"❌ Invoke binding failed: {binding_name}/{operation}: {e}")
                raise
    
    # ========================================================================
    # Secrets
    # ========================================================================
    
    async def get_secret(
        self,
        key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Get secret from secret store.
        
        Args:
            key: Secret key
            metadata: Optional metadata
            
        Returns:
            Secret value(s)
        """
        async with DaprClient() as client:
            try:
                response = await client.get_secret(
                    store_name=self.secret_store_name,
                    key=key,
                    metadata=metadata
                )
                
                logger.debug(f"✅ Secret retrieved: {key}")
                
                return response.secret
            
            except Exception as e:
                logger.error(f"❌ Get secret failed: {key}: {e}")
                raise
    
    # ========================================================================
    # Distributed Lock
    # ========================================================================
    
    async def try_lock(
        self,
        store_name: str,
        resource_id: str,
        lock_owner: str,
        expiry_in_seconds: int = 60
    ) -> bool:
        """
        Try to acquire distributed lock.
        
        Args:
            store_name: Lock store name
            resource_id: Resource ID to lock
            lock_owner: Lock owner ID
            expiry_in_seconds: Lock expiry time
            
        Returns:
            True if lock acquired
        """
        async with DaprClient() as client:
            try:
                response = await client.try_lock(
                    store_name=store_name,
                    resource_id=resource_id,
                    lock_owner=lock_owner,
                    expiry_in_seconds=expiry_in_seconds
                )
                
                if response.success:
                    logger.debug(f"✅ Lock acquired: {resource_id}")
                else:
                    logger.debug(f"Lock not acquired: {resource_id}")
                
                return response.success
            
            except Exception as e:
                logger.error(f"❌ Try lock failed: {resource_id}: {e}")
                raise
    
    async def unlock(
        self,
        store_name: str,
        resource_id: str,
        lock_owner: str
    ) -> bool:
        """
        Release distributed lock.
        
        Args:
            store_name: Lock store name
            resource_id: Resource ID to unlock
            lock_owner: Lock owner ID
            
        Returns:
            True if lock released
        """
        async with DaprClient() as client:
            try:
                response = await client.unlock(
                    store_name=store_name,
                    resource_id=resource_id,
                    lock_owner=lock_owner
                )
                
                if response.status == 0:
                    logger.debug(f"✅ Lock released: {resource_id}")
                    return True
                else:
                    logger.debug(f"Lock release failed: {resource_id}")
                    return False
            
            except Exception as e:
                logger.error(f"❌ Unlock failed: {resource_id}: {e}")
                raise
    
    # ========================================================================
    # Metrics
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, int]:
        """Get client metrics."""
        return {
            "service_invocations": self.service_invocations,
            "state_operations": self.state_operations,
            "pubsub_operations": self.pubsub_operations
        }


# Example usage
async def main():
    """Example usage of Dapr client."""
    client = AgentBankingDaprClient()
    
    # Service invocation
    balance = await client.invoke_service(
        app_id="wallet-service",
        method="get-balance",
        data={"user_id": "agent-001"}
    )
    print(f"Balance: {balance}")
    
    # State management
    await client.save_state(
        key="user-session-123",
        value={"user_id": "agent-001", "login_time": datetime.utcnow().isoformat()}
    )
    
    session = await client.get_state("user-session-123")
    print(f"Session: {session}")
    
    # Pub/Sub
    await client.publish_event(
        topic="transactions.created",
        data={"transaction_id": "txn-123", "amount": 10000}
    )
    
    # Get metrics
    metrics = client.get_metrics()
    print(f"Metrics: {metrics}")


if __name__ == "__main__":
    asyncio.run(main())

