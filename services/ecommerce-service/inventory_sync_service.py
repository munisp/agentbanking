"""
Inventory Sync Service
Real-time inventory synchronization between e-commerce and supply chain systems
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import httpx
import asyncio
import json
import logging

import os
# Configuration
app = FastAPI(title="Inventory Sync Service")
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# Enums
class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class InventoryOperation(str, Enum):
    RESERVE = "reserve"
    RELEASE = "release"
    ADJUST = "adjust"
    SYNC = "sync"

class StockStatus(str, Enum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    BACKORDER = "backorder"

# Models
class InventoryItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    sku: str
    warehouse_id: int
    quantity_available: int
    quantity_reserved: int
    quantity_on_order: int
    reorder_point: int = 10
    reorder_quantity: int = 50
    last_sync_at: Optional[datetime] = None

class InventoryUpdate(BaseModel):
    sku: str
    warehouse_id: int
    operation: InventoryOperation
    quantity: int
    order_id: Optional[int] = None
    notes: Optional[str] = None

class SyncLog(BaseModel):
    id: int
    sync_type: str
    status: SyncStatus
    items_synced: int
    items_failed: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

class StockAlert(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    sku: str
    warehouse_id: int
    alert_type: str
    current_quantity: int
    threshold: int
    created_at: datetime
    resolved_at: Optional[datetime] = None

# Database initialization
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        # Inventory table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                sku VARCHAR(100) NOT NULL,
                warehouse_id INTEGER NOT NULL,
                quantity_available INTEGER DEFAULT 0,
                quantity_reserved INTEGER DEFAULT 0,
                quantity_on_order INTEGER DEFAULT 0,
                reorder_point INTEGER DEFAULT 10,
                reorder_quantity INTEGER DEFAULT 50,
                last_sync_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(sku, warehouse_id)
            )
        ''')
        
        # Inventory transactions table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id SERIAL PRIMARY KEY,
                inventory_id INTEGER REFERENCES inventory(id),
                operation VARCHAR(50) NOT NULL,
                quantity INTEGER NOT NULL,
                order_id INTEGER,
                reference_type VARCHAR(50),
                reference_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Sync logs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS inventory_sync_logs (
                id SERIAL PRIMARY KEY,
                sync_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                items_synced INTEGER DEFAULT 0,
                items_failed INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        ''')
        
        # Stock alerts table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS stock_alerts (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                sku VARCHAR(100) NOT NULL,
                warehouse_id INTEGER NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                current_quantity INTEGER NOT NULL,
                threshold INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                resolved_at TIMESTAMP
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_inventory_sku ON inventory(sku)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory(warehouse_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_transactions_inventory ON inventory_transactions(inventory_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_transactions_order ON inventory_transactions(order_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON stock_alerts(resolved_at)')

# Helper functions
async def get_inventory_by_sku(sku: str, warehouse_id: int) -> Optional[Dict]:
    """Get inventory record by SKU and warehouse"""
    async with db_pool.acquire() as conn:
        inventory = await conn.fetchrow(
            """
            SELECT * FROM inventory
            WHERE sku = $1 AND warehouse_id = $2
            """,
            sku, warehouse_id
        )
        return dict(inventory) if inventory else None

async def create_inventory_transaction(
    inventory_id: int,
    operation: str,
    quantity: int,
    order_id: Optional[int] = None,
    notes: Optional[str] = None
):
    """Log inventory transaction"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO inventory_transactions (
                inventory_id, operation, quantity, order_id, notes
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            inventory_id, operation, quantity, order_id, notes
        )

async def check_stock_alerts(inventory_id: int):
    """Check and create stock alerts if needed"""
    async with db_pool.acquire() as conn:
        inventory = await conn.fetchrow(
            "SELECT * FROM inventory WHERE id = $1",
            inventory_id
        )
        
        if not inventory:
            return
        
        # Check if quantity is below reorder point
        if inventory['quantity_available'] <= inventory['reorder_point']:
            # Check if alert already exists
            existing_alert = await conn.fetchrow(
                """
                SELECT id FROM stock_alerts
                WHERE sku = $1 AND warehouse_id = $2
                AND alert_type = 'low_stock' AND resolved_at IS NULL
                """,
                inventory['sku'], inventory['warehouse_id']
            )
            
            if not existing_alert:
                await conn.execute(
                    """
                    INSERT INTO stock_alerts (
                        product_id, variant_id, sku, warehouse_id,
                        alert_type, current_quantity, threshold
                    )
                    VALUES ($1, $2, $3, $4, 'low_stock', $5, $6)
                    """,
                    inventory['product_id'], inventory['variant_id'],
                    inventory['sku'], inventory['warehouse_id'],
                    inventory['quantity_available'], inventory['reorder_point']
                )
                
                logger.warning(f"Low stock alert created for SKU {inventory['sku']} at warehouse {inventory['warehouse_id']}")

async def sync_with_supply_chain(sku: str, warehouse_id: int) -> Dict:
    """Sync inventory with supply chain system"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"http://localhost:9000/supply-chain/inventory/{sku}",
                params={"warehouse_id": warehouse_id},
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to sync with supply chain: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Supply chain sync error: {e}")
            return {}

async def update_product_stock_status(product_id: int):
    """Update product stock status in catalog"""
    async with db_pool.acquire() as conn:
        # Calculate total available quantity across all warehouses
        total = await conn.fetchval(
            """
            SELECT SUM(quantity_available) FROM inventory
            WHERE product_id = $1
            """,
            product_id
        )
        
        total = total or 0
        
        # Determine stock status
        if total == 0:
            status = StockStatus.OUT_OF_STOCK
        elif total <= 10:
            status = StockStatus.LOW_STOCK
        else:
            status = StockStatus.IN_STOCK
        
        # Update product catalog
        async with httpx.AsyncClient() as client:
            try:
                await client.put(
                    f"http://localhost:8082/products/{product_id}/stock",
                    json={
                        "stock_quantity": total,
                        "status": status.value
                    },
                    timeout=5.0
                )
            except Exception as e:
                logger.error(f"Failed to update product stock status: {e}")

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()
    # Start background sync task
    asyncio.create_task(periodic_sync())

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/inventory/update")
async def update_inventory(update: InventoryUpdate, background_tasks: BackgroundTasks):
    """Update inventory quantity"""
    async with db_pool.acquire() as conn:
        # Get or create inventory record
        inventory = await conn.fetchrow(
            """
            SELECT * FROM inventory
            WHERE sku = $1 AND warehouse_id = $2
            """,
            update.sku, update.warehouse_id
        )
        
        if not inventory:
            raise HTTPException(status_code=404, detail="Inventory record not found")
        
        inventory_id = inventory['id']
        
        # Update based on operation
        if update.operation == InventoryOperation.RESERVE:
            # Reserve quantity for order
            if inventory['quantity_available'] < update.quantity:
                raise HTTPException(status_code=400, detail="Insufficient inventory")
            
            await conn.execute(
                """
                UPDATE inventory
                SET quantity_available = quantity_available - $1,
                    quantity_reserved = quantity_reserved + $1,
                    updated_at = NOW()
                WHERE id = $2
                """,
                update.quantity, inventory_id
            )
            
        elif update.operation == InventoryOperation.RELEASE:
            # Release reserved quantity (e.g., order cancelled)
            await conn.execute(
                """
                UPDATE inventory
                SET quantity_available = quantity_available + $1,
                    quantity_reserved = quantity_reserved - $1,
                    updated_at = NOW()
                WHERE id = $2
                """,
                update.quantity, inventory_id
            )
            
        elif update.operation == InventoryOperation.ADJUST:
            # Manual adjustment
            await conn.execute(
                """
                UPDATE inventory
                SET quantity_available = quantity_available + $1,
                    updated_at = NOW()
                WHERE id = $2
                """,
                update.quantity, inventory_id
            )
        
        # Log transaction
        await create_inventory_transaction(
            inventory_id,
            update.operation.value,
            update.quantity,
            update.order_id,
            update.notes
        )
        
        # Check for stock alerts
        background_tasks.add_task(check_stock_alerts, inventory_id)
        
        # Update product stock status
        background_tasks.add_task(update_product_stock_status, inventory['product_id'])
        
        # Get updated inventory
        updated = await conn.fetchrow(
            "SELECT * FROM inventory WHERE id = $1",
            inventory_id
        )
        
        return InventoryItem(**dict(updated))

@app.get("/inventory/{sku}")
async def get_inventory(sku: str, warehouse_id: Optional[int] = None):
    """Get inventory for SKU"""
    async with db_pool.acquire() as conn:
        if warehouse_id:
            inventory = await conn.fetch(
                """
                SELECT * FROM inventory
                WHERE sku = $1 AND warehouse_id = $2
                """,
                sku, warehouse_id
            )
        else:
            inventory = await conn.fetch(
                """
                SELECT * FROM inventory
                WHERE sku = $1
                """,
                sku
            )
        
        if not inventory:
            raise HTTPException(status_code=404, detail="Inventory not found")
        
        return [InventoryItem(**dict(inv)) for inv in inventory]

@app.get("/inventory/product/{product_id}")
async def get_product_inventory(product_id: int):
    """Get all inventory for a product"""
    async with db_pool.acquire() as conn:
        inventory = await conn.fetch(
            """
            SELECT * FROM inventory
            WHERE product_id = $1
            ORDER BY warehouse_id
            """,
            product_id
        )
        
        return [InventoryItem(**dict(inv)) for inv in inventory]

@app.post("/inventory/sync")
async def trigger_sync(sku: Optional[str] = None, warehouse_id: Optional[int] = None):
    """Trigger manual inventory sync"""
    async with db_pool.acquire() as conn:
        # Create sync log
        sync_id = await conn.fetchval(
            """
            INSERT INTO inventory_sync_logs (sync_type, status)
            VALUES ('manual', 'in_progress')
            RETURNING id
            """,
        )
        
        items_synced = 0
        items_failed = 0
        
        try:
            # Get inventory items to sync
            if sku and warehouse_id:
                items = await conn.fetch(
                    """
                    SELECT * FROM inventory
                    WHERE sku = $1 AND warehouse_id = $2
                    """,
                    sku, warehouse_id
                )
            else:
                items = await conn.fetch(
                    "SELECT * FROM inventory LIMIT 1000"
                )
            
            # Sync each item
            for item in items:
                try:
                    # Get data from supply chain
                    sc_data = await sync_with_supply_chain(item['sku'], item['warehouse_id'])
                    
                    if sc_data:
                        # Update inventory
                        await conn.execute(
                            """
                            UPDATE inventory
                            SET quantity_available = $1,
                                quantity_on_order = $2,
                                last_sync_at = NOW(),
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            sc_data.get('quantity_available', item['quantity_available']),
                            sc_data.get('quantity_on_order', item['quantity_on_order']),
                            item['id']
                        )
                        items_synced += 1
                    else:
                        items_failed += 1
                        
                except Exception as e:
                    logger.error(f"Failed to sync item {item['sku']}: {e}")
                    items_failed += 1
            
            # Update sync log
            await conn.execute(
                """
                UPDATE inventory_sync_logs
                SET status = 'completed',
                    items_synced = $1,
                    items_failed = $2,
                    completed_at = NOW()
                WHERE id = $3
                """,
                items_synced, items_failed, sync_id
            )
            
            return {
                "sync_id": sync_id,
                "status": "completed",
                "items_synced": items_synced,
                "items_failed": items_failed
            }
            
        except Exception as e:
            # Update sync log with error
            await conn.execute(
                """
                UPDATE inventory_sync_logs
                SET status = 'failed',
                    error_message = $1,
                    completed_at = NOW()
                WHERE id = $2
                """,
                str(e), sync_id
            )
            
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@app.get("/inventory/sync/logs")
async def get_sync_logs(limit: int = 50):
    """Get sync logs"""
    async with db_pool.acquire() as conn:
        logs = await conn.fetch(
            """
            SELECT * FROM inventory_sync_logs
            ORDER BY started_at DESC
            LIMIT $1
            """,
            limit
        )
        
        return [SyncLog(**dict(log)) for log in logs]

@app.get("/inventory/alerts")
async def get_stock_alerts(resolved: Optional[bool] = None):
    """Get stock alerts"""
    async with db_pool.acquire() as conn:
        if resolved is None:
            alerts = await conn.fetch(
                """
                SELECT * FROM stock_alerts
                ORDER BY created_at DESC
                LIMIT 100
                """
            )
        elif resolved:
            alerts = await conn.fetch(
                """
                SELECT * FROM stock_alerts
                WHERE resolved_at IS NOT NULL
                ORDER BY resolved_at DESC
                LIMIT 100
                """
            )
        else:
            alerts = await conn.fetch(
                """
                SELECT * FROM stock_alerts
                WHERE resolved_at IS NULL
                ORDER BY created_at DESC
                """
            )
        
        return [StockAlert(**dict(alert)) for alert in alerts]

@app.put("/inventory/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    """Resolve stock alert"""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE stock_alerts
            SET resolved_at = NOW()
            WHERE id = $1 AND resolved_at IS NULL
            """,
            alert_id
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")
        
        return {"message": "Alert resolved"}

@app.get("/inventory/transactions/{inventory_id}")
async def get_inventory_transactions(inventory_id: int, limit: int = 50):
    """Get inventory transaction history"""
    async with db_pool.acquire() as conn:
        transactions = await conn.fetch(
            """
            SELECT * FROM inventory_transactions
            WHERE inventory_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            inventory_id, limit
        )
        
        return [dict(t) for t in transactions]

async def periodic_sync():
    """Background task for periodic inventory sync"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            
            logger.info("Starting periodic inventory sync")
            
            async with db_pool.acquire() as conn:
                # Create sync log
                sync_id = await conn.fetchval(
                    """
                    INSERT INTO inventory_sync_logs (sync_type, status)
                    VALUES ('automatic', 'in_progress')
                    RETURNING id
                    """,
                )
                
                items_synced = 0
                items_failed = 0
                
                # Get items that need sync (not synced in last hour)
                items = await conn.fetch(
                    """
                    SELECT * FROM inventory
                    WHERE last_sync_at IS NULL
                    OR last_sync_at < NOW() - INTERVAL '1 hour'
                    LIMIT 100
                    """
                )
                
                for item in items:
                    try:
                        sc_data = await sync_with_supply_chain(item['sku'], item['warehouse_id'])
                        
                        if sc_data:
                            await conn.execute(
                                """
                                UPDATE inventory
                                SET quantity_available = $1,
                                    quantity_on_order = $2,
                                    last_sync_at = NOW(),
                                    updated_at = NOW()
                                WHERE id = $3
                                """,
                                sc_data.get('quantity_available', item['quantity_available']),
                                sc_data.get('quantity_on_order', item['quantity_on_order']),
                                item['id']
                            )
                            items_synced += 1
                    except Exception as e:
                        logger.error(f"Failed to sync item {item['sku']}: {e}")
                        items_failed += 1
                
                # Update sync log
                await conn.execute(
                    """
                    UPDATE inventory_sync_logs
                    SET status = 'completed',
                        items_synced = $1,
                        items_failed = $2,
                        completed_at = NOW()
                    WHERE id = $3
                    """,
                    items_synced, items_failed, sync_id
                )
                
                logger.info(f"Periodic sync completed: {items_synced} synced, {items_failed} failed")
                
        except Exception as e:
            logger.error(f"Periodic sync error: {e}")

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "inventory_sync",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)

