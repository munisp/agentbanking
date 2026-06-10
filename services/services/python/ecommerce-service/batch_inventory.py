"""
Batch Inventory Operations Module
Implements efficient batch operations for inventory management
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import asyncpg

from service_config import get_config
from kafka_consumer import InventoryEventProducer, InventoryEvent, InventoryEventType

logger = logging.getLogger(__name__)


class BatchOperationType(str, Enum):
    """Batch operation types"""
    STOCK_UPDATE = "stock_update"
    STOCK_ADJUSTMENT = "stock_adjustment"
    WAREHOUSE_TRANSFER = "warehouse_transfer"
    BULK_RESERVE = "bulk_reserve"
    BULK_RELEASE = "bulk_release"


@dataclass
class BatchItem:
    """Single item in a batch operation"""
    warehouse_id: str
    product_id: str
    sku: str
    quantity: int
    operation: str = "set"  # set, add, subtract
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of a batch operation"""
    batch_id: str
    operation_type: BatchOperationType
    total_items: int
    successful_items: int
    failed_items: int
    errors: List[Dict[str, Any]]
    duration_ms: float
    created_at: datetime


class BatchInventoryService:
    """
    Batch inventory operations service
    
    Features:
    - Bulk stock updates with transaction safety
    - Warehouse transfers in batch
    - Bulk reservations and releases
    - Progress tracking and error reporting
    - Kafka event publishing for each change
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        event_producer: Optional[InventoryEventProducer] = None
    ):
        self.db_pool = db_pool
        self.event_producer = event_producer
        self.config = get_config()
        self.batch_size = self.config.inventory.batch_size
    
    async def bulk_update_stock(
        self,
        items: List[BatchItem],
        reason: str = "bulk_update"
    ) -> BatchResult:
        """
        Bulk update stock quantities
        
        Args:
            items: List of items to update
            reason: Reason for the update
        
        Returns:
            BatchResult with operation summary
        """
        batch_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        successful = 0
        failed = 0
        errors = []
        events = []
        
        # Process in chunks for memory efficiency
        for chunk_start in range(0, len(items), self.batch_size):
            chunk = items[chunk_start:chunk_start + self.batch_size]
            
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    for item in chunk:
                        try:
                            # Get current inventory with lock
                            current = await conn.fetchrow("""
                                SELECT quantity_available, quantity_reserved
                                FROM inventory
                                WHERE warehouse_id = $1 AND product_id = $2
                                FOR UPDATE
                            """, uuid.UUID(item.warehouse_id), uuid.UUID(item.product_id))
                            
                            if not current:
                                # Create new inventory record
                                await conn.execute("""
                                    INSERT INTO inventory (
                                        warehouse_id, product_id, sku,
                                        quantity_available, quantity_reserved,
                                        created_at, updated_at
                                    ) VALUES ($1, $2, $3, $4, 0, NOW(), NOW())
                                """,
                                    uuid.UUID(item.warehouse_id),
                                    uuid.UUID(item.product_id),
                                    item.sku,
                                    item.quantity
                                )
                                new_available = item.quantity
                                quantity_change = item.quantity
                            else:
                                # Calculate new quantity
                                if item.operation == "set":
                                    new_available = item.quantity
                                    quantity_change = item.quantity - current["quantity_available"]
                                elif item.operation == "add":
                                    new_available = current["quantity_available"] + item.quantity
                                    quantity_change = item.quantity
                                elif item.operation == "subtract":
                                    new_available = max(0, current["quantity_available"] - item.quantity)
                                    quantity_change = -min(item.quantity, current["quantity_available"])
                                else:
                                    raise ValueError(f"Invalid operation: {item.operation}")
                                
                                # Update inventory
                                await conn.execute("""
                                    UPDATE inventory
                                    SET quantity_available = $1, updated_at = NOW()
                                    WHERE warehouse_id = $2 AND product_id = $3
                                """, new_available, uuid.UUID(item.warehouse_id), uuid.UUID(item.product_id))
                            
                            # Log the transaction
                            await conn.execute("""
                                INSERT INTO inventory_transactions (
                                    id, warehouse_id, product_id, sku,
                                    transaction_type, quantity_change,
                                    quantity_before, quantity_after,
                                    reason, batch_id, created_at
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                            """,
                                uuid.uuid4(),
                                uuid.UUID(item.warehouse_id),
                                uuid.UUID(item.product_id),
                                item.sku,
                                "bulk_update",
                                quantity_change,
                                current["quantity_available"] if current else 0,
                                new_available,
                                reason,
                                batch_id
                            )
                            
                            # Prepare event
                            events.append(InventoryEvent(
                                event_id=str(uuid.uuid4()),
                                event_type=InventoryEventType.STOCK_UPDATED,
                                timestamp=datetime.utcnow(),
                                warehouse_id=item.warehouse_id,
                                product_id=item.product_id,
                                sku=item.sku,
                                quantity_change=quantity_change,
                                quantity_available=new_available,
                                quantity_reserved=current["quantity_reserved"] if current else 0,
                                metadata={"batch_id": batch_id, "reason": reason}
                            ))
                            
                            successful += 1
                            
                        except Exception as e:
                            failed += 1
                            errors.append({
                                "warehouse_id": item.warehouse_id,
                                "product_id": item.product_id,
                                "sku": item.sku,
                                "error": str(e)
                            })
                            logger.error(f"Failed to update {item.sku}: {e}")
        
        # Publish events
        if self.event_producer and events:
            try:
                await self.event_producer.publish_batch(events)
            except Exception as e:
                logger.error(f"Failed to publish events: {e}")
        
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = BatchResult(
            batch_id=batch_id,
            operation_type=BatchOperationType.STOCK_UPDATE,
            total_items=len(items),
            successful_items=successful,
            failed_items=failed,
            errors=errors,
            duration_ms=duration,
            created_at=start_time
        )
        
        logger.info(
            f"Batch update {batch_id}: {successful}/{len(items)} successful, "
            f"{failed} failed, {duration:.2f}ms"
        )
        
        return result
    
    async def warehouse_transfer(
        self,
        source_warehouse_id: str,
        destination_warehouse_id: str,
        items: List[Tuple[str, str, int]],  # (product_id, sku, quantity)
        reason: str = "warehouse_transfer"
    ) -> BatchResult:
        """
        Transfer inventory between warehouses
        
        Args:
            source_warehouse_id: Source warehouse
            destination_warehouse_id: Destination warehouse
            items: List of (product_id, sku, quantity) tuples
            reason: Reason for transfer
        
        Returns:
            BatchResult with operation summary
        """
        batch_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        successful = 0
        failed = 0
        errors = []
        events = []
        
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for product_id, sku, quantity in items:
                    try:
                        # Lock source inventory
                        source = await conn.fetchrow("""
                            SELECT quantity_available, quantity_reserved
                            FROM inventory
                            WHERE warehouse_id = $1 AND product_id = $2
                            FOR UPDATE
                        """, uuid.UUID(source_warehouse_id), uuid.UUID(product_id))
                        
                        if not source or source["quantity_available"] < quantity:
                            raise ValueError(
                                f"Insufficient stock at source: "
                                f"available {source['quantity_available'] if source else 0}, "
                                f"requested {quantity}"
                            )
                        
                        # Lock or create destination inventory
                        dest = await conn.fetchrow("""
                            SELECT quantity_available, quantity_reserved
                            FROM inventory
                            WHERE warehouse_id = $1 AND product_id = $2
                            FOR UPDATE
                        """, uuid.UUID(destination_warehouse_id), uuid.UUID(product_id))
                        
                        # Decrease source
                        await conn.execute("""
                            UPDATE inventory
                            SET quantity_available = quantity_available - $1, updated_at = NOW()
                            WHERE warehouse_id = $2 AND product_id = $3
                        """, quantity, uuid.UUID(source_warehouse_id), uuid.UUID(product_id))
                        
                        # Increase destination
                        if dest:
                            await conn.execute("""
                                UPDATE inventory
                                SET quantity_available = quantity_available + $1, updated_at = NOW()
                                WHERE warehouse_id = $2 AND product_id = $3
                            """, quantity, uuid.UUID(destination_warehouse_id), uuid.UUID(product_id))
                        else:
                            await conn.execute("""
                                INSERT INTO inventory (
                                    warehouse_id, product_id, sku,
                                    quantity_available, quantity_reserved,
                                    created_at, updated_at
                                ) VALUES ($1, $2, $3, $4, 0, NOW(), NOW())
                            """,
                                uuid.UUID(destination_warehouse_id),
                                uuid.UUID(product_id),
                                sku,
                                quantity
                            )
                        
                        # Log transactions
                        await conn.execute("""
                            INSERT INTO inventory_transactions (
                                id, warehouse_id, product_id, sku,
                                transaction_type, quantity_change,
                                quantity_before, quantity_after,
                                reason, batch_id, created_at
                            ) VALUES ($1, $2, $3, $4, 'transfer_out', $5, $6, $7, $8, $9, NOW())
                        """,
                            uuid.uuid4(),
                            uuid.UUID(source_warehouse_id),
                            uuid.UUID(product_id),
                            sku,
                            -quantity,
                            source["quantity_available"],
                            source["quantity_available"] - quantity,
                            reason,
                            batch_id
                        )
                        
                        await conn.execute("""
                            INSERT INTO inventory_transactions (
                                id, warehouse_id, product_id, sku,
                                transaction_type, quantity_change,
                                quantity_before, quantity_after,
                                reason, batch_id, created_at
                            ) VALUES ($1, $2, $3, $4, 'transfer_in', $5, $6, $7, $8, $9, NOW())
                        """,
                            uuid.uuid4(),
                            uuid.UUID(destination_warehouse_id),
                            uuid.UUID(product_id),
                            sku,
                            quantity,
                            dest["quantity_available"] if dest else 0,
                            (dest["quantity_available"] if dest else 0) + quantity,
                            reason,
                            batch_id
                        )
                        
                        # Prepare events
                        events.append(InventoryEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=InventoryEventType.WAREHOUSE_TRANSFER,
                            timestamp=datetime.utcnow(),
                            warehouse_id=source_warehouse_id,
                            product_id=product_id,
                            sku=sku,
                            quantity_change=-quantity,
                            quantity_available=source["quantity_available"] - quantity,
                            quantity_reserved=source["quantity_reserved"],
                            metadata={
                                "batch_id": batch_id,
                                "destination_warehouse_id": destination_warehouse_id,
                                "direction": "out"
                            }
                        ))
                        
                        events.append(InventoryEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=InventoryEventType.WAREHOUSE_TRANSFER,
                            timestamp=datetime.utcnow(),
                            warehouse_id=destination_warehouse_id,
                            product_id=product_id,
                            sku=sku,
                            quantity_change=quantity,
                            quantity_available=(dest["quantity_available"] if dest else 0) + quantity,
                            quantity_reserved=dest["quantity_reserved"] if dest else 0,
                            metadata={
                                "batch_id": batch_id,
                                "source_warehouse_id": source_warehouse_id,
                                "direction": "in"
                            }
                        ))
                        
                        successful += 1
                        
                    except Exception as e:
                        failed += 1
                        errors.append({
                            "product_id": product_id,
                            "sku": sku,
                            "quantity": quantity,
                            "error": str(e)
                        })
                        logger.error(f"Failed to transfer {sku}: {e}")
                        raise  # Rollback entire transaction
        
        # Publish events
        if self.event_producer and events:
            try:
                await self.event_producer.publish_batch(events)
            except Exception as e:
                logger.error(f"Failed to publish events: {e}")
        
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = BatchResult(
            batch_id=batch_id,
            operation_type=BatchOperationType.WAREHOUSE_TRANSFER,
            total_items=len(items),
            successful_items=successful,
            failed_items=failed,
            errors=errors,
            duration_ms=duration,
            created_at=start_time
        )
        
        logger.info(
            f"Warehouse transfer {batch_id}: {successful}/{len(items)} successful, "
            f"{duration:.2f}ms"
        )
        
        return result
    
    async def bulk_stock_adjustment(
        self,
        items: List[BatchItem],
        adjustment_type: str,
        reason: str
    ) -> BatchResult:
        """
        Bulk stock adjustment (damage, expiry, count correction, etc.)
        
        Args:
            items: List of items to adjust
            adjustment_type: Type of adjustment (damage, expiry, count, etc.)
            reason: Detailed reason for adjustment
        
        Returns:
            BatchResult with operation summary
        """
        batch_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        successful = 0
        failed = 0
        errors = []
        events = []
        
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for item in items:
                    try:
                        # Get current inventory with lock
                        current = await conn.fetchrow("""
                            SELECT quantity_available, quantity_reserved
                            FROM inventory
                            WHERE warehouse_id = $1 AND product_id = $2
                            FOR UPDATE
                        """, uuid.UUID(item.warehouse_id), uuid.UUID(item.product_id))
                        
                        if not current:
                            raise ValueError(f"No inventory record for {item.sku}")
                        
                        # Calculate adjustment
                        if item.operation == "subtract":
                            new_available = max(0, current["quantity_available"] - item.quantity)
                            quantity_change = -(current["quantity_available"] - new_available)
                        elif item.operation == "add":
                            new_available = current["quantity_available"] + item.quantity
                            quantity_change = item.quantity
                        else:  # set
                            new_available = item.quantity
                            quantity_change = item.quantity - current["quantity_available"]
                        
                        # Update inventory
                        await conn.execute("""
                            UPDATE inventory
                            SET quantity_available = $1, updated_at = NOW()
                            WHERE warehouse_id = $2 AND product_id = $3
                        """, new_available, uuid.UUID(item.warehouse_id), uuid.UUID(item.product_id))
                        
                        # Log adjustment
                        await conn.execute("""
                            INSERT INTO inventory_adjustments (
                                id, warehouse_id, product_id, sku,
                                adjustment_type, quantity_before, quantity_after,
                                quantity_change, reason, batch_id, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                        """,
                            uuid.uuid4(),
                            uuid.UUID(item.warehouse_id),
                            uuid.UUID(item.product_id),
                            item.sku,
                            adjustment_type,
                            current["quantity_available"],
                            new_available,
                            quantity_change,
                            reason,
                            batch_id
                        )
                        
                        # Prepare event
                        events.append(InventoryEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=InventoryEventType.INVENTORY_ADJUSTMENT,
                            timestamp=datetime.utcnow(),
                            warehouse_id=item.warehouse_id,
                            product_id=item.product_id,
                            sku=item.sku,
                            quantity_change=quantity_change,
                            quantity_available=new_available,
                            quantity_reserved=current["quantity_reserved"],
                            metadata={
                                "batch_id": batch_id,
                                "adjustment_type": adjustment_type,
                                "reason": reason
                            }
                        ))
                        
                        successful += 1
                        
                    except Exception as e:
                        failed += 1
                        errors.append({
                            "warehouse_id": item.warehouse_id,
                            "product_id": item.product_id,
                            "sku": item.sku,
                            "error": str(e)
                        })
                        logger.error(f"Failed to adjust {item.sku}: {e}")
        
        # Publish events
        if self.event_producer and events:
            try:
                await self.event_producer.publish_batch(events)
            except Exception as e:
                logger.error(f"Failed to publish events: {e}")
        
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = BatchResult(
            batch_id=batch_id,
            operation_type=BatchOperationType.STOCK_ADJUSTMENT,
            total_items=len(items),
            successful_items=successful,
            failed_items=failed,
            errors=errors,
            duration_ms=duration,
            created_at=start_time
        )
        
        logger.info(
            f"Batch adjustment {batch_id}: {successful}/{len(items)} successful, "
            f"{failed} failed, {duration:.2f}ms"
        )
        
        return result
    
    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a batch operation"""
        async with self.db_pool.acquire() as conn:
            transactions = await conn.fetch("""
                SELECT COUNT(*) as count, 
                       MIN(created_at) as started_at,
                       MAX(created_at) as completed_at
                FROM inventory_transactions
                WHERE batch_id = $1
            """, batch_id)
            
            if not transactions or transactions[0]["count"] == 0:
                return None
            
            return {
                "batch_id": batch_id,
                "transaction_count": transactions[0]["count"],
                "started_at": transactions[0]["started_at"],
                "completed_at": transactions[0]["completed_at"]
            }
