"""
Saga Orchestrator for E-commerce Transactions
Implements the Saga pattern with Outbox for reliable cross-service transactions
Ensures data consistency across Order, Inventory, Payment, and Shipment services
"""

import os
import json
import uuid
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
import asyncpg
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class SagaStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SagaStep:
    name: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    compensation_result: Optional[Dict[str, Any]] = None


@dataclass
class SagaState:
    saga_id: str
    saga_type: str
    status: SagaStatus
    idempotency_key: str
    payload: Dict[str, Any]
    steps: List[SagaStep] = field(default_factory=list)
    current_step: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboxMessage:
    message_id: str
    saga_id: str
    event_type: str
    payload: Dict[str, Any]
    destination: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 5
    status: str = "pending"


class SagaRepository:
    """Repository for saga state persistence"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def initialize_schema(self):
        """Create saga tables if they don't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sagas (
                    saga_id UUID PRIMARY KEY,
                    saga_type VARCHAR(100) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
                    payload JSONB NOT NULL,
                    steps JSONB NOT NULL DEFAULT '[]',
                    current_step INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    error TEXT,
                    metadata JSONB NOT NULL DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS idx_sagas_status ON sagas(status);
                CREATE INDEX IF NOT EXISTS idx_sagas_type ON sagas(saga_type);
                CREATE INDEX IF NOT EXISTS idx_sagas_idempotency ON sagas(idempotency_key);
                CREATE INDEX IF NOT EXISTS idx_sagas_created ON sagas(created_at);
                
                CREATE TABLE IF NOT EXISTS outbox_messages (
                    message_id UUID PRIMARY KEY,
                    saga_id UUID NOT NULL REFERENCES sagas(saga_id),
                    event_type VARCHAR(100) NOT NULL,
                    payload JSONB NOT NULL,
                    destination VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    processed_at TIMESTAMP,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 5,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending'
                );
                
                CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox_messages(status);
                CREATE INDEX IF NOT EXISTS idx_outbox_saga ON outbox_messages(saga_id);
                CREATE INDEX IF NOT EXISTS idx_outbox_created ON outbox_messages(created_at);
            """)
    
    async def create_saga(self, state: SagaState) -> SagaState:
        """Create a new saga"""
        async with self.pool.acquire() as conn:
            steps_json = json.dumps([asdict(s) for s in state.steps], default=str)
            
            await conn.execute("""
                INSERT INTO sagas (
                    saga_id, saga_type, status, idempotency_key, payload,
                    steps, current_step, created_at, updated_at, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                uuid.UUID(state.saga_id),
                state.saga_type,
                state.status.value,
                state.idempotency_key,
                json.dumps(state.payload),
                steps_json,
                state.current_step,
                state.created_at,
                state.updated_at,
                json.dumps(state.metadata)
            )
            
            return state
    
    async def get_saga(self, saga_id: str) -> Optional[SagaState]:
        """Get saga by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sagas WHERE saga_id = $1",
                uuid.UUID(saga_id)
            )
            
            if not row:
                return None
            
            return self._row_to_state(row)
    
    async def get_saga_by_idempotency_key(self, key: str) -> Optional[SagaState]:
        """Get saga by idempotency key"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sagas WHERE idempotency_key = $1",
                key
            )
            
            if not row:
                return None
            
            return self._row_to_state(row)
    
    async def update_saga(self, state: SagaState) -> SagaState:
        """Update saga state"""
        state.updated_at = datetime.utcnow()
        
        async with self.pool.acquire() as conn:
            steps_json = json.dumps([asdict(s) for s in state.steps], default=str)
            
            await conn.execute("""
                UPDATE sagas SET
                    status = $2,
                    steps = $3,
                    current_step = $4,
                    updated_at = $5,
                    completed_at = $6,
                    error = $7,
                    metadata = $8
                WHERE saga_id = $1
            """,
                uuid.UUID(state.saga_id),
                state.status.value,
                steps_json,
                state.current_step,
                state.updated_at,
                state.completed_at,
                state.error,
                json.dumps(state.metadata)
            )
            
            return state
    
    async def get_pending_sagas(self, saga_type: Optional[str] = None, limit: int = 100) -> List[SagaState]:
        """Get pending or running sagas for recovery"""
        async with self.pool.acquire() as conn:
            if saga_type:
                rows = await conn.fetch("""
                    SELECT * FROM sagas
                    WHERE status IN ('pending', 'running', 'compensating')
                    AND saga_type = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                """, saga_type, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM sagas
                    WHERE status IN ('pending', 'running', 'compensating')
                    ORDER BY created_at ASC
                    LIMIT $1
                """, limit)
            
            return [self._row_to_state(row) for row in rows]
    
    async def add_outbox_message(self, message: OutboxMessage) -> OutboxMessage:
        """Add message to outbox"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO outbox_messages (
                    message_id, saga_id, event_type, payload, destination,
                    created_at, status, retry_count, max_retries
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                uuid.UUID(message.message_id),
                uuid.UUID(message.saga_id),
                message.event_type,
                json.dumps(message.payload),
                message.destination,
                message.created_at,
                message.status,
                message.retry_count,
                message.max_retries
            )
            
            return message
    
    async def get_pending_outbox_messages(self, limit: int = 100) -> List[OutboxMessage]:
        """Get pending outbox messages"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM outbox_messages
                WHERE status = 'pending' AND retry_count < max_retries
                ORDER BY created_at ASC
                LIMIT $1
            """, limit)
            
            return [self._row_to_outbox(row) for row in rows]
    
    async def mark_outbox_processed(self, message_id: str):
        """Mark outbox message as processed"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE outbox_messages
                SET status = 'processed', processed_at = NOW()
                WHERE message_id = $1
            """, uuid.UUID(message_id))
    
    async def increment_outbox_retry(self, message_id: str):
        """Increment retry count for outbox message"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE outbox_messages
                SET retry_count = retry_count + 1
                WHERE message_id = $1
            """, uuid.UUID(message_id))
    
    async def mark_outbox_failed(self, message_id: str):
        """Mark outbox message as failed"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE outbox_messages
                SET status = 'failed'
                WHERE message_id = $1
            """, uuid.UUID(message_id))
    
    def _row_to_state(self, row) -> SagaState:
        """Convert database row to SagaState"""
        steps_data = json.loads(row['steps']) if isinstance(row['steps'], str) else row['steps']
        steps = []
        for s in steps_data:
            step = SagaStep(
                name=s['name'],
                status=StepStatus(s['status']),
                started_at=datetime.fromisoformat(s['started_at']) if s.get('started_at') else None,
                completed_at=datetime.fromisoformat(s['completed_at']) if s.get('completed_at') else None,
                result=s.get('result'),
                error=s.get('error'),
                compensation_result=s.get('compensation_result')
            )
            steps.append(step)
        
        return SagaState(
            saga_id=str(row['saga_id']),
            saga_type=row['saga_type'],
            status=SagaStatus(row['status']),
            idempotency_key=row['idempotency_key'],
            payload=json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload'],
            steps=steps,
            current_step=row['current_step'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            completed_at=row['completed_at'],
            error=row['error'],
            metadata=json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
        )
    
    def _row_to_outbox(self, row) -> OutboxMessage:
        """Convert database row to OutboxMessage"""
        return OutboxMessage(
            message_id=str(row['message_id']),
            saga_id=str(row['saga_id']),
            event_type=row['event_type'],
            payload=json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload'],
            destination=row['destination'],
            created_at=row['created_at'],
            processed_at=row['processed_at'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            status=row['status']
        )


class SagaDefinition(ABC):
    """Abstract base class for saga definitions"""
    
    @property
    @abstractmethod
    def saga_type(self) -> str:
        """Return the saga type identifier"""
        pass
    
    @property
    @abstractmethod
    def steps(self) -> List[str]:
        """Return the list of step names in order"""
        pass
    
    @abstractmethod
    async def execute_step(
        self,
        step_name: str,
        payload: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a saga step"""
        pass
    
    @abstractmethod
    async def compensate_step(
        self,
        step_name: str,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate a saga step"""
        pass


class OrderFulfillmentSaga(SagaDefinition):
    """Saga for order fulfillment: Order -> Payment -> Inventory -> Shipment"""
    
    def __init__(
        self,
        order_service: Any,
        payment_service: Any,
        inventory_service: Any,
        shipment_service: Any,
        notification_service: Any
    ):
        self.order_service = order_service
        self.payment_service = payment_service
        self.inventory_service = inventory_service
        self.shipment_service = shipment_service
        self.notification_service = notification_service
    
    @property
    def saga_type(self) -> str:
        return "order_fulfillment"
    
    @property
    def steps(self) -> List[str]:
        return [
            "validate_order",
            "reserve_inventory",
            "process_payment",
            "confirm_order",
            "create_shipment",
            "send_confirmation"
        ]
    
    async def execute_step(
        self,
        step_name: str,
        payload: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a saga step"""
        if step_name == "validate_order":
            return await self._validate_order(payload, context)
        elif step_name == "reserve_inventory":
            return await self._reserve_inventory(payload, context)
        elif step_name == "process_payment":
            return await self._process_payment(payload, context)
        elif step_name == "confirm_order":
            return await self._confirm_order(payload, context)
        elif step_name == "create_shipment":
            return await self._create_shipment(payload, context)
        elif step_name == "send_confirmation":
            return await self._send_confirmation(payload, context)
        else:
            raise ValueError(f"Unknown step: {step_name}")
    
    async def compensate_step(
        self,
        step_name: str,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate a saga step"""
        if step_name == "validate_order":
            return await self._compensate_validate_order(payload, context, step_result)
        elif step_name == "reserve_inventory":
            return await self._compensate_reserve_inventory(payload, context, step_result)
        elif step_name == "process_payment":
            return await self._compensate_process_payment(payload, context, step_result)
        elif step_name == "confirm_order":
            return await self._compensate_confirm_order(payload, context, step_result)
        elif step_name == "create_shipment":
            return await self._compensate_create_shipment(payload, context, step_result)
        elif step_name == "send_confirmation":
            return {"status": "skipped"}
        else:
            raise ValueError(f"Unknown step: {step_name}")
    
    async def _validate_order(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate order details"""
        order_id = payload.get("order_id")
        
        order = await self.order_service.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.get("status") not in ["pending", "created"]:
            raise ValueError(f"Order {order_id} is not in valid state for fulfillment")
        
        for item in order.get("items", []):
            product = await self.inventory_service.get_product(item["product_id"])
            if not product:
                raise ValueError(f"Product {item['product_id']} not found")
            if product.get("available_quantity", 0) < item["quantity"]:
                raise ValueError(f"Insufficient stock for product {item['product_id']}")
        
        return {
            "order_id": order_id,
            "order": order,
            "validated_at": datetime.utcnow().isoformat()
        }
    
    async def _reserve_inventory(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Reserve inventory for order items"""
        order = context.get("validate_order", {}).get("order", {})
        order_id = payload.get("order_id")
        
        reservations = []
        for item in order.get("items", []):
            reservation = await self.inventory_service.reserve_inventory(
                product_id=item["product_id"],
                quantity=item["quantity"],
                order_id=order_id,
                expiry_minutes=30
            )
            reservations.append(reservation)
        
        return {
            "reservations": reservations,
            "reserved_at": datetime.utcnow().isoformat()
        }
    
    async def _process_payment(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment for order"""
        order = context.get("validate_order", {}).get("order", {})
        order_id = payload.get("order_id")
        
        payment_result = await self.payment_service.process_payment(
            order_id=order_id,
            amount=order.get("total"),
            currency=order.get("currency", "USD"),
            payment_method=order.get("payment_method"),
            idempotency_key=f"order-{order_id}-payment"
        )
        
        if payment_result.get("status") != "success":
            raise ValueError(f"Payment failed: {payment_result.get('error')}")
        
        return {
            "payment_id": payment_result.get("payment_id"),
            "transaction_id": payment_result.get("transaction_id"),
            "amount": payment_result.get("amount"),
            "processed_at": datetime.utcnow().isoformat()
        }
    
    async def _confirm_order(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Confirm order after payment"""
        order_id = payload.get("order_id")
        payment_result = context.get("process_payment", {})
        
        await self.order_service.update_order_status(
            order_id=order_id,
            status="confirmed",
            payment_id=payment_result.get("payment_id")
        )
        
        reservations = context.get("reserve_inventory", {}).get("reservations", [])
        for reservation in reservations:
            await self.inventory_service.confirm_reservation(reservation.get("reservation_id"))
        
        return {
            "confirmed_at": datetime.utcnow().isoformat()
        }
    
    async def _create_shipment(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Create shipment for order"""
        order = context.get("validate_order", {}).get("order", {})
        order_id = payload.get("order_id")
        
        shipment = await self.shipment_service.create_shipment(
            order_id=order_id,
            items=order.get("items", []),
            shipping_address=order.get("shipping_address"),
            shipping_method=order.get("shipping_method")
        )
        
        await self.order_service.update_order_status(
            order_id=order_id,
            status="processing",
            shipment_id=shipment.get("shipment_id")
        )
        
        return {
            "shipment_id": shipment.get("shipment_id"),
            "tracking_number": shipment.get("tracking_number"),
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def _send_confirmation(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Send order confirmation notification"""
        order = context.get("validate_order", {}).get("order", {})
        shipment = context.get("create_shipment", {})
        
        await self.notification_service.send_order_confirmation(
            customer_email=order.get("customer_email"),
            order_id=payload.get("order_id"),
            order_number=order.get("order_number"),
            tracking_number=shipment.get("tracking_number"),
            items=order.get("items", []),
            total=order.get("total")
        )
        
        return {
            "notification_sent": True,
            "sent_at": datetime.utcnow().isoformat()
        }
    
    async def _compensate_validate_order(
        self,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate order validation - mark order as failed"""
        order_id = payload.get("order_id")
        
        await self.order_service.update_order_status(
            order_id=order_id,
            status="failed",
            error="Order fulfillment saga failed"
        )
        
        return {"compensated": True}
    
    async def _compensate_reserve_inventory(
        self,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate inventory reservation - release reserved inventory"""
        reservations = step_result.get("reservations", [])
        
        for reservation in reservations:
            await self.inventory_service.release_reservation(reservation.get("reservation_id"))
        
        return {"released_reservations": len(reservations)}
    
    async def _compensate_process_payment(
        self,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate payment - refund"""
        payment_id = step_result.get("payment_id")
        
        refund_result = await self.payment_service.refund_payment(
            payment_id=payment_id,
            reason="Order fulfillment failed"
        )
        
        return {
            "refund_id": refund_result.get("refund_id"),
            "refunded_amount": refund_result.get("amount")
        }
    
    async def _compensate_confirm_order(
        self,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate order confirmation - revert to pending"""
        order_id = payload.get("order_id")
        
        await self.order_service.update_order_status(
            order_id=order_id,
            status="cancelled",
            error="Order fulfillment saga rolled back"
        )
        
        return {"compensated": True}
    
    async def _compensate_create_shipment(
        self,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compensate shipment creation - cancel shipment"""
        shipment_id = step_result.get("shipment_id")
        
        await self.shipment_service.cancel_shipment(shipment_id)
        
        return {"cancelled_shipment": shipment_id}


class SagaOrchestrator:
    """Orchestrates saga execution with compensation on failure"""
    
    def __init__(self, repository: SagaRepository):
        self.repository = repository
        self.definitions: Dict[str, SagaDefinition] = {}
        self._running = False
        self._recovery_task: Optional[asyncio.Task] = None
    
    def register_saga(self, definition: SagaDefinition):
        """Register a saga definition"""
        self.definitions[definition.saga_type] = definition
        logger.info(f"Registered saga: {definition.saga_type}")
    
    async def start_saga(
        self,
        saga_type: str,
        payload: Dict[str, Any],
        idempotency_key: str
    ) -> SagaState:
        """Start a new saga or return existing one for idempotency key"""
        existing = await self.repository.get_saga_by_idempotency_key(idempotency_key)
        if existing:
            logger.info(f"Found existing saga for idempotency key: {idempotency_key}")
            return existing
        
        definition = self.definitions.get(saga_type)
        if not definition:
            raise ValueError(f"Unknown saga type: {saga_type}")
        
        steps = [SagaStep(name=name) for name in definition.steps]
        
        state = SagaState(
            saga_id=str(uuid.uuid4()),
            saga_type=saga_type,
            status=SagaStatus.PENDING,
            idempotency_key=idempotency_key,
            payload=payload,
            steps=steps
        )
        
        await self.repository.create_saga(state)
        logger.info(f"Created saga {state.saga_id} of type {saga_type}")
        
        asyncio.create_task(self._execute_saga(state))
        
        return state
    
    async def _execute_saga(self, state: SagaState):
        """Execute saga steps"""
        definition = self.definitions.get(state.saga_type)
        if not definition:
            return
        
        state.status = SagaStatus.RUNNING
        await self.repository.update_saga(state)
        
        context: Dict[str, Any] = {}
        
        try:
            for i, step in enumerate(state.steps):
                if step.status == StepStatus.COMPLETED:
                    context[step.name] = step.result
                    continue
                
                state.current_step = i
                step.status = StepStatus.RUNNING
                step.started_at = datetime.utcnow()
                await self.repository.update_saga(state)
                
                logger.info(f"Executing step {step.name} for saga {state.saga_id}")
                
                try:
                    result = await definition.execute_step(step.name, state.payload, context)
                    
                    step.status = StepStatus.COMPLETED
                    step.completed_at = datetime.utcnow()
                    step.result = result
                    context[step.name] = result
                    
                    await self.repository.update_saga(state)
                    
                    await self._publish_step_event(state, step, "completed")
                    
                except Exception as e:
                    logger.error(f"Step {step.name} failed for saga {state.saga_id}: {e}")
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    await self.repository.update_saga(state)
                    
                    await self._compensate_saga(state, context, i)
                    return
            
            state.status = SagaStatus.COMPLETED
            state.completed_at = datetime.utcnow()
            await self.repository.update_saga(state)
            
            await self._publish_saga_event(state, "completed")
            logger.info(f"Saga {state.saga_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Saga {state.saga_id} failed: {e}")
            state.status = SagaStatus.FAILED
            state.error = str(e)
            await self.repository.update_saga(state)
    
    async def _compensate_saga(self, state: SagaState, context: Dict[str, Any], failed_step_index: int):
        """Compensate saga by rolling back completed steps"""
        definition = self.definitions.get(state.saga_type)
        if not definition:
            return
        
        state.status = SagaStatus.COMPENSATING
        await self.repository.update_saga(state)
        
        logger.info(f"Starting compensation for saga {state.saga_id} from step {failed_step_index}")
        
        for i in range(failed_step_index - 1, -1, -1):
            step = state.steps[i]
            
            if step.status != StepStatus.COMPLETED:
                continue
            
            step.status = StepStatus.COMPENSATING
            await self.repository.update_saga(state)
            
            try:
                logger.info(f"Compensating step {step.name} for saga {state.saga_id}")
                
                compensation_result = await definition.compensate_step(
                    step.name,
                    state.payload,
                    context,
                    step.result or {}
                )
                
                step.status = StepStatus.COMPENSATED
                step.compensation_result = compensation_result
                await self.repository.update_saga(state)
                
                await self._publish_step_event(state, step, "compensated")
                
            except Exception as e:
                logger.error(f"Compensation failed for step {step.name} in saga {state.saga_id}: {e}")
                step.status = StepStatus.FAILED
                step.error = f"Compensation failed: {e}"
                await self.repository.update_saga(state)
        
        state.status = SagaStatus.COMPENSATED
        state.completed_at = datetime.utcnow()
        await self.repository.update_saga(state)
        
        await self._publish_saga_event(state, "compensated")
        logger.info(f"Saga {state.saga_id} compensation completed")
    
    async def _publish_step_event(self, state: SagaState, step: SagaStep, event_type: str):
        """Publish step event to outbox"""
        message = OutboxMessage(
            message_id=str(uuid.uuid4()),
            saga_id=state.saga_id,
            event_type=f"saga.step.{event_type}",
            payload={
                "saga_id": state.saga_id,
                "saga_type": state.saga_type,
                "step_name": step.name,
                "step_result": step.result,
                "timestamp": datetime.utcnow().isoformat()
            },
            destination="saga-events"
        )
        
        await self.repository.add_outbox_message(message)
    
    async def _publish_saga_event(self, state: SagaState, event_type: str):
        """Publish saga event to outbox"""
        message = OutboxMessage(
            message_id=str(uuid.uuid4()),
            saga_id=state.saga_id,
            event_type=f"saga.{event_type}",
            payload={
                "saga_id": state.saga_id,
                "saga_type": state.saga_type,
                "status": state.status.value,
                "payload": state.payload,
                "timestamp": datetime.utcnow().isoformat()
            },
            destination="saga-events"
        )
        
        await self.repository.add_outbox_message(message)
    
    async def start_recovery(self, interval_seconds: int = 60):
        """Start background recovery task"""
        self._running = True
        self._recovery_task = asyncio.create_task(self._recovery_loop(interval_seconds))
        logger.info("Started saga recovery task")
    
    async def stop_recovery(self):
        """Stop background recovery task"""
        self._running = False
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped saga recovery task")
    
    async def _recovery_loop(self, interval_seconds: int):
        """Background loop for recovering stuck sagas"""
        while self._running:
            try:
                await self._recover_sagas()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def _recover_sagas(self):
        """Recover stuck sagas"""
        pending_sagas = await self.repository.get_pending_sagas()
        
        for state in pending_sagas:
            if state.updated_at < datetime.utcnow() - timedelta(minutes=5):
                logger.info(f"Recovering stuck saga {state.saga_id}")
                
                context = {}
                for step in state.steps:
                    if step.status == StepStatus.COMPLETED and step.result:
                        context[step.name] = step.result
                
                asyncio.create_task(self._execute_saga(state))
    
    async def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga status"""
        state = await self.repository.get_saga(saga_id)
        if not state:
            return None
        
        return {
            "saga_id": state.saga_id,
            "saga_type": state.saga_type,
            "status": state.status.value,
            "current_step": state.current_step,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "error": s.error
                }
                for s in state.steps
            ],
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            "error": state.error
        }


class OutboxProcessor:
    """Processes outbox messages and publishes to message broker"""
    
    def __init__(
        self,
        repository: SagaRepository,
        message_publisher: Callable[[str, Dict[str, Any]], Awaitable[bool]]
    ):
        self.repository = repository
        self.message_publisher = message_publisher
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self, interval_seconds: int = 5):
        """Start outbox processor"""
        self._running = True
        self._task = asyncio.create_task(self._process_loop(interval_seconds))
        logger.info("Started outbox processor")
    
    async def stop(self):
        """Stop outbox processor"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped outbox processor")
    
    async def _process_loop(self, interval_seconds: int):
        """Background loop for processing outbox messages"""
        while self._running:
            try:
                await self._process_messages()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Outbox processor error: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def _process_messages(self):
        """Process pending outbox messages"""
        messages = await self.repository.get_pending_outbox_messages()
        
        for message in messages:
            try:
                success = await self.message_publisher(message.destination, message.payload)
                
                if success:
                    await self.repository.mark_outbox_processed(message.message_id)
                    logger.debug(f"Processed outbox message {message.message_id}")
                else:
                    await self.repository.increment_outbox_retry(message.message_id)
                    
                    if message.retry_count + 1 >= message.max_retries:
                        await self.repository.mark_outbox_failed(message.message_id)
                        logger.error(f"Outbox message {message.message_id} failed after max retries")
                        
            except Exception as e:
                logger.error(f"Failed to process outbox message {message.message_id}: {e}")
                await self.repository.increment_outbox_retry(message.message_id)
