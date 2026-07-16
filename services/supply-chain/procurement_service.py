"""
Procurement Service
Supplier management and purchase order processing
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date, timedelta
from enum import Enum
import uuid
import os
import logging
from pydantic import BaseModel, EmailStr

from inventory_service import get_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
# ============================================================================

class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"

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

class SupplierCreate(BaseModel):
    code: str
    name: str
    legal_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    billing_address: Optional[Dict[str, Any]] = None
    shipping_address: Optional[str] = None
    tax_id: Optional[str] = None
    business_registration: Optional[str] = None
    payment_terms: Optional[str] = "Net 30"
    currency: str = "USD"
    is_preferred: bool = False
    notes: Optional[str] = None

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    billing_address: Optional[Dict[str, Any]] = None
    shipping_address: Optional[Dict[str, Any]] = None
    payment_terms: Optional[str] = None
    status: Optional[SupplierStatus] = None
    is_preferred: Optional[bool] = None
    notes: Optional[str] = None

class SupplierProductCreate(BaseModel):
    supplier_id: str
    product_id: str
    supplier_sku: Optional[str] = None
    unit_price: Decimal
    currency: str = "USD"
    minimum_order_quantity: int = 1
    lead_time_days: int = 7
    is_preferred: bool = False

class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    warehouse_id: str
    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    buyer_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_email: Optional[EmailStr] = None
    shipping_address: Optional[Dict[str, Any]] = None
    shipping_method: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    items: List[Dict[str, Any]]  # [{"product_id": "...", "quantity": 10, "unit_price": 100.00}]

class PurchaseOrderUpdate(BaseModel):
    status: Optional[PurchaseOrderStatus] = None
    expected_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Procurement Service",
    description="Supplier management and purchase order processing",
    version="1.0.0"
)

# ============================================================================
# PROCUREMENT MANAGER CLASS
# ============================================================================

class ProcurementManager:
    """Procurement operations management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ========================================================================
    # SUPPLIER MANAGEMENT
    # ========================================================================
    
    async def create_supplier(self, data: SupplierCreate) -> Dict[str, Any]:
        """Create new supplier"""
        
        # Check if code already exists
        existing = self.db.execute(
            "SELECT id FROM suppliers WHERE code = :code",
            {"code": data.code}
        ).first()
        
        if existing:
            raise ValueError(f"Supplier with code '{data.code}' already exists")
        
        supplier_id = uuid.uuid4()
        
        self.db.execute(
            """
            INSERT INTO suppliers (
                id, code, name, legal_name, email, phone, website,
                billing_address, shipping_address, tax_id, business_registration,
                payment_terms, currency, is_preferred, notes, status
            ) VALUES (
                :id, :code, :name, :legal_name, :email, :phone, :website,
                :billing_address, :shipping_address, :tax_id, :business_registration,
                :payment_terms, :currency, :is_preferred, :notes, :status
            )
            """,
            {
                "id": supplier_id,
                "code": data.code,
                "name": data.name,
                "legal_name": data.legal_name,
                "email": data.email,
                "phone": data.phone,
                "website": data.website,
                "billing_address": data.billing_address,
                "shipping_address": data.shipping_address,
                "tax_id": data.tax_id,
                "business_registration": data.business_registration,
                "payment_terms": data.payment_terms,
                "currency": data.currency,
                "is_preferred": data.is_preferred,
                "notes": data.notes,
                "status": SupplierStatus.ACTIVE.value
            }
        )
        
        self.db.commit()
        
        logger.info(f"Supplier created: {data.code} - {data.name}")
        
        return await self.get_supplier(str(supplier_id))
    
    async def update_supplier(
        self,
        supplier_id: str,
        data: SupplierUpdate
    ) -> Dict[str, Any]:
        """Update supplier"""
        
        updates = []
        params = {"supplier_id": uuid.UUID(supplier_id)}
        
        if data.name:
            updates.append("name = :name")
            params["name"] = data.name
        
        if data.email:
            updates.append("email = :email")
            params["email"] = data.email
        
        if data.phone:
            updates.append("phone = :phone")
            params["phone"] = data.phone
        
        if data.website:
            updates.append("website = :website")
            params["website"] = data.website
        
        if data.billing_address:
            updates.append("billing_address = :billing_address")
            params["billing_address"] = data.billing_address
        
        if data.shipping_address:
            updates.append("shipping_address = :shipping_address")
            params["shipping_address"] = data.shipping_address
        
        if data.payment_terms:
            updates.append("payment_terms = :payment_terms")
            params["payment_terms"] = data.payment_terms
        
        if data.status:
            updates.append("status = :status")
            params["status"] = data.status.value
        
        if data.is_preferred is not None:
            updates.append("is_preferred = :is_preferred")
            params["is_preferred"] = data.is_preferred
        
        if data.notes:
            updates.append("notes = :notes")
            params["notes"] = data.notes
        
        if not updates:
            raise ValueError("No fields to update")
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE suppliers
            SET {", ".join(updates)}
            WHERE id = :supplier_id
        """
        
        self.db.execute(query, params)
        self.db.commit()
        
        logger.info(f"Supplier updated: {supplier_id}")
        
        return await self.get_supplier(supplier_id)
    
    async def get_supplier(self, supplier_id: str) -> Dict[str, Any]:
        """Get supplier details"""
        
        supplier = self.db.execute(
            """
            SELECT * FROM supplier_performance
            WHERE supplier_id = :supplier_id
            """,
            {"supplier_id": uuid.UUID(supplier_id)}
        ).first()
        
        if not supplier:
            raise ValueError("Supplier not found")
        
        return {
            "supplier_id": str(supplier.supplier_id),
            "code": supplier.supplier_code,
            "name": supplier.supplier_name,
            "rating": float(supplier.rating) if supplier.rating else 0.0,
            "on_time_delivery_rate": float(supplier.on_time_delivery_rate) if supplier.on_time_delivery_rate else 0.0,
            "quality_score": float(supplier.quality_score) if supplier.quality_score else 0.0,
            "total_orders": supplier.total_orders,
            "total_spent": float(supplier.total_spent) if supplier.total_spent else 0.0,
            "active_orders": supplier.active_orders,
            "completed_orders": supplier.completed_orders,
            "avg_delivery_delay_days": float(supplier.avg_delivery_delay_days) if supplier.avg_delivery_delay_days else 0.0
        }
    
    async def list_suppliers(
        self,
        status: Optional[SupplierStatus] = None,
        is_preferred: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List suppliers"""
        
        query = "SELECT * FROM supplier_performance WHERE 1=1"
        params = {}
        
        if status:
            # Note: supplier_performance view doesn't include status, 
            # so we'd need to join with suppliers table
            pass
        
        if is_preferred is not None:
            # Same issue - would need to join
            pass
        
        result = self.db.execute(query, params)
        
        suppliers = []
        for row in result:
            suppliers.append({
                "supplier_id": str(row.supplier_id),
                "code": row.supplier_code,
                "name": row.supplier_name,
                "rating": float(row.rating) if row.rating else 0.0,
                "on_time_delivery_rate": float(row.on_time_delivery_rate) if row.on_time_delivery_rate else 0.0,
                "quality_score": float(row.quality_score) if row.quality_score else 0.0,
                "total_orders": row.total_orders,
                "total_spent": float(row.total_spent) if row.total_spent else 0.0,
                "active_orders": row.active_orders
            })
        
        return suppliers
    
    async def add_supplier_product(
        self,
        data: SupplierProductCreate
    ) -> Dict[str, Any]:
        """Add product to supplier catalog"""
        
        # Check if already exists
        existing = self.db.execute(
            """
            SELECT id FROM supplier_products
            WHERE supplier_id = :supplier_id AND product_id = :product_id
            """,
            {
                "supplier_id": uuid.UUID(data.supplier_id),
                "product_id": uuid.UUID(data.product_id)
            }
        ).first()
        
        if existing:
            raise ValueError("Product already exists for this supplier")
        
        sp_id = uuid.uuid4()
        
        self.db.execute(
            """
            INSERT INTO supplier_products (
                id, supplier_id, product_id, supplier_sku,
                unit_price, currency, minimum_order_quantity,
                lead_time_days, is_preferred
            ) VALUES (
                :id, :supplier_id, :product_id, :supplier_sku,
                :unit_price, :currency, :minimum_order_quantity,
                :lead_time_days, :is_preferred
            )
            """,
            {
                "id": sp_id,
                "supplier_id": uuid.UUID(data.supplier_id),
                "product_id": uuid.UUID(data.product_id),
                "supplier_sku": data.supplier_sku,
                "unit_price": data.unit_price,
                "currency": data.currency,
                "minimum_order_quantity": data.minimum_order_quantity,
                "lead_time_days": data.lead_time_days,
                "is_preferred": data.is_preferred
            }
        )
        
        self.db.commit()
        
        logger.info(f"Supplier product added: supplier={data.supplier_id}, product={data.product_id}")
        
        return {
            "id": str(sp_id),
            "supplier_id": data.supplier_id,
            "product_id": data.product_id,
            "supplier_sku": data.supplier_sku,
            "unit_price": float(data.unit_price),
            "currency": data.currency,
            "minimum_order_quantity": data.minimum_order_quantity,
            "lead_time_days": data.lead_time_days,
            "is_preferred": data.is_preferred
        }
    
    # ========================================================================
    # PURCHASE ORDER MANAGEMENT
    # ========================================================================
    
    async def create_purchase_order(
        self,
        data: PurchaseOrderCreate
    ) -> Dict[str, Any]:
        """Create purchase order"""
        
        # Generate PO number
        po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate totals
        subtotal = Decimal('0.00')
        for item in data.items:
            line_total = Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))
            subtotal += line_total
        
        tax_amount = subtotal * Decimal('0.00')  # Configure tax rate
        shipping_amount = Decimal('0.00')  # Configure shipping
        discount_amount = Decimal('0.00')
        total_amount = subtotal + tax_amount + shipping_amount - discount_amount
        
        # Create PO
        po_id = uuid.uuid4()
        
        self.db.execute(
            """
            INSERT INTO purchase_orders (
                id, po_number, supplier_id, warehouse_id,
                subtotal, tax_amount, shipping_amount, discount_amount, total_amount,
                order_date, expected_delivery_date,
                buyer_id, buyer_name, buyer_email,
                shipping_address, shipping_method,
                notes, internal_notes, terms_and_conditions,
                status
            ) VALUES (
                :id, :po_number, :supplier_id, :warehouse_id,
                :subtotal, :tax_amount, :shipping_amount, :discount_amount, :total_amount,
                :order_date, :expected_delivery_date,
                :buyer_id, :buyer_name, :buyer_email,
                :shipping_address, :shipping_method,
                :notes, :internal_notes, :terms_and_conditions,
                :status
            )
            """,
            {
                "id": po_id,
                "po_number": po_number,
                "supplier_id": uuid.UUID(data.supplier_id),
                "warehouse_id": uuid.UUID(data.warehouse_id),
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "shipping_amount": shipping_amount,
                "discount_amount": discount_amount,
                "total_amount": total_amount,
                "order_date": data.order_date or date.today(),
                "expected_delivery_date": data.expected_delivery_date,
                "buyer_id": uuid.UUID(data.buyer_id) if data.buyer_id else None,
                "buyer_name": data.buyer_name,
                "buyer_email": data.buyer_email,
                "shipping_address": data.shipping_address,
                "shipping_method": data.shipping_method,
                "notes": data.notes,
                "internal_notes": data.internal_notes,
                "terms_and_conditions": data.terms_and_conditions,
                "status": PurchaseOrderStatus.DRAFT.value
            }
        )
        
        # Create PO items
        for item in data.items:
            line_total = Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))
            
            self.db.execute(
                """
                INSERT INTO purchase_order_items (
                    id, purchase_order_id, product_id,
                    product_name, product_sku, supplier_sku,
                    quantity_ordered, unit_price, line_total,
                    expected_delivery_date, notes
                ) VALUES (
                    :id, :purchase_order_id, :product_id,
                    :product_name, :product_sku, :supplier_sku,
                    :quantity_ordered, :unit_price, :line_total,
                    :expected_delivery_date, :notes
                )
                """,
                {
                    "id": uuid.uuid4(),
                    "purchase_order_id": po_id,
                    "product_id": uuid.UUID(item['product_id']),
                    "product_name": item.get('product_name', ''),
                    "product_sku": item.get('product_sku', ''),
                    "supplier_sku": item.get('supplier_sku', ''),
                    "quantity_ordered": item['quantity'],
                    "unit_price": Decimal(str(item['unit_price'])),
                    "line_total": line_total,
                    "expected_delivery_date": item.get('expected_delivery_date'),
                    "notes": item.get('notes')
                }
            )
        
        self.db.commit()
        
        logger.info(f"Purchase order created: {po_number}, items={len(data.items)}, total=${total_amount}")
        
        return await self.get_purchase_order(str(po_id))
    
    async def update_purchase_order(
        self,
        po_id: str,
        data: PurchaseOrderUpdate
    ) -> Dict[str, Any]:
        """Update purchase order"""
        
        updates = []
        params = {"po_id": uuid.UUID(po_id)}
        
        if data.status:
            updates.append("status = :status")
            params["status"] = data.status.value
            
            if data.status == PurchaseOrderStatus.APPROVED:
                updates.append("approved_at = NOW()")
            elif data.status == PurchaseOrderStatus.SENT_TO_SUPPLIER:
                updates.append("sent_at = NOW()")
            elif data.status == PurchaseOrderStatus.ACKNOWLEDGED:
                updates.append("acknowledged_at = NOW()")
            elif data.status == PurchaseOrderStatus.RECEIVED:
                updates.append("completed_at = NOW()")
            elif data.status == PurchaseOrderStatus.CANCELLED:
                updates.append("cancelled_at = NOW()")
        
        if data.expected_delivery_date:
            updates.append("expected_delivery_date = :expected_delivery_date")
            params["expected_delivery_date"] = data.expected_delivery_date
        
        if data.actual_delivery_date:
            updates.append("actual_delivery_date = :actual_delivery_date")
            params["actual_delivery_date"] = data.actual_delivery_date
        
        if data.tracking_number:
            updates.append("tracking_number = :tracking_number")
            params["tracking_number"] = data.tracking_number
        
        if data.notes:
            updates.append("notes = :notes")
            params["notes"] = data.notes
        
        if not updates:
            raise ValueError("No fields to update")
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE purchase_orders
            SET {", ".join(updates)}
            WHERE id = :po_id
        """
        
        self.db.execute(query, params)
        self.db.commit()
        
        logger.info(f"Purchase order updated: {po_id}")
        
        return await self.get_purchase_order(po_id)
    
    async def get_purchase_order(self, po_id: str) -> Dict[str, Any]:
        """Get purchase order details"""
        
        po = self.db.execute(
            """
            SELECT 
                po.id, po.po_number, po.supplier_id, po.warehouse_id,
                s.name AS supplier_name, s.code AS supplier_code,
                w.name AS warehouse_name, w.code AS warehouse_code,
                po.subtotal, po.tax_amount, po.shipping_amount,
                po.discount_amount, po.total_amount, po.currency,
                po.status, po.order_date, po.expected_delivery_date,
                po.actual_delivery_date, po.buyer_name, po.buyer_email,
                po.shipping_address, po.shipping_method, po.tracking_number,
                po.notes, po.internal_notes, po.terms_and_conditions,
                po.created_at, po.updated_at, po.approved_at,
                po.sent_at, po.acknowledged_at, po.completed_at
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            JOIN warehouses w ON po.warehouse_id = w.id
            WHERE po.id = :po_id
            """,
            {"po_id": uuid.UUID(po_id)}
        ).first()
        
        if not po:
            raise ValueError("Purchase order not found")
        
        # Get PO items
        items = self.db.execute(
            """
            SELECT 
                id, product_id, product_name, product_sku, supplier_sku,
                quantity_ordered, quantity_received, quantity_pending,
                unit_price, tax_rate, discount_percentage, line_total,
                expected_delivery_date, notes
            FROM purchase_order_items
            WHERE purchase_order_id = :po_id
            """,
            {"po_id": uuid.UUID(po_id)}
        ).fetchall()
        
        return {
            "po_id": str(po.id),
            "po_number": po.po_number,
            "supplier_id": str(po.supplier_id),
            "supplier_name": po.supplier_name,
            "supplier_code": po.supplier_code,
            "warehouse_id": str(po.warehouse_id),
            "warehouse_name": po.warehouse_name,
            "warehouse_code": po.warehouse_code,
            "subtotal": float(po.subtotal),
            "tax_amount": float(po.tax_amount),
            "shipping_amount": float(po.shipping_amount),
            "discount_amount": float(po.discount_amount),
            "total_amount": float(po.total_amount),
            "currency": po.currency,
            "status": po.status,
            "order_date": po.order_date.isoformat(),
            "expected_delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
            "actual_delivery_date": po.actual_delivery_date.isoformat() if po.actual_delivery_date else None,
            "buyer_name": po.buyer_name,
            "buyer_email": po.buyer_email,
            "shipping_address": po.shipping_address,
            "shipping_method": po.shipping_method,
            "tracking_number": po.tracking_number,
            "notes": po.notes,
            "internal_notes": po.internal_notes,
            "terms_and_conditions": po.terms_and_conditions,
            "created_at": po.created_at.isoformat(),
            "updated_at": po.updated_at.isoformat(),
            "approved_at": po.approved_at.isoformat() if po.approved_at else None,
            "sent_at": po.sent_at.isoformat() if po.sent_at else None,
            "acknowledged_at": po.acknowledged_at.isoformat() if po.acknowledged_at else None,
            "completed_at": po.completed_at.isoformat() if po.completed_at else None,
            "items": [
                {
                    "id": str(item.id),
                    "product_id": str(item.product_id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "supplier_sku": item.supplier_sku,
                    "quantity_ordered": item.quantity_ordered,
                    "quantity_received": item.quantity_received,
                    "quantity_pending": item.quantity_pending,
                    "unit_price": float(item.unit_price),
                    "line_total": float(item.line_total),
                    "expected_delivery_date": item.expected_delivery_date.isoformat() if item.expected_delivery_date else None,
                    "notes": item.notes
                }
                for item in items
            ]
        }
    
    async def list_purchase_orders(
        self,
        supplier_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        status: Optional[PurchaseOrderStatus] = None
    ) -> List[Dict[str, Any]]:
        """List purchase orders"""
        
        query = """
            SELECT 
                po.id, po.po_number, po.supplier_id, po.warehouse_id,
                s.name AS supplier_name, w.name AS warehouse_name,
                po.total_amount, po.currency, po.status,
                po.order_date, po.expected_delivery_date,
                po.created_at
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            JOIN warehouses w ON po.warehouse_id = w.id
            WHERE 1=1
        """
        
        params = {}
        
        if supplier_id:
            query += " AND po.supplier_id = :supplier_id"
            params["supplier_id"] = uuid.UUID(supplier_id)
        
        if warehouse_id:
            query += " AND po.warehouse_id = :warehouse_id"
            params["warehouse_id"] = uuid.UUID(warehouse_id)
        
        if status:
            query += " AND po.status = :status"
            params["status"] = status.value
        
        query += " ORDER BY po.created_at DESC"
        
        result = self.db.execute(query, params)
        
        pos = []
        for row in result:
            pos.append({
                "po_id": str(row.id),
                "po_number": row.po_number,
                "supplier_id": str(row.supplier_id),
                "supplier_name": row.supplier_name,
                "warehouse_id": str(row.warehouse_id),
                "warehouse_name": row.warehouse_name,
                "total_amount": float(row.total_amount),
                "currency": row.currency,
                "status": row.status,
                "order_date": row.order_date.isoformat(),
                "expected_delivery_date": row.expected_delivery_date.isoformat() if row.expected_delivery_date else None,
                "created_at": row.created_at.isoformat()
            })
        
        return pos

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/suppliers", response_model=Dict[str, Any])
async def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db)
):
    """Create supplier"""
    manager = ProcurementManager(db)
    return await manager.create_supplier(data)

@app.put("/suppliers/{supplier_id}", response_model=Dict[str, Any])
async def update_supplier(
    supplier_id: str,
    data: SupplierUpdate,
    db: Session = Depends(get_db)
):
    """Update supplier"""
    manager = ProcurementManager(db)
    return await manager.update_supplier(supplier_id, data)

@app.get("/suppliers/{supplier_id}", response_model=Dict[str, Any])
async def get_supplier(
    supplier_id: str,
    db: Session = Depends(get_db)
):
    """Get supplier"""
    manager = ProcurementManager(db)
    return await manager.get_supplier(supplier_id)

@app.get("/suppliers", response_model=List[Dict[str, Any]])
async def list_suppliers(
    status: Optional[SupplierStatus] = None,
    is_preferred: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List suppliers"""
    manager = ProcurementManager(db)
    return await manager.list_suppliers(status, is_preferred)

@app.post("/supplier-products", response_model=Dict[str, Any])
async def add_supplier_product(
    data: SupplierProductCreate,
    db: Session = Depends(get_db)
):
    """Add supplier product"""
    manager = ProcurementManager(db)
    return await manager.add_supplier_product(data)

@app.post("/purchase-orders", response_model=Dict[str, Any])
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db)
):
    """Create purchase order"""
    manager = ProcurementManager(db)
    return await manager.create_purchase_order(data)

@app.put("/purchase-orders/{po_id}", response_model=Dict[str, Any])
async def update_purchase_order(
    po_id: str,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db)
):
    """Update purchase order"""
    manager = ProcurementManager(db)
    return await manager.update_purchase_order(po_id, data)

@app.get("/purchase-orders/{po_id}", response_model=Dict[str, Any])
async def get_purchase_order(
    po_id: str,
    db: Session = Depends(get_db)
):
    """Get purchase order"""
    manager = ProcurementManager(db)
    return await manager.get_purchase_order(po_id)

@app.get("/purchase-orders", response_model=List[Dict[str, Any]])
async def list_purchase_orders(
    supplier_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    status: Optional[PurchaseOrderStatus] = None,
    db: Session = Depends(get_db)
):
    """List purchase orders"""
    manager = ProcurementManager(db)
    return await manager.list_purchase_orders(supplier_id, warehouse_id, status)

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "procurement-service",
        "version": "1.0.0"
    }

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

