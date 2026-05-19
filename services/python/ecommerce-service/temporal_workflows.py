"""
Temporal Workflows Module
Implements distributed transaction workflows for e-commerce operations
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy

from service_config import get_config

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class OrderItem:
    """Order item for workflow"""
    product_id: str
    variant_id: Optional[str]
    sku: str
    quantity: int
    unit_price: float
    warehouse_id: str


@dataclass
class OrderRequest:
    """Order creation request"""
    order_id: str
    customer_id: str
    idempotency_key: str
    items: List[Dict[str, Any]]
    shipping_address: Dict[str, str]
    payment_method: str
    payment_details: Dict[str, Any]
    total_amount: float
    currency: str = "NGN"


@dataclass
class OrderResult:
    """Order workflow result"""
    order_id: str
    status: str
    payment_id: Optional[str]
    reservation_ids: List[str]
    error: Optional[str] = None


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "pending"
    INVENTORY_RESERVED = "inventory_reserved"
    PAYMENT_PROCESSING = "payment_processing"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_FAILED = "payment_failed"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ============================================================================
# Activities
# ============================================================================

@activity.defn
async def reserve_inventory_activity(
    order_id: str,
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Reserve inventory for order items
    
    This activity calls the inventory reservation service to reserve
    stock for all items in the order.
    """
    from inventory_reservation import InventoryReservationManager, InsufficientInventoryError
    import asyncpg
    import redis.asyncio as redis
    
    config = get_config()
    
    # Create connections
    db_pool = await asyncpg.create_pool(config.database.async_url)
    redis_client = redis.from_url(config.redis.url)
    
    try:
        reservation_manager = InventoryReservationManager(db_pool, redis_client)
        await reservation_manager.initialize()
        
        reservations = await reservation_manager.reserve(
            order_id=order_id,
            items=items,
            timeout_minutes=config.inventory.reservation_timeout_minutes
        )
        
        return {
            "success": True,
            "reservation_ids": [r.id for r in reservations],
            "expires_at": reservations[0].expires_at.isoformat() if reservations else None
        }
    except InsufficientInventoryError as e:
        return {
            "success": False,
            "error": str(e),
            "reservation_ids": []
        }
    finally:
        await db_pool.close()
        await redis_client.close()


@activity.defn
async def release_inventory_activity(
    order_id: str,
    reason: str = "order_cancelled"
) -> Dict[str, Any]:
    """
    Release inventory reservations for an order
    """
    from inventory_reservation import InventoryReservationManager
    import asyncpg
    import redis.asyncio as redis
    
    config = get_config()
    
    db_pool = await asyncpg.create_pool(config.database.async_url)
    redis_client = redis.from_url(config.redis.url)
    
    try:
        reservation_manager = InventoryReservationManager(db_pool, redis_client)
        released = await reservation_manager.release(order_id, reason)
        
        return {
            "success": True,
            "released_count": released
        }
    finally:
        await db_pool.close()
        await redis_client.close()


@activity.defn
async def fulfill_inventory_activity(order_id: str) -> Dict[str, Any]:
    """
    Fulfill inventory reservations (convert to actual sale)
    """
    from inventory_reservation import InventoryReservationManager
    import asyncpg
    import redis.asyncio as redis
    
    config = get_config()
    
    db_pool = await asyncpg.create_pool(config.database.async_url)
    redis_client = redis.from_url(config.redis.url)
    
    try:
        reservation_manager = InventoryReservationManager(db_pool, redis_client)
        fulfilled = await reservation_manager.fulfill(order_id)
        
        return {
            "success": True,
            "fulfilled_count": fulfilled
        }
    finally:
        await db_pool.close()
        await redis_client.close()


@activity.defn
async def process_payment_activity(
    order_id: str,
    customer_id: str,
    amount: float,
    currency: str,
    payment_method: str,
    payment_details: Dict[str, Any],
    idempotency_key: str
) -> Dict[str, Any]:
    """
    Process payment for order
    """
    from circuit_breaker import get_payment_client
    
    config = get_config()
    payment_client = get_payment_client(config.endpoints.payment_gateway)
    
    try:
        response = await payment_client.post(
            "/payments/process",
            json={
                "order_id": order_id,
                "customer_id": customer_id,
                "amount": amount,
                "currency": currency,
                "payment_method": payment_method,
                "payment_details": payment_details,
                "idempotency_key": idempotency_key
            }
        )
        
        data = response.json()
        return {
            "success": data.get("status") == "completed",
            "payment_id": data.get("payment_id"),
            "status": data.get("status"),
            "error": data.get("error")
        }
    except Exception as e:
        return {
            "success": False,
            "payment_id": None,
            "status": "failed",
            "error": str(e)
        }
    finally:
        await payment_client.close()


@activity.defn
async def refund_payment_activity(
    payment_id: str,
    amount: float,
    reason: str
) -> Dict[str, Any]:
    """
    Refund payment
    """
    from circuit_breaker import get_payment_client
    
    config = get_config()
    payment_client = get_payment_client(config.endpoints.payment_gateway)
    
    try:
        response = await payment_client.post(
            f"/payments/{payment_id}/refund",
            json={
                "amount": amount,
                "reason": reason
            }
        )
        
        data = response.json()
        return {
            "success": data.get("status") == "refunded",
            "refund_id": data.get("refund_id"),
            "error": data.get("error")
        }
    except Exception as e:
        return {
            "success": False,
            "refund_id": None,
            "error": str(e)
        }
    finally:
        await payment_client.close()


@activity.defn
async def update_order_status_activity(
    order_id: str,
    status: str,
    payment_id: Optional[str] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update order status in database
    """
    import asyncpg
    
    config = get_config()
    
    conn = await asyncpg.connect(config.database.async_url)
    
    try:
        await conn.execute("""
            UPDATE orders
            SET status = $1, 
                payment_id = COALESCE($2, payment_id),
                error_message = $3,
                updated_at = NOW()
            WHERE id = $4
        """, status, payment_id, error, order_id)
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await conn.close()


@activity.defn
async def send_order_confirmation_activity(
    order_id: str,
    customer_id: str,
    customer_email: str
) -> Dict[str, Any]:
    """
    Send order confirmation email
    """
    from circuit_breaker import get_email_client
    
    config = get_config()
    email_client = get_email_client(config.endpoints.email_service)
    
    try:
        response = await email_client.post(
            "/emails/send",
            json={
                "template": "order_confirmation",
                "to": customer_email,
                "data": {
                    "order_id": order_id,
                    "customer_id": customer_id
                }
            }
        )
        
        return {"success": response.status_code == 200}
    except Exception as e:
        # Email failure should not fail the order
        logger.error(f"Failed to send order confirmation: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await email_client.close()


@activity.defn
async def publish_order_event_activity(
    order_id: str,
    event_type: str,
    event_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Publish order event to Kafka
    """
    from aiokafka import AIOKafkaProducer
    import json
    from datetime import datetime
    import uuid
    
    config = get_config()
    
    producer = AIOKafkaProducer(
        bootstrap_servers=config.kafka.bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8")
    )
    
    try:
        await producer.start()
        
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "order_id": order_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": event_data
        }
        
        await producer.send_and_wait(config.kafka.order_events_topic, event)
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to publish order event: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await producer.stop()


# ============================================================================
# Workflows
# ============================================================================

@workflow.defn
class OrderCreationWorkflow:
    """
    Distributed transaction workflow for order creation
    
    This workflow ensures atomic order creation with:
    1. Inventory reservation
    2. Payment processing
    3. Order confirmation
    4. Automatic compensation on failure
    """
    
    @workflow.run
    async def run(self, request: OrderRequest) -> OrderResult:
        """Execute order creation workflow"""
        
        reservation_ids = []
        payment_id = None
        
        try:
            # Step 1: Reserve inventory
            workflow.logger.info(f"Reserving inventory for order {request.order_id}")
            
            reserve_result = await workflow.execute_activity(
                reserve_inventory_activity,
                args=[request.order_id, request.items],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10)
                )
            )
            
            if not reserve_result["success"]:
                await self._update_order_status(request.order_id, OrderStatus.CANCELLED.value, error=reserve_result.get("error"))
                return OrderResult(
                    order_id=request.order_id,
                    status=OrderStatus.CANCELLED.value,
                    payment_id=None,
                    reservation_ids=[],
                    error=reserve_result.get("error", "Inventory reservation failed")
                )
            
            reservation_ids = reserve_result["reservation_ids"]
            await self._update_order_status(request.order_id, OrderStatus.INVENTORY_RESERVED.value)
            
            # Step 2: Process payment
            workflow.logger.info(f"Processing payment for order {request.order_id}")
            await self._update_order_status(request.order_id, OrderStatus.PAYMENT_PROCESSING.value)
            
            payment_result = await workflow.execute_activity(
                process_payment_activity,
                args=[
                    request.order_id,
                    request.customer_id,
                    request.total_amount,
                    request.currency,
                    request.payment_method,
                    request.payment_details,
                    request.idempotency_key
                ],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30)
                )
            )
            
            if not payment_result["success"]:
                # Compensate: Release inventory
                workflow.logger.info(f"Payment failed, releasing inventory for order {request.order_id}")
                await workflow.execute_activity(
                    release_inventory_activity,
                    args=[request.order_id, "payment_failed"],
                    start_to_close_timeout=timedelta(seconds=30)
                )
                
                await self._update_order_status(
                    request.order_id, 
                    OrderStatus.PAYMENT_FAILED.value,
                    error=payment_result.get("error")
                )
                
                return OrderResult(
                    order_id=request.order_id,
                    status=OrderStatus.PAYMENT_FAILED.value,
                    payment_id=None,
                    reservation_ids=reservation_ids,
                    error=payment_result.get("error", "Payment processing failed")
                )
            
            payment_id = payment_result["payment_id"]
            await self._update_order_status(
                request.order_id, 
                OrderStatus.PAYMENT_COMPLETED.value,
                payment_id=payment_id
            )
            
            # Step 3: Fulfill inventory (convert reservation to sale)
            workflow.logger.info(f"Fulfilling inventory for order {request.order_id}")
            
            fulfill_result = await workflow.execute_activity(
                fulfill_inventory_activity,
                args=[request.order_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1)
                )
            )
            
            if not fulfill_result["success"]:
                # This is a critical error - payment succeeded but fulfillment failed
                # Log for manual intervention
                workflow.logger.error(
                    f"CRITICAL: Fulfillment failed for order {request.order_id} "
                    f"after successful payment {payment_id}"
                )
            
            # Step 4: Confirm order
            await self._update_order_status(request.order_id, OrderStatus.CONFIRMED.value, payment_id=payment_id)
            
            # Step 5: Publish event (non-blocking)
            await workflow.execute_activity(
                publish_order_event_activity,
                args=[request.order_id, "order.confirmed", {
                    "customer_id": request.customer_id,
                    "total_amount": request.total_amount,
                    "items_count": len(request.items)
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Step 6: Send confirmation email (non-blocking)
            # Note: We don't await this as email failure shouldn't affect order
            workflow.execute_activity(
                send_order_confirmation_activity,
                args=[request.order_id, request.customer_id, request.payment_details.get("email", "")],
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            workflow.logger.info(f"Order {request.order_id} completed successfully")
            
            return OrderResult(
                order_id=request.order_id,
                status=OrderStatus.CONFIRMED.value,
                payment_id=payment_id,
                reservation_ids=reservation_ids
            )
            
        except Exception as e:
            workflow.logger.error(f"Order workflow failed: {e}")
            
            # Compensate based on what was completed
            if reservation_ids:
                await workflow.execute_activity(
                    release_inventory_activity,
                    args=[request.order_id, f"workflow_error: {str(e)}"],
                    start_to_close_timeout=timedelta(seconds=30)
                )
            
            if payment_id:
                await workflow.execute_activity(
                    refund_payment_activity,
                    args=[payment_id, request.total_amount, f"workflow_error: {str(e)}"],
                    start_to_close_timeout=timedelta(seconds=60)
                )
            
            await self._update_order_status(request.order_id, OrderStatus.CANCELLED.value, error=str(e))
            
            return OrderResult(
                order_id=request.order_id,
                status=OrderStatus.CANCELLED.value,
                payment_id=payment_id,
                reservation_ids=reservation_ids,
                error=str(e)
            )
    
    async def _update_order_status(
        self,
        order_id: str,
        status: str,
        payment_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Helper to update order status"""
        await workflow.execute_activity(
            update_order_status_activity,
            args=[order_id, status, payment_id, error],
            start_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn
class OrderCancellationWorkflow:
    """
    Workflow for order cancellation with compensation
    """
    
    @workflow.run
    async def run(self, order_id: str, payment_id: Optional[str], reason: str) -> Dict[str, Any]:
        """Execute order cancellation"""
        
        # Release inventory
        release_result = await workflow.execute_activity(
            release_inventory_activity,
            args=[order_id, reason],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Refund payment if exists
        refund_result = None
        if payment_id:
            # Get order amount from database
            refund_result = await workflow.execute_activity(
                refund_payment_activity,
                args=[payment_id, 0, reason],  # Amount will be fetched from payment record
                start_to_close_timeout=timedelta(seconds=60)
            )
        
        # Update order status
        await workflow.execute_activity(
            update_order_status_activity,
            args=[order_id, OrderStatus.CANCELLED.value, None, reason],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Publish event
        await workflow.execute_activity(
            publish_order_event_activity,
            args=[order_id, "order.cancelled", {"reason": reason}],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {
            "order_id": order_id,
            "status": "cancelled",
            "inventory_released": release_result.get("released_count", 0) if release_result else 0,
            "refund_success": refund_result.get("success") if refund_result else None
        }


# ============================================================================
# Worker and Client
# ============================================================================

class TemporalOrderService:
    """
    Service for interacting with Temporal workflows
    """
    
    def __init__(self):
        self.config = get_config()
        self._client: Optional[Client] = None
        self._worker: Optional[Worker] = None
    
    async def connect(self):
        """Connect to Temporal server"""
        self._client = await Client.connect(self.config.temporal.address)
        logger.info(f"Connected to Temporal at {self.config.temporal.address}")
    
    async def start_worker(self):
        """Start Temporal worker"""
        if not self._client:
            await self.connect()
        
        self._worker = Worker(
            self._client,
            task_queue=self.config.temporal.task_queue,
            workflows=[OrderCreationWorkflow, OrderCancellationWorkflow],
            activities=[
                reserve_inventory_activity,
                release_inventory_activity,
                fulfill_inventory_activity,
                process_payment_activity,
                refund_payment_activity,
                update_order_status_activity,
                send_order_confirmation_activity,
                publish_order_event_activity
            ]
        )
        
        logger.info(f"Starting Temporal worker on task queue: {self.config.temporal.task_queue}")
        await self._worker.run()
    
    async def create_order(self, request: OrderRequest) -> OrderResult:
        """Start order creation workflow"""
        if not self._client:
            await self.connect()
        
        handle = await self._client.start_workflow(
            OrderCreationWorkflow.run,
            request,
            id=f"order-{request.order_id}",
            task_queue=self.config.temporal.task_queue
        )
        
        logger.info(f"Started order workflow: {handle.id}")
        
        # Wait for result
        result = await handle.result()
        return result
    
    async def cancel_order(
        self,
        order_id: str,
        payment_id: Optional[str],
        reason: str
    ) -> Dict[str, Any]:
        """Start order cancellation workflow"""
        if not self._client:
            await self.connect()
        
        handle = await self._client.start_workflow(
            OrderCancellationWorkflow.run,
            args=[order_id, payment_id, reason],
            id=f"cancel-order-{order_id}",
            task_queue=self.config.temporal.task_queue
        )
        
        logger.info(f"Started cancellation workflow: {handle.id}")
        
        result = await handle.result()
        return result
    
    async def close(self):
        """Close connections"""
        if self._worker:
            self._worker.shutdown()
        logger.info("Temporal service closed")


# Global service instance
temporal_service = TemporalOrderService()
