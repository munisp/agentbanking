"""
Inventory Management Service
Multi-warehouse inventory tracking with real-time updates
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy import Column, String, DateTime, Numeric, Integer, Boolean, Text, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import uuid
import os
import logging
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ecommerce")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============================================================================
# ENUMS
# ============================================================================

class InventoryStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_TRANSIT = "in_transit"
    DAMAGED = "damaged"
    EXPIRED = "expired"
    QUARANTINE = "quarantine"
    RETURNED = "returned"

class StockMovementType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGE = "damage"
    EXPIRY = "expiry"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class InventoryCreate(BaseModel):
    warehouse_id: str
    product_id: str
    quantity_available: int = 0
    reorder_point: int = 10
    reorder_quantity: int = 50
    min_stock_level: int = 5
    max_stock_level: Optional[int] = None

class InventoryUpdate(BaseModel):
    quantity_available: Optional[int] = None
    quantity_reserved: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_quantity: Optional[int] = None
    min_stock_level: Optional[int] = None
    max_stock_level: Optional[int] = None

class StockMovementCreate(BaseModel):
    warehouse_id: str
    product_id: str
    movement_type: StockMovementType
    quantity: int
    unit_cost: Optional[Decimal] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    from_warehouse_id: Optional[str] = None
    to_warehouse_id: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    performed_by: Optional[str] = None

class StockTransferCreate(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    items: List[Dict[str, Any]]  # [{"product_id": "...", "quantity": 10}]
    reason: Optional[str] = None
    notes: Optional[str] = None
    requested_by: Optional[str] = None

class InventoryAdjustment(BaseModel):
    warehouse_id: str
    product_id: str
    adjustment_quantity: int  # Positive or negative
    reason: str
    notes: Optional[str] = None
    performed_by: Optional[str] = None

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Inventory Management Service",
    description="Multi-warehouse inventory tracking and management",
    version="1.0.0"
)

# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# INVENTORY MANAGEMENT CLASS
# ============================================================================

class InventoryManager:
    """Inventory management operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_inventory(
        self,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get inventory levels"""
        
        query = """
            SELECT 
                i.id,
                i.warehouse_id,
                w.name AS warehouse_name,
                w.code AS warehouse_code,
                i.product_id,
                i.quantity_available,
                i.quantity_reserved,
                i.quantity_in_transit,
                i.quantity_damaged,
                i.quantity_total,
                i.reorder_point,
                i.reorder_quantity,
                i.max_stock_level,
                i.min_stock_level,
                i.status,
                i.last_count_date,
                i.last_movement_date,
                i.created_at,
                i.updated_at,
                CASE 
                    WHEN i.quantity_available <= i.reorder_point THEN TRUE
                    ELSE FALSE
                END AS is_low_stock,
                CASE
                    WHEN i.max_stock_level IS NOT NULL AND i.quantity_available >= i.max_stock_level THEN TRUE
                    ELSE FALSE
                END AS is_overstock
            FROM inventory i
            JOIN warehouses w ON i.warehouse_id = w.id
            WHERE 1=1
        """
        
        params = {}
        
        if warehouse_id:
            query += " AND i.warehouse_id = :warehouse_id"
            params["warehouse_id"] = uuid.UUID(warehouse_id)
        
        if product_id:
            query += " AND i.product_id = :product_id"
            params["product_id"] = uuid.UUID(product_id)
        
        query += " ORDER BY w.name, i.product_id"
        
        result = self.db.execute(query, params)
        
        inventory = []
        for row in result:
            inventory.append({
                "id": str(row.id),
                "warehouse_id": str(row.warehouse_id),
                "warehouse_name": row.warehouse_name,
                "warehouse_code": row.warehouse_code,
                "product_id": str(row.product_id),
                "quantity_available": row.quantity_available,
                "quantity_reserved": row.quantity_reserved,
                "quantity_in_transit": row.quantity_in_transit,
                "quantity_damaged": row.quantity_damaged,
                "quantity_total": row.quantity_total,
                "reorder_point": row.reorder_point,
                "reorder_quantity": row.reorder_quantity,
                "max_stock_level": row.max_stock_level,
                "min_stock_level": row.min_stock_level,
                "status": row.status,
                "is_low_stock": row.is_low_stock,
                "is_overstock": row.is_overstock,
                "last_count_date": row.last_count_date.isoformat() if row.last_count_date else None,
                "last_movement_date": row.last_movement_date.isoformat() if row.last_movement_date else None,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat()
            })
        
        return inventory
    
    async def create_inventory(self, data: InventoryCreate) -> Dict[str, Any]:
        """Create inventory record"""
        
        # Check if inventory already exists
        existing = self.db.execute(
            """
            SELECT id FROM inventory 
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
            """,
            {
                "warehouse_id": uuid.UUID(data.warehouse_id),
                "product_id": uuid.UUID(data.product_id)
            }
        ).first()
        
        if existing:
            raise ValueError("Inventory already exists for this warehouse and product")
        
        # Insert inventory
        inventory_id = uuid.uuid4()
        
        self.db.execute(
            """
            INSERT INTO inventory (
                id, warehouse_id, product_id, quantity_available,
                reorder_point, reorder_quantity, min_stock_level, max_stock_level
            ) VALUES (
                :id, :warehouse_id, :product_id, :quantity_available,
                :reorder_point, :reorder_quantity, :min_stock_level, :max_stock_level
            )
            """,
            {
                "id": inventory_id,
                "warehouse_id": uuid.UUID(data.warehouse_id),
                "product_id": uuid.UUID(data.product_id),
                "quantity_available": data.quantity_available,
                "reorder_point": data.reorder_point,
                "reorder_quantity": data.reorder_quantity,
                "min_stock_level": data.min_stock_level,
                "max_stock_level": data.max_stock_level
            }
        )
        
        self.db.commit()
        
        logger.info(f"Inventory created: {inventory_id}")
        
        return await self.get_inventory(data.warehouse_id, data.product_id)
    
    async def update_inventory(
        self,
        warehouse_id: str,
        product_id: str,
        data: InventoryUpdate
    ) -> Dict[str, Any]:
        """Update inventory settings"""
        
        updates = []
        params = {
            "warehouse_id": uuid.UUID(warehouse_id),
            "product_id": uuid.UUID(product_id)
        }
        
        if data.quantity_available is not None:
            updates.append("quantity_available = :quantity_available")
            params["quantity_available"] = data.quantity_available
        
        if data.quantity_reserved is not None:
            updates.append("quantity_reserved = :quantity_reserved")
            params["quantity_reserved"] = data.quantity_reserved
        
        if data.reorder_point is not None:
            updates.append("reorder_point = :reorder_point")
            params["reorder_point"] = data.reorder_point
        
        if data.reorder_quantity is not None:
            updates.append("reorder_quantity = :reorder_quantity")
            params["reorder_quantity"] = data.reorder_quantity
        
        if data.min_stock_level is not None:
            updates.append("min_stock_level = :min_stock_level")
            params["min_stock_level"] = data.min_stock_level
        
        if data.max_stock_level is not None:
            updates.append("max_stock_level = :max_stock_level")
            params["max_stock_level"] = data.max_stock_level
        
        if not updates:
            raise ValueError("No fields to update")
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE inventory
            SET {", ".join(updates)}
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
        """
        
        self.db.execute(query, params)
        self.db.commit()
        
        logger.info(f"Inventory updated: warehouse={warehouse_id}, product={product_id}")
        
        inventory = await self.get_inventory(warehouse_id, product_id)
        return inventory[0] if inventory else None
    
    async def record_stock_movement(
        self,
        data: StockMovementCreate
    ) -> Dict[str, Any]:
        """Record stock movement"""
        
        movement_id = uuid.uuid4()
        total_cost = data.unit_cost * data.quantity if data.unit_cost else None
        
        self.db.execute(
            """
            INSERT INTO stock_movements (
                id, warehouse_id, product_id, movement_type, quantity,
                unit_cost, total_cost, reference_type, reference_id,
                from_warehouse_id, to_warehouse_id, reason, notes, performed_by
            ) VALUES (
                :id, :warehouse_id, :product_id, :movement_type, :quantity,
                :unit_cost, :total_cost, :reference_type, :reference_id,
                :from_warehouse_id, :to_warehouse_id, :reason, :notes, :performed_by
            )
            """,
            {
                "id": movement_id,
                "warehouse_id": uuid.UUID(data.warehouse_id),
                "product_id": uuid.UUID(data.product_id),
                "movement_type": data.movement_type.value,
                "quantity": data.quantity,
                "unit_cost": data.unit_cost,
                "total_cost": total_cost,
                "reference_type": data.reference_type,
                "reference_id": uuid.UUID(data.reference_id) if data.reference_id else None,
                "from_warehouse_id": uuid.UUID(data.from_warehouse_id) if data.from_warehouse_id else None,
                "to_warehouse_id": uuid.UUID(data.to_warehouse_id) if data.to_warehouse_id else None,
                "reason": data.reason,
                "notes": data.notes,
                "performed_by": uuid.UUID(data.performed_by) if data.performed_by else None
            }
        )
        
        self.db.commit()
        
        logger.info(f"Stock movement recorded: {movement_id}, type={data.movement_type}, qty={data.quantity}")
        
        return {
            "movement_id": str(movement_id),
            "warehouse_id": data.warehouse_id,
            "product_id": data.product_id,
            "movement_type": data.movement_type.value,
            "quantity": data.quantity,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def adjust_inventory(
        self,
        data: InventoryAdjustment
    ) -> Dict[str, Any]:
        """Adjust inventory (cycle count, damage, etc.)"""
        
        # Record stock movement
        movement_type = StockMovementType.ADJUSTMENT
        if data.adjustment_quantity < 0 and "damage" in data.reason.lower():
            movement_type = StockMovementType.DAMAGE
        
        movement = await self.record_stock_movement(
            StockMovementCreate(
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                movement_type=movement_type,
                quantity=data.adjustment_quantity,
                reason=data.reason,
                notes=data.notes,
                performed_by=data.performed_by
            )
        )
        
        return movement
    
    async def reserve_inventory(
        self,
        warehouse_id: str,
        product_id: str,
        quantity: int
    ) -> bool:
        """Reserve inventory for an order"""
        
        # Check available quantity
        result = self.db.execute(
            """
            SELECT quantity_available FROM inventory
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
            FOR UPDATE
            """,
            {
                "warehouse_id": uuid.UUID(warehouse_id),
                "product_id": uuid.UUID(product_id)
            }
        ).first()
        
        if not result or result.quantity_available < quantity:
            return False
        
        # Reserve quantity
        self.db.execute(
            """
            UPDATE inventory
            SET quantity_available = quantity_available - :quantity,
                quantity_reserved = quantity_reserved + :quantity,
                updated_at = NOW()
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
            """,
            {
                "warehouse_id": uuid.UUID(warehouse_id),
                "product_id": uuid.UUID(product_id),
                "quantity": quantity
            }
        )
        
        self.db.commit()
        
        logger.info(f"Inventory reserved: warehouse={warehouse_id}, product={product_id}, qty={quantity}")
        
        return True
    
    async def release_reservation(
        self,
        warehouse_id: str,
        product_id: str,
        quantity: int
    ) -> bool:
        """Release reserved inventory"""
        
        self.db.execute(
            """
            UPDATE inventory
            SET quantity_available = quantity_available + :quantity,
                quantity_reserved = quantity_reserved - :quantity,
                updated_at = NOW()
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
            """,
            {
                "warehouse_id": uuid.UUID(warehouse_id),
                "product_id": uuid.UUID(product_id),
                "quantity": quantity
            }
        )
        
        self.db.commit()
        
        logger.info(f"Reservation released: warehouse={warehouse_id}, product={product_id}, qty={quantity}")
        
        return True
    
    async def fulfill_reservation(
        self,
        warehouse_id: str,
        product_id: str,
        quantity: int,
        order_id: str
    ) -> bool:
        """Fulfill reserved inventory (convert to outbound)"""
        
        # Decrease reserved quantity
        self.db.execute(
            """
            UPDATE inventory
            SET quantity_reserved = quantity_reserved - :quantity,
                last_movement_date = NOW(),
                updated_at = NOW()
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
            """,
            {
                "warehouse_id": uuid.UUID(warehouse_id),
                "product_id": uuid.UUID(product_id),
                "quantity": quantity
            }
        )
        
        # Record outbound movement
        await self.record_stock_movement(
            StockMovementCreate(
                warehouse_id=warehouse_id,
                product_id=product_id,
                movement_type=StockMovementType.OUTBOUND,
                quantity=quantity,
                reference_type="sales_order",
                reference_id=order_id
            )
        )
        
        logger.info(f"Reservation fulfilled: warehouse={warehouse_id}, product={product_id}, qty={quantity}")
        
        return True
    
    async def get_low_stock_items(self) -> List[Dict[str, Any]]:
        """Get items that need reordering"""
        
        result = self.db.execute("""
            SELECT * FROM check_low_stock()
        """)
        
        items = []
        for row in result:
            items.append({
                "warehouse_id": str(row.warehouse_id),
                "warehouse_name": row.warehouse_name,
                "product_id": str(row.product_id),
                "quantity_available": row.quantity_available,
                "reorder_point": row.reorder_point,
                "reorder_quantity": row.reorder_quantity,
                "shortage": row.reorder_point - row.quantity_available
            })
        
        return items
    
    async def get_inventory_summary(self) -> Dict[str, Any]:
        """Get overall inventory summary"""
        
        result = self.db.execute("""
            SELECT * FROM inventory_summary
        """)
        
        summary = []
        for row in result:
            summary.append({
                "warehouse_id": str(row.warehouse_id),
                "warehouse_name": row.warehouse_name,
                "warehouse_code": row.warehouse_code,
                "total_products": row.total_products,
                "total_quantity": row.total_quantity,
                "total_available": row.total_available,
                "total_reserved": row.total_reserved,
                "total_in_transit": row.total_in_transit,
                "total_damaged": row.total_damaged,
                "low_stock_count": row.low_stock_count
            })
        
        return {
            "warehouses": summary,
            "total_warehouses": len(summary),
            "grand_total_quantity": sum(w["total_quantity"] for w in summary),
            "grand_total_available": sum(w["total_available"] for w in summary)
        }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/inventory", response_model=List[Dict[str, Any]])
async def get_inventory(
    warehouse_id: Optional[str] = None,
    product_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get inventory levels"""
    manager = InventoryManager(db)
    return await manager.get_inventory(warehouse_id, product_id)

@app.post("/inventory", response_model=Dict[str, Any])
async def create_inventory(
    data: InventoryCreate,
    db: Session = Depends(get_db)
):
    """Create inventory record"""
    manager = InventoryManager(db)
    return await manager.create_inventory(data)

@app.put("/inventory/{warehouse_id}/{product_id}", response_model=Dict[str, Any])
async def update_inventory(
    warehouse_id: str,
    product_id: str,
    data: InventoryUpdate,
    db: Session = Depends(get_db)
):
    """Update inventory settings"""
    manager = InventoryManager(db)
    return await manager.update_inventory(warehouse_id, product_id, data)

@app.post("/inventory/movements", response_model=Dict[str, Any])
async def record_stock_movement(
    data: StockMovementCreate,
    db: Session = Depends(get_db)
):
    """Record stock movement"""
    manager = InventoryManager(db)
    return await manager.record_stock_movement(data)

@app.post("/inventory/adjust", response_model=Dict[str, Any])
async def adjust_inventory(
    data: InventoryAdjustment,
    db: Session = Depends(get_db)
):
    """Adjust inventory"""
    manager = InventoryManager(db)
    return await manager.adjust_inventory(data)

@app.post("/inventory/reserve", response_model=Dict[str, Any])
async def reserve_inventory(
    warehouse_id: str,
    product_id: str,
    quantity: int,
    db: Session = Depends(get_db)
):
    """Reserve inventory"""
    manager = InventoryManager(db)
    success = await manager.reserve_inventory(warehouse_id, product_id, quantity)
    return {"success": success}

@app.post("/inventory/release", response_model=Dict[str, Any])
async def release_reservation(
    warehouse_id: str,
    product_id: str,
    quantity: int,
    db: Session = Depends(get_db)
):
    """Release reservation"""
    manager = InventoryManager(db)
    success = await manager.release_reservation(warehouse_id, product_id, quantity)
    return {"success": success}

@app.post("/inventory/fulfill", response_model=Dict[str, Any])
async def fulfill_reservation(
    warehouse_id: str,
    product_id: str,
    quantity: int,
    order_id: str,
    db: Session = Depends(get_db)
):
    """Fulfill reservation"""
    manager = InventoryManager(db)
    success = await manager.fulfill_reservation(warehouse_id, product_id, quantity, order_id)
    return {"success": success}

@app.get("/inventory/low-stock", response_model=List[Dict[str, Any]])
async def get_low_stock_items(db: Session = Depends(get_db)):
    """Get low stock items"""
    manager = InventoryManager(db)
    return await manager.get_low_stock_items()

@app.get("/inventory/summary", response_model=Dict[str, Any])
async def get_inventory_summary(db: Session = Depends(get_db)):
    """Get inventory summary"""
    manager = InventoryManager(db)
    return await manager.get_inventory_summary()

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "inventory-service",
        "version": "1.0.0"
    }

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

