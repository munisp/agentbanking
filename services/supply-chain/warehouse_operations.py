"""
Warehouse Operations Service
Complete warehouse management: receiving, picking, packing, shipping
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import uuid
import os
import logging
from pydantic import BaseModel

from inventory_service import InventoryManager, get_db, StockMovementCreate, StockMovementType

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
# ============================================================================

class ShipmentStatus(str, Enum):
    PENDING = "pending"
    PICKED = "picked"
    PACKED = "packed"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED = "returned"

class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT_TO_SUPPLIER = "sent_to_supplier"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    CLOSED = "closed"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class GoodsReceiptCreate(BaseModel):
    purchase_order_id: str
    warehouse_id: str
    received_by: Optional[str] = None
    received_by_name: str
    quality_checked: bool = False
    quality_check_passed: Optional[bool] = None
    quality_notes: Optional[str] = None
    notes: Optional[str] = None
    items: List[Dict[str, Any]]  # [{"po_item_id": "...", "quantity_received": 10, "quantity_accepted": 10, "quantity_rejected": 0}]

class PickListCreate(BaseModel):
    order_id: str
    warehouse_id: str
    picker_id: Optional[str] = None
    picker_name: Optional[str] = None
    priority: str = "normal"  # low, normal, high, urgent
    notes: Optional[str] = None

class PackingCreate(BaseModel):
    shipment_id: str
    packer_id: Optional[str] = None
    packer_name: Optional[str] = None
    number_of_packages: int = 1
    total_weight_kg: Optional[Decimal] = None
    total_volume_cbm: Optional[Decimal] = None
    packing_materials: Optional[List[str]] = None
    notes: Optional[str] = None

class ShipmentCreate(BaseModel):
    order_id: str
    warehouse_id: str
    carrier: str
    service_level: str
    shipping_address: Dict[str, Any]
    return_address: Optional[Dict[str, Any]] = None
    total_weight_kg: Optional[Decimal] = None
    total_volume_cbm: Optional[Decimal] = None
    number_of_packages: int = 1
    shipping_cost: Optional[Decimal] = None
    insurance_cost: Optional[Decimal] = None
    signature_required: bool = False
    special_instructions: Optional[str] = None
    notes: Optional[str] = None
    items: List[Dict[str, Any]]  # [{"order_item_id": "...", "product_id": "...", "quantity": 2}]

class ShipmentUpdate(BaseModel):
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    status: Optional[ShipmentStatus] = None
    ship_date: Optional[datetime] = None
    estimated_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    signature_received: Optional[bool] = None
    signed_by: Optional[str] = None
    notes: Optional[str] = None

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Warehouse Operations Service",
    description="Complete warehouse management: receiving, picking, packing, shipping",
    version="1.0.0"
)

# ============================================================================
# WAREHOUSE OPERATIONS CLASS
# ============================================================================

class WarehouseOperations:
    """Warehouse operations management"""
    
    def __init__(self, db: Session):
        self.db = db
        self.inventory_manager = InventoryManager(db)
    
    # ========================================================================
    # RECEIVING OPERATIONS
    # ========================================================================
    
    async def create_goods_receipt(
        self,
        data: GoodsReceiptCreate
    ) -> Dict[str, Any]:
        """Create goods receipt from purchase order"""
        
        # Get purchase order
        po = self.db.execute(
            """
            SELECT id, po_number, supplier_id, warehouse_id, status
            FROM purchase_orders
            WHERE id = :po_id
            """,
            {"po_id": uuid.UUID(data.purchase_order_id)}
        ).first()
        
        if not po:
            raise ValueError("Purchase order not found")
        
        if po.status not in ['approved', 'sent_to_supplier', 'acknowledged', 'partially_received']:
            raise ValueError(f"Cannot receive from PO with status: {po.status}")
        
        # Generate receipt number
        receipt_number = f"GR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create goods receipt
        receipt_id = uuid.uuid4()
        
        self.db.execute(
            """
            INSERT INTO goods_receipts (
                id, receipt_number, purchase_order_id, warehouse_id,
                received_by, received_by_name, quality_checked,
                quality_check_passed, quality_notes, notes
            ) VALUES (
                :id, :receipt_number, :purchase_order_id, :warehouse_id,
                :received_by, :received_by_name, :quality_checked,
                :quality_check_passed, :quality_notes, :notes
            )
            """,
            {
                "id": receipt_id,
                "receipt_number": receipt_number,
                "purchase_order_id": uuid.UUID(data.purchase_order_id),
                "warehouse_id": uuid.UUID(data.warehouse_id),
                "received_by": uuid.UUID(data.received_by) if data.received_by else None,
                "received_by_name": data.received_by_name,
                "quality_checked": data.quality_checked,
                "quality_check_passed": data.quality_check_passed,
                "quality_notes": data.quality_notes,
                "notes": data.notes
            }
        )
        
        # Process receipt items
        total_received = 0
        all_items_complete = True
        
        for item in data.items:
            # Get PO item details
            po_item = self.db.execute(
                """
                SELECT product_id, quantity_ordered, quantity_received
                FROM purchase_order_items
                WHERE id = :po_item_id
                """,
                {"po_item_id": uuid.UUID(item["po_item_id"])}
            ).first()
            
            if not po_item:
                continue
            
            # Create receipt item
            self.db.execute(
                """
                INSERT INTO goods_receipt_items (
                    id, goods_receipt_id, purchase_order_item_id, product_id,
                    quantity_ordered, quantity_received, quantity_accepted, quantity_rejected,
                    rejection_reason, zone_id, bin_location
                ) VALUES (
                    :id, :goods_receipt_id, :purchase_order_item_id, :product_id,
                    :quantity_ordered, :quantity_received, :quantity_accepted, :quantity_rejected,
                    :rejection_reason, :zone_id, :bin_location
                )
                """,
                {
                    "id": uuid.uuid4(),
                    "goods_receipt_id": receipt_id,
                    "purchase_order_item_id": uuid.UUID(item["po_item_id"]),
                    "product_id": po_item.product_id,
                    "quantity_ordered": po_item.quantity_ordered,
                    "quantity_received": item["quantity_received"],
                    "quantity_accepted": item.get("quantity_accepted", item["quantity_received"]),
                    "quantity_rejected": item.get("quantity_rejected", 0),
                    "rejection_reason": item.get("rejection_reason"),
                    "zone_id": uuid.UUID(item["zone_id"]) if item.get("zone_id") else None,
                    "bin_location": item.get("bin_location")
                }
            )
            
            # Update PO item quantity received
            new_quantity_received = po_item.quantity_received + item["quantity_received"]
            
            self.db.execute(
                """
                UPDATE purchase_order_items
                SET quantity_received = :quantity_received,
                    updated_at = NOW()
                WHERE id = :po_item_id
                """,
                {
                    "po_item_id": uuid.UUID(item["po_item_id"]),
                    "quantity_received": new_quantity_received
                }
            )
            
            # Record inbound stock movement for accepted quantity
            if item.get("quantity_accepted", item["quantity_received"]) > 0:
                await self.inventory_manager.record_stock_movement(
                    StockMovementCreate(
                        warehouse_id=data.warehouse_id,
                        product_id=str(po_item.product_id),
                        movement_type=StockMovementType.INBOUND,
                        quantity=item.get("quantity_accepted", item["quantity_received"]),
                        reference_type="purchase_order",
                        reference_id=data.purchase_order_id,
                        performed_by=data.received_by
                    )
                )
            
            total_received += item["quantity_received"]
            
            if new_quantity_received < po_item.quantity_ordered:
                all_items_complete = False
        
        # Update PO status
        if all_items_complete:
            new_status = PurchaseOrderStatus.RECEIVED
        else:
            new_status = PurchaseOrderStatus.PARTIALLY_RECEIVED
        
        self.db.execute(
            """
            UPDATE purchase_orders
            SET status = :status,
                updated_at = NOW()
            WHERE id = :po_id
            """,
            {
                "po_id": uuid.UUID(data.purchase_order_id),
                "status": new_status.value
            }
        )
        
        # Mark receipt as complete if all items processed
        if all_items_complete:
            self.db.execute(
                """
                UPDATE goods_receipts
                SET is_complete = TRUE,
                    updated_at = NOW()
                WHERE id = :receipt_id
                """,
                {"receipt_id": receipt_id}
            )
        
        self.db.commit()
        
        logger.info(f"Goods receipt created: {receipt_number}, items={len(data.items)}, qty={total_received}")
        
        return {
            "receipt_id": str(receipt_id),
            "receipt_number": receipt_number,
            "purchase_order_id": data.purchase_order_id,
            "warehouse_id": data.warehouse_id,
            "total_items": len(data.items),
            "total_quantity_received": total_received,
            "is_complete": all_items_complete,
            "created_at": datetime.utcnow().isoformat()
        }
    
    # ========================================================================
    # PICKING OPERATIONS
    # ========================================================================
    
    async def create_pick_list(
        self,
        data: PickListCreate
    ) -> Dict[str, Any]:
        """Create pick list for order"""
        
        # Get order items
        order_items = self.db.execute(
            """
            SELECT 
                oi.id AS order_item_id,
                oi.product_id,
                oi.product_name,
                oi.product_sku,
                oi.quantity
            FROM order_items oi
            WHERE oi.order_id = :order_id
            """,
            {"order_id": uuid.UUID(data.order_id)}
        ).fetchall()
        
        if not order_items:
            raise ValueError("No items found for order")
        
        # Generate pick list number
        pick_list_number = f"PL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create pick list (using a simple table structure)
        pick_list = {
            "pick_list_number": pick_list_number,
            "order_id": data.order_id,
            "warehouse_id": data.warehouse_id,
            "picker_id": data.picker_id,
            "picker_name": data.picker_name,
            "priority": data.priority,
            "status": "pending",
            "items": []
        }
        
        # Check inventory availability and create pick list items
        for item in order_items:
            # Check inventory
            inventory = self.db.execute(
                """
                SELECT quantity_available
                FROM inventory
                WHERE warehouse_id = :warehouse_id AND product_id = :product_id
                """,
                {
                    "warehouse_id": uuid.UUID(data.warehouse_id),
                    "product_id": item.product_id
                }
            ).first()
            
            if not inventory or inventory.quantity_available < item.quantity:
                pick_list["items"].append({
                    "order_item_id": str(item.order_item_id),
                    "product_id": str(item.product_id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "quantity_ordered": item.quantity,
                    "quantity_available": inventory.quantity_available if inventory else 0,
                    "quantity_to_pick": min(item.quantity, inventory.quantity_available if inventory else 0),
                    "status": "insufficient_stock" if not inventory or inventory.quantity_available < item.quantity else "ready"
                })
            else:
                pick_list["items"].append({
                    "order_item_id": str(item.order_item_id),
                    "product_id": str(item.product_id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "quantity_ordered": item.quantity,
                    "quantity_available": inventory.quantity_available,
                    "quantity_to_pick": item.quantity,
                    "status": "ready"
                })
                
                # Reserve inventory
                await self.inventory_manager.reserve_inventory(
                    data.warehouse_id,
                    str(item.product_id),
                    item.quantity
                )
        
        logger.info(f"Pick list created: {pick_list_number}, items={len(pick_list['items'])}")
        
        return pick_list
    
    async def complete_picking(
        self,
        pick_list_number: str,
        picked_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Complete picking operation"""
        
        # Update picked quantities and statuses
        # In a real system, this would update a pick_lists table
        
        logger.info(f"Picking completed: {pick_list_number}, items={len(picked_items)}")
        
        return {
            "pick_list_number": pick_list_number,
            "status": "completed",
            "items_picked": len(picked_items),
            "completed_at": datetime.utcnow().isoformat()
        }
    
    # ========================================================================
    # PACKING OPERATIONS
    # ========================================================================
    
    async def create_packing(
        self,
        data: PackingCreate
    ) -> Dict[str, Any]:
        """Create packing record"""
        
        # Get shipment
        shipment = self.db.execute(
            """
            SELECT id, shipment_number, status
            FROM shipments
            WHERE id = :shipment_id
            """,
            {"shipment_id": uuid.UUID(data.shipment_id)}
        ).first()
        
        if not shipment:
            raise ValueError("Shipment not found")
        
        if shipment.status != 'picked':
            raise ValueError(f"Cannot pack shipment with status: {shipment.status}")
        
        # Update shipment with packing details
        self.db.execute(
            """
            UPDATE shipments
            SET status = :status,
                number_of_packages = :number_of_packages,
                total_weight_kg = :total_weight_kg,
                total_volume_cbm = :total_volume_cbm,
                updated_at = NOW()
            WHERE id = :shipment_id
            """,
            {
                "shipment_id": uuid.UUID(data.shipment_id),
                "status": ShipmentStatus.PACKED.value,
                "number_of_packages": data.number_of_packages,
                "total_weight_kg": data.total_weight_kg,
                "total_volume_cbm": data.total_volume_cbm
            }
        )
        
        self.db.commit()
        
        logger.info(f"Packing completed: shipment={shipment.shipment_number}, packages={data.number_of_packages}")
        
        return {
            "shipment_id": data.shipment_id,
            "shipment_number": shipment.shipment_number,
            "status": ShipmentStatus.PACKED.value,
            "number_of_packages": data.number_of_packages,
            "total_weight_kg": float(data.total_weight_kg) if data.total_weight_kg else None,
            "total_volume_cbm": float(data.total_volume_cbm) if data.total_volume_cbm else None,
            "packed_at": datetime.utcnow().isoformat()
        }
    
    # ========================================================================
    # SHIPPING OPERATIONS
    # ========================================================================
    
    async def create_shipment(
        self,
        data: ShipmentCreate
    ) -> Dict[str, Any]:
        """Create shipment for order"""
        
        # Generate shipment number
        shipment_number = f"SH-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create shipment
        shipment_id = uuid.uuid4()
        
        self.db.execute(
            """
            INSERT INTO shipments (
                id, shipment_number, order_id, warehouse_id,
                carrier, service_level, shipping_address, return_address,
                total_weight_kg, total_volume_cbm, number_of_packages,
                shipping_cost, insurance_cost, signature_required,
                special_instructions, notes, status
            ) VALUES (
                :id, :shipment_number, :order_id, :warehouse_id,
                :carrier, :service_level, :shipping_address, :return_address,
                :total_weight_kg, :total_volume_cbm, :number_of_packages,
                :shipping_cost, :insurance_cost, :signature_required,
                :special_instructions, :notes, :status
            )
            """,
            {
                "id": shipment_id,
                "shipment_number": shipment_number,
                "order_id": uuid.UUID(data.order_id),
                "warehouse_id": uuid.UUID(data.warehouse_id),
                "carrier": data.carrier,
                "service_level": data.service_level,
                "shipping_address": data.shipping_address,
                "return_address": data.return_address,
                "total_weight_kg": data.total_weight_kg,
                "total_volume_cbm": data.total_volume_cbm,
                "number_of_packages": data.number_of_packages,
                "shipping_cost": data.shipping_cost,
                "insurance_cost": data.insurance_cost,
                "signature_required": data.signature_required,
                "special_instructions": data.special_instructions,
                "notes": data.notes,
                "status": ShipmentStatus.PENDING.value
            }
        )
        
        # Create shipment items
        for item in data.items:
            self.db.execute(
                """
                INSERT INTO shipment_items (
                    id, shipment_id, order_item_id, product_id,
                    product_name, product_sku, quantity
                ) VALUES (
                    :id, :shipment_id, :order_item_id, :product_id,
                    :product_name, :product_sku, :quantity
                )
                """,
                {
                    "id": uuid.uuid4(),
                    "shipment_id": shipment_id,
                    "order_item_id": uuid.UUID(item["order_item_id"]),
                    "product_id": uuid.UUID(item["product_id"]),
                    "product_name": item.get("product_name", ""),
                    "product_sku": item.get("product_sku", ""),
                    "quantity": item["quantity"]
                }
            )
            
            # Fulfill reservation (convert reserved to outbound)
            await self.inventory_manager.fulfill_reservation(
                data.warehouse_id,
                item["product_id"],
                item["quantity"],
                data.order_id
            )
        
        self.db.commit()
        
        logger.info(f"Shipment created: {shipment_number}, items={len(data.items)}")
        
        return {
            "shipment_id": str(shipment_id),
            "shipment_number": shipment_number,
            "order_id": data.order_id,
            "warehouse_id": data.warehouse_id,
            "carrier": data.carrier,
            "service_level": data.service_level,
            "status": ShipmentStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def update_shipment(
        self,
        shipment_id: str,
        data: ShipmentUpdate
    ) -> Dict[str, Any]:
        """Update shipment details"""
        
        updates = []
        params = {"shipment_id": uuid.UUID(shipment_id)}
        
        if data.tracking_number:
            updates.append("tracking_number = :tracking_number")
            params["tracking_number"] = data.tracking_number
        
        if data.tracking_url:
            updates.append("tracking_url = :tracking_url")
            params["tracking_url"] = data.tracking_url
        
        if data.status:
            updates.append("status = :status")
            params["status"] = data.status.value
            
            if data.status == ShipmentStatus.SHIPPED:
                updates.append("ship_date = :ship_date")
                params["ship_date"] = data.ship_date or datetime.utcnow()
            
            elif data.status == ShipmentStatus.DELIVERED:
                updates.append("actual_delivery_date = :actual_delivery_date")
                params["actual_delivery_date"] = data.actual_delivery_date or datetime.utcnow()
        
        if data.estimated_delivery_date:
            updates.append("estimated_delivery_date = :estimated_delivery_date")
            params["estimated_delivery_date"] = data.estimated_delivery_date
        
        if data.signature_received is not None:
            updates.append("signature_received = :signature_received")
            params["signature_received"] = data.signature_received
        
        if data.signed_by:
            updates.append("signed_by = :signed_by")
            params["signed_by"] = data.signed_by
        
        if data.notes:
            updates.append("notes = :notes")
            params["notes"] = data.notes
        
        if not updates:
            raise ValueError("No fields to update")
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE shipments
            SET {", ".join(updates)}
            WHERE id = :shipment_id
        """
        
        self.db.execute(query, params)
        self.db.commit()
        
        logger.info(f"Shipment updated: {shipment_id}")
        
        # Get updated shipment
        shipment = self.db.execute(
            """
            SELECT 
                id, shipment_number, order_id, warehouse_id,
                carrier, service_level, tracking_number, tracking_url,
                status, ship_date, estimated_delivery_date, actual_delivery_date,
                created_at, updated_at
            FROM shipments
            WHERE id = :shipment_id
            """,
            {"shipment_id": uuid.UUID(shipment_id)}
        ).first()
        
        return {
            "shipment_id": str(shipment.id),
            "shipment_number": shipment.shipment_number,
            "order_id": str(shipment.order_id),
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "tracking_url": shipment.tracking_url,
            "status": shipment.status,
            "ship_date": shipment.ship_date.isoformat() if shipment.ship_date else None,
            "estimated_delivery_date": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else None,
            "actual_delivery_date": shipment.actual_delivery_date.isoformat() if shipment.actual_delivery_date else None,
            "updated_at": shipment.updated_at.isoformat()
        }
    
    async def get_shipment(self, shipment_id: str) -> Dict[str, Any]:
        """Get shipment details"""
        
        shipment = self.db.execute(
            """
            SELECT 
                s.id, s.shipment_number, s.order_id, s.warehouse_id,
                w.name AS warehouse_name,
                s.carrier, s.service_level, s.tracking_number, s.tracking_url,
                s.shipping_address, s.return_address,
                s.total_weight_kg, s.total_volume_cbm, s.number_of_packages,
                s.shipping_cost, s.insurance_cost,
                s.signature_required, s.signature_received, s.signed_by,
                s.status, s.ship_date, s.estimated_delivery_date, s.actual_delivery_date,
                s.special_instructions, s.notes,
                s.created_at, s.updated_at
            FROM shipments s
            JOIN warehouses w ON s.warehouse_id = w.id
            WHERE s.id = :shipment_id
            """,
            {"shipment_id": uuid.UUID(shipment_id)}
        ).first()
        
        if not shipment:
            raise ValueError("Shipment not found")
        
        # Get shipment items
        items = self.db.execute(
            """
            SELECT 
                si.id, si.order_item_id, si.product_id,
                si.product_name, si.product_sku, si.quantity
            FROM shipment_items si
            WHERE si.shipment_id = :shipment_id
            """,
            {"shipment_id": uuid.UUID(shipment_id)}
        ).fetchall()
        
        return {
            "shipment_id": str(shipment.id),
            "shipment_number": shipment.shipment_number,
            "order_id": str(shipment.order_id),
            "warehouse_id": str(shipment.warehouse_id),
            "warehouse_name": shipment.warehouse_name,
            "carrier": shipment.carrier,
            "service_level": shipment.service_level,
            "tracking_number": shipment.tracking_number,
            "tracking_url": shipment.tracking_url,
            "shipping_address": shipment.shipping_address,
            "return_address": shipment.return_address,
            "total_weight_kg": float(shipment.total_weight_kg) if shipment.total_weight_kg else None,
            "total_volume_cbm": float(shipment.total_volume_cbm) if shipment.total_volume_cbm else None,
            "number_of_packages": shipment.number_of_packages,
            "shipping_cost": float(shipment.shipping_cost) if shipment.shipping_cost else None,
            "insurance_cost": float(shipment.insurance_cost) if shipment.insurance_cost else None,
            "signature_required": shipment.signature_required,
            "signature_received": shipment.signature_received,
            "signed_by": shipment.signed_by,
            "status": shipment.status,
            "ship_date": shipment.ship_date.isoformat() if shipment.ship_date else None,
            "estimated_delivery_date": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else None,
            "actual_delivery_date": shipment.actual_delivery_date.isoformat() if shipment.actual_delivery_date else None,
            "special_instructions": shipment.special_instructions,
            "notes": shipment.notes,
            "created_at": shipment.created_at.isoformat(),
            "updated_at": shipment.updated_at.isoformat(),
            "items": [
                {
                    "id": str(item.id),
                    "order_item_id": str(item.order_item_id),
                    "product_id": str(item.product_id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "quantity": item.quantity
                }
                for item in items
            ]
        }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/receiving/goods-receipt", response_model=Dict[str, Any])
async def create_goods_receipt(
    data: GoodsReceiptCreate,
    db: Session = Depends(get_db)
):
    """Create goods receipt"""
    ops = WarehouseOperations(db)
    return await ops.create_goods_receipt(data)

@app.post("/picking/pick-list", response_model=Dict[str, Any])
async def create_pick_list(
    data: PickListCreate,
    db: Session = Depends(get_db)
):
    """Create pick list"""
    ops = WarehouseOperations(db)
    return await ops.create_pick_list(data)

@app.post("/packing", response_model=Dict[str, Any])
async def create_packing(
    data: PackingCreate,
    db: Session = Depends(get_db)
):
    """Create packing record"""
    ops = WarehouseOperations(db)
    return await ops.create_packing(data)

@app.post("/shipping/shipment", response_model=Dict[str, Any])
async def create_shipment(
    data: ShipmentCreate,
    db: Session = Depends(get_db)
):
    """Create shipment"""
    ops = WarehouseOperations(db)
    return await ops.create_shipment(data)

@app.put("/shipping/shipment/{shipment_id}", response_model=Dict[str, Any])
async def update_shipment(
    shipment_id: str,
    data: ShipmentUpdate,
    db: Session = Depends(get_db)
):
    """Update shipment"""
    ops = WarehouseOperations(db)
    return await ops.update_shipment(shipment_id, data)

@app.get("/shipping/shipment/{shipment_id}", response_model=Dict[str, Any])
async def get_shipment(
    shipment_id: str,
    db: Session = Depends(get_db)
):
    """Get shipment details"""
    ops = WarehouseOperations(db)
    return await ops.get_shipment(shipment_id)

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "warehouse-operations",
        "version": "1.0.0"
    }

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

