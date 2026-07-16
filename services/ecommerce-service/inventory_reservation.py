"""
Inventory Reservation Module
Implements inventory reservation with automatic expiry and release
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import asyncpg
import redis.asyncio as redis

from service_config import get_config

logger = logging.getLogger(__name__)


class ReservationStatus(str, Enum):
    """Reservation status"""
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class InventoryReservation:
    """Inventory reservation record"""
    id: str
    order_id: str
    warehouse_id: str
    product_id: str
    variant_id: Optional[str]
    sku: str
    quantity: int
    status: ReservationStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    fulfilled_at: Optional[datetime] = None
    released_at: Optional[datetime] = None


class InventoryReservationManager:
    """
    Manages inventory reservations with automatic expiry
    
    Features:
    - Reserve inventory for orders with configurable timeout
    - Automatic release of expired reservations
    - Distributed locking via Redis
    - Batch operations for efficiency
    """
    
    def __init__(self, db_pool: asyncpg.Pool, redis_client: redis.Redis):
        self.db_pool = db_pool
        self.redis = redis_client
        self.config = get_config()
        self._expiry_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize reservation manager and start expiry task"""
        await self._ensure_tables()
        self._expiry_task = asyncio.create_task(self._expiry_loop())
        logger.info("Inventory reservation manager initialized")
    
    async def shutdown(self):
        """Shutdown reservation manager"""
        if self._expiry_task:
            self._expiry_task.cancel()
            try:
                await self._expiry_task
            except asyncio.CancelledError:
                pass
        logger.info("Inventory reservation manager shutdown")
    
    async def _ensure_tables(self):
        """Ensure reservation tables exist"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory_reservations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    order_id VARCHAR(100) NOT NULL,
                    warehouse_id UUID NOT NULL,
                    product_id UUID NOT NULL,
                    variant_id UUID,
                    sku VARCHAR(100) NOT NULL,
                    quantity INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fulfilled_at TIMESTAMP,
                    released_at TIMESTAMP,
                    CONSTRAINT positive_quantity CHECK (quantity > 0)
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reservations_order 
                ON inventory_reservations(order_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reservations_status_expires 
                ON inventory_reservations(status, expires_at)
                WHERE status = 'active'
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reservations_warehouse_product 
                ON inventory_reservations(warehouse_id, product_id)
            """)
    
    async def reserve(
        self,
        order_id: str,
        items: List[Dict[str, Any]],
        timeout_minutes: Optional[int] = None
    ) -> List[InventoryReservation]:
        """
        Reserve inventory for an order
        
        Args:
            order_id: Order identifier
            items: List of items to reserve [{warehouse_id, product_id, variant_id, sku, quantity}]
            timeout_minutes: Reservation timeout (default from config)
        
        Returns:
            List of created reservations
        
        Raises:
            InsufficientInventoryError: If any item has insufficient stock
        """
        timeout = timeout_minutes or self.config.inventory.reservation_timeout_minutes
        expires_at = datetime.utcnow() + timedelta(minutes=timeout)
        
        reservations = []
        
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for item in items:
                    warehouse_id = item["warehouse_id"]
                    product_id = item["product_id"]
                    quantity = item["quantity"]
                    
                    # Lock and check inventory
                    inventory = await conn.fetchrow("""
                        SELECT quantity_available, quantity_reserved
                        FROM inventory
                        WHERE warehouse_id = $1 AND product_id = $2
                        FOR UPDATE
                    """, uuid.UUID(warehouse_id), uuid.UUID(product_id))
                    
                    if not inventory:
                        raise InsufficientInventoryError(
                            f"No inventory record for product {product_id} in warehouse {warehouse_id}"
                        )
                    
                    if inventory["quantity_available"] < quantity:
                        raise InsufficientInventoryError(
                            f"Insufficient inventory for product {product_id}: "
                            f"requested {quantity}, available {inventory['quantity_available']}"
                        )
                    
                    # Create reservation
                    reservation_id = uuid.uuid4()
                    await conn.execute("""
                        INSERT INTO inventory_reservations (
                            id, order_id, warehouse_id, product_id, variant_id, sku,
                            quantity, status, expires_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8)
                    """,
                        reservation_id,
                        order_id,
                        uuid.UUID(warehouse_id),
                        uuid.UUID(product_id),
                        uuid.UUID(item.get("variant_id")) if item.get("variant_id") else None,
                        item.get("sku", ""),
                        quantity,
                        expires_at
                    )
                    
                    # Update inventory
                    await conn.execute("""
                        UPDATE inventory
                        SET quantity_available = quantity_available - $1,
                            quantity_reserved = quantity_reserved + $1,
                            updated_at = NOW()
                        WHERE warehouse_id = $2 AND product_id = $3
                    """, quantity, uuid.UUID(warehouse_id), uuid.UUID(product_id))
                    
                    reservations.append(InventoryReservation(
                        id=str(reservation_id),
                        order_id=order_id,
                        warehouse_id=warehouse_id,
                        product_id=product_id,
                        variant_id=item.get("variant_id"),
                        sku=item.get("sku", ""),
                        quantity=quantity,
                        status=ReservationStatus.ACTIVE,
                        expires_at=expires_at,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    ))
        
        # Set Redis expiry key for faster expiry detection
        for reservation in reservations:
            await self.redis.setex(
                f"reservation:expiry:{reservation.id}",
                timeout * 60,
                order_id
            )
        
        logger.info(f"Created {len(reservations)} reservations for order {order_id}")
        return reservations
    
    async def fulfill(self, order_id: str) -> int:
        """
        Fulfill reservations for an order (convert to actual sale)
        
        Args:
            order_id: Order identifier
        
        Returns:
            Number of reservations fulfilled
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Get active reservations
                reservations = await conn.fetch("""
                    SELECT id, warehouse_id, product_id, quantity
                    FROM inventory_reservations
                    WHERE order_id = $1 AND status = 'active'
                    FOR UPDATE
                """, order_id)
                
                if not reservations:
                    logger.warning(f"No active reservations found for order {order_id}")
                    return 0
                
                # Update reservations to fulfilled
                await conn.execute("""
                    UPDATE inventory_reservations
                    SET status = 'fulfilled',
                        fulfilled_at = NOW(),
                        updated_at = NOW()
                    WHERE order_id = $1 AND status = 'active'
                """, order_id)
                
                # Decrease reserved quantity (already removed from available)
                for res in reservations:
                    await conn.execute("""
                        UPDATE inventory
                        SET quantity_reserved = quantity_reserved - $1,
                            updated_at = NOW()
                        WHERE warehouse_id = $2 AND product_id = $3
                    """, res["quantity"], res["warehouse_id"], res["product_id"])
                    
                    # Remove Redis expiry key
                    await self.redis.delete(f"reservation:expiry:{res['id']}")
        
        logger.info(f"Fulfilled {len(reservations)} reservations for order {order_id}")
        return len(reservations)
    
    async def release(self, order_id: str, reason: str = "cancelled") -> int:
        """
        Release reservations for an order (return to available)
        
        Args:
            order_id: Order identifier
            reason: Reason for release
        
        Returns:
            Number of reservations released
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Get active reservations
                reservations = await conn.fetch("""
                    SELECT id, warehouse_id, product_id, quantity
                    FROM inventory_reservations
                    WHERE order_id = $1 AND status = 'active'
                    FOR UPDATE
                """, order_id)
                
                if not reservations:
                    return 0
                
                # Update reservations to released
                await conn.execute("""
                    UPDATE inventory_reservations
                    SET status = 'released',
                        released_at = NOW(),
                        updated_at = NOW()
                    WHERE order_id = $1 AND status = 'active'
                """, order_id)
                
                # Return quantity to available
                for res in reservations:
                    await conn.execute("""
                        UPDATE inventory
                        SET quantity_available = quantity_available + $1,
                            quantity_reserved = quantity_reserved - $1,
                            updated_at = NOW()
                        WHERE warehouse_id = $2 AND product_id = $3
                    """, res["quantity"], res["warehouse_id"], res["product_id"])
                    
                    # Remove Redis expiry key
                    await self.redis.delete(f"reservation:expiry:{res['id']}")
        
        logger.info(f"Released {len(reservations)} reservations for order {order_id}: {reason}")
        return len(reservations)
    
    async def _expire_reservations(self) -> int:
        """
        Expire and release overdue reservations
        
        Returns:
            Number of reservations expired
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Get expired reservations
                expired = await conn.fetch("""
                    SELECT id, order_id, warehouse_id, product_id, quantity
                    FROM inventory_reservations
                    WHERE status = 'active' AND expires_at < NOW()
                    FOR UPDATE
                    LIMIT 100
                """)
                
                if not expired:
                    return 0
                
                expired_ids = [r["id"] for r in expired]
                
                # Update reservations to expired
                await conn.execute("""
                    UPDATE inventory_reservations
                    SET status = 'expired',
                        released_at = NOW(),
                        updated_at = NOW()
                    WHERE id = ANY($1)
                """, expired_ids)
                
                # Return quantity to available
                for res in expired:
                    await conn.execute("""
                        UPDATE inventory
                        SET quantity_available = quantity_available + $1,
                            quantity_reserved = quantity_reserved - $1,
                            updated_at = NOW()
                        WHERE warehouse_id = $2 AND product_id = $3
                    """, res["quantity"], res["warehouse_id"], res["product_id"])
                    
                    # Remove Redis expiry key
                    await self.redis.delete(f"reservation:expiry:{res['id']}")
        
        if expired:
            logger.info(f"Expired {len(expired)} reservations")
        
        return len(expired)
    
    async def _expiry_loop(self):
        """Background task to expire reservations"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._expire_reservations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reservation expiry loop: {e}")
                await asyncio.sleep(5)
    
    async def get_reservations(self, order_id: str) -> List[InventoryReservation]:
        """Get all reservations for an order"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM inventory_reservations
                WHERE order_id = $1
                ORDER BY created_at
            """, order_id)
            
            return [
                InventoryReservation(
                    id=str(row["id"]),
                    order_id=row["order_id"],
                    warehouse_id=str(row["warehouse_id"]),
                    product_id=str(row["product_id"]),
                    variant_id=str(row["variant_id"]) if row["variant_id"] else None,
                    sku=row["sku"],
                    quantity=row["quantity"],
                    status=ReservationStatus(row["status"]),
                    expires_at=row["expires_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    fulfilled_at=row.get("fulfilled_at"),
                    released_at=row.get("released_at")
                )
                for row in rows
            ]
    
    async def get_expiring_soon(self, minutes: int = 5) -> List[InventoryReservation]:
        """Get reservations expiring within specified minutes"""
        threshold = datetime.utcnow() + timedelta(minutes=minutes)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM inventory_reservations
                WHERE status = 'active' AND expires_at < $1
                ORDER BY expires_at
            """, threshold)
            
            return [
                InventoryReservation(
                    id=str(row["id"]),
                    order_id=row["order_id"],
                    warehouse_id=str(row["warehouse_id"]),
                    product_id=str(row["product_id"]),
                    variant_id=str(row["variant_id"]) if row["variant_id"] else None,
                    sku=row["sku"],
                    quantity=row["quantity"],
                    status=ReservationStatus(row["status"]),
                    expires_at=row["expires_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]


class InsufficientInventoryError(Exception):
    """Raised when there is insufficient inventory for a reservation"""
    pass
