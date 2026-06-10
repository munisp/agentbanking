"""
Extensive Inventory Management — API Router
Merges:
1. Original agent inventory management (SIM cards, POS paper, branded materials)
2. New full merchant inventory management (products, stock, purchase orders, AI photo)
"""
import os
import uuid
import base64
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from enum import Enum

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

# ─────────────────────────────────────────────
# SECTION 1: AGENT INVENTORY (original — SIM cards, POS paper, etc.)
# ─────────────────────────────────────────────

WEBHOOK_URL = os.getenv("INVENTORY_WEBHOOK_URL", "")
LOW_STOCK_WEBHOOK_ENABLED = os.getenv("LOW_STOCK_WEBHOOK_ENABLED", "true").lower() == "true"
_webhook_log: List[Dict[str, Any]] = []


class ItemCategory(str, Enum):
    SIM_CARD = "sim_card"
    POS_PAPER = "pos_paper"
    POS_TERMINAL = "pos_terminal"
    BRANDED_MATERIAL = "branded_material"
    ID_CARD_STOCK = "id_card_stock"
    RECEIPT_ROLL = "receipt_roll"
    MARKETING_FLYER = "marketing_flyer"
    SIGNAGE = "signage"
    CASH_BAG = "cash_bag"
    OTHER = "other"


class ItemStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DEPLETED = "depleted"
    DAMAGED = "damaged"
    RETURNED = "returned"


class ItemCreate(BaseModel):
    name: str
    category: ItemCategory
    description: Optional[str] = None
    sku: Optional[str] = None
    quantity: int = Field(..., ge=0)
    unit: str = Field(default="piece")
    unit_cost: Optional[float] = None
    currency: str = Field(default="NGN")
    warehouse_id: Optional[str] = None
    reorder_level: int = Field(default=10, ge=0)
    metadata: Optional[Dict[str, Any]] = None


class ItemResponse(BaseModel):
    id: str
    name: str
    category: ItemCategory
    description: Optional[str] = None
    sku: str
    quantity: int
    assigned_quantity: int = 0
    available_quantity: int = 0
    unit: str
    unit_cost: Optional[float] = None
    currency: str
    warehouse_id: Optional[str] = None
    reorder_level: int
    status: ItemStatus
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class AgentAssignment(BaseModel):
    item_id: str
    agent_id: str
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None


class AgentAssignmentResponse(BaseModel):
    assignment_id: str
    item_id: str
    item_name: str
    agent_id: str
    quantity: int
    status: str
    assigned_at: str
    returned_at: Optional[str] = None
    notes: Optional[str] = None


class TransferRequest(BaseModel):
    item_id: str
    from_agent_id: str
    to_agent_id: str
    quantity: int = Field(..., gt=0)
    reason: Optional[str] = None


_items: Dict[str, ItemResponse] = {}
_assignments: Dict[str, AgentAssignmentResponse] = {}
_agent_inventory: Dict[str, Dict[str, int]] = {}
_sku_counter = 0


def _generate_agent_sku(category: ItemCategory) -> str:
    global _sku_counter
    _sku_counter += 1
    prefix = category.value[:3].upper()
    return f"{prefix}-{_sku_counter:06d}"


def _update_item_status(item: ItemResponse):
    if item.available_quantity <= 0 and item.assigned_quantity > 0:
        item.status = ItemStatus.ASSIGNED
    elif item.quantity <= 0:
        item.status = ItemStatus.DEPLETED
    else:
        item.status = ItemStatus.AVAILABLE


async def _check_low_stock_webhook(item: ItemResponse, agent_id: Optional[str] = None):
    if not LOW_STOCK_WEBHOOK_ENABLED or item.available_quantity > item.reorder_level:
        return
    payload = {
        "alert_type": "low_stock",
        "item_id": item.id,
        "item_name": item.name,
        "category": item.category.value,
        "sku": item.sku,
        "available_quantity": item.available_quantity,
        "reorder_level": item.reorder_level,
        "agent_id": agent_id,
        "severity": "critical" if item.available_quantity == 0 else "warning",
        "triggered_at": datetime.utcnow().isoformat(),
    }
    _webhook_log.append(payload)
    if WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(WEBHOOK_URL, json=payload)
        except Exception as e:
            logger.warning(f"Low stock webhook failed: {e}")


@router.get("/")
async def root():
    return {"service": "inventory-management", "status": "ok", "total_items": len(_items)}


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "inventory-management"}


@router.post("/agent-items", response_model=ItemResponse)
async def create_agent_item(item: ItemCreate):
    """Create an agent supply item (SIM cards, POS paper, branded materials)."""
    item_id = str(uuid.uuid4())
    sku = item.sku or _generate_agent_sku(item.category)
    now = datetime.utcnow().isoformat()
    response = ItemResponse(
        id=item_id, name=item.name, category=item.category, description=item.description,
        sku=sku, quantity=item.quantity, assigned_quantity=0, available_quantity=item.quantity,
        unit=item.unit, unit_cost=item.unit_cost, currency=item.currency,
        warehouse_id=item.warehouse_id, reorder_level=item.reorder_level,
        status=ItemStatus.AVAILABLE if item.quantity > 0 else ItemStatus.DEPLETED,
        metadata=item.metadata, created_at=now, updated_at=now,
    )
    _items[item_id] = response
    if response.available_quantity <= response.reorder_level:
        import asyncio
        asyncio.create_task(_check_low_stock_webhook(response))
    return response


@router.get("/agent-items", response_model=List[ItemResponse])
async def list_agent_items(
    category: Optional[ItemCategory] = None,
    status: Optional[ItemStatus] = None,
    warehouse_id: Optional[str] = None,
    low_stock: bool = False,
    skip: int = 0,
    limit: int = 100,
):
    """List all agent supply items."""
    items = list(_items.values())
    if category:
        items = [i for i in items if i.category == category]
    if status:
        items = [i for i in items if i.status == status]
    if warehouse_id:
        items = [i for i in items if i.warehouse_id == warehouse_id]
    if low_stock:
        items = [i for i in items if i.available_quantity <= i.reorder_level]
    return items[skip:skip + limit]


@router.get("/agent-items/{item_id}", response_model=ItemResponse)
async def get_agent_item(item_id: str):
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="Item not found")
    return _items[item_id]


@router.put("/agent-items/{item_id}", response_model=ItemResponse)
async def update_agent_item(item_id: str, item: ItemCreate):
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="Item not found")
    existing = _items[item_id]
    existing.name = item.name
    existing.category = item.category
    existing.description = item.description
    existing.quantity = item.quantity
    existing.available_quantity = item.quantity - existing.assigned_quantity
    existing.unit = item.unit
    existing.unit_cost = item.unit_cost
    existing.warehouse_id = item.warehouse_id
    existing.reorder_level = item.reorder_level
    existing.metadata = item.metadata
    existing.updated_at = datetime.utcnow().isoformat()
    _update_item_status(existing)
    return existing


@router.delete("/agent-items/{item_id}")
async def delete_agent_item(item_id: str):
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = _items[item_id]
    if item.assigned_quantity > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete item with {item.assigned_quantity} units assigned")
    del _items[item_id]
    return {"status": "deleted", "item_id": item_id}


@router.post("/agent-items/{item_id}/restock")
async def restock_agent_item(item_id: str, quantity: int = Query(..., gt=0)):
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = _items[item_id]
    item.quantity += quantity
    item.available_quantity += quantity
    item.updated_at = datetime.utcnow().isoformat()
    _update_item_status(item)
    return {"item_id": item_id, "new_quantity": item.quantity, "available": item.available_quantity}


@router.post("/assign-agent", response_model=AgentAssignmentResponse)
async def assign_to_agent(request: AgentAssignment):
    if request.item_id not in _items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = _items[request.item_id]
    if item.available_quantity < request.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock: {item.available_quantity} available")
    assignment_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item.assigned_quantity += request.quantity
    item.available_quantity -= request.quantity
    item.updated_at = now
    _update_item_status(item)
    import asyncio
    asyncio.create_task(_check_low_stock_webhook(item, request.agent_id))
    _agent_inventory.setdefault(request.agent_id, {})
    _agent_inventory[request.agent_id][request.item_id] = (
        _agent_inventory[request.agent_id].get(request.item_id, 0) + request.quantity
    )
    assignment = AgentAssignmentResponse(
        assignment_id=assignment_id, item_id=request.item_id, item_name=item.name,
        agent_id=request.agent_id, quantity=request.quantity, status="assigned",
        assigned_at=now, notes=request.notes,
    )
    _assignments[assignment_id] = assignment
    return assignment


@router.post("/return-from-agent")
async def return_from_agent(
    assignment_id: str,
    quantity: Optional[int] = None,
    condition: str = Query(default="good"),
):
    if assignment_id not in _assignments:
        raise HTTPException(status_code=404, detail="Assignment not found")
    assignment = _assignments[assignment_id]
    return_qty = quantity or assignment.quantity
    if return_qty > assignment.quantity:
        raise HTTPException(status_code=400, detail="Return quantity exceeds assigned quantity")
    item = _items.get(assignment.item_id)
    if item:
        item.assigned_quantity -= return_qty
        if condition == "good":
            item.available_quantity += return_qty
        else:
            item.quantity -= return_qty
        item.updated_at = datetime.utcnow().isoformat()
        _update_item_status(item)
    agent_inv = _agent_inventory.get(assignment.agent_id, {})
    agent_inv[assignment.item_id] = max(0, agent_inv.get(assignment.item_id, 0) - return_qty)
    assignment.quantity -= return_qty
    if assignment.quantity <= 0:
        assignment.status = "returned"
        assignment.returned_at = datetime.utcnow().isoformat()
    return {"assignment_id": assignment_id, "returned_quantity": return_qty, "condition": condition}


@router.post("/transfer", response_model=AgentAssignmentResponse)
async def transfer_between_agents(request: TransferRequest):
    from_inv = _agent_inventory.get(request.from_agent_id, {})
    current_qty = from_inv.get(request.item_id, 0)
    if current_qty < request.quantity:
        raise HTTPException(status_code=400, detail=f"Agent only has {current_qty} units")
    from_inv[request.item_id] = current_qty - request.quantity
    _agent_inventory.setdefault(request.to_agent_id, {})
    _agent_inventory[request.to_agent_id][request.item_id] = (
        _agent_inventory[request.to_agent_id].get(request.item_id, 0) + request.quantity
    )
    assignment_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = _items.get(request.item_id)
    assignment = AgentAssignmentResponse(
        assignment_id=assignment_id, item_id=request.item_id,
        item_name=item.name if item else "unknown", agent_id=request.to_agent_id,
        quantity=request.quantity, status="transferred", assigned_at=now,
        notes=f"Transferred from {request.from_agent_id}. {request.reason or ''}".strip(),
    )
    _assignments[assignment_id] = assignment
    return assignment


@router.get("/agent/{agent_id}")
async def get_agent_inventory(agent_id: str):
    agent_inv = _agent_inventory.get(agent_id, {})
    items = [
        {"item_id": iid, "item_name": _items[iid].name if iid in _items else "unknown",
         "category": _items[iid].category.value if iid in _items else "unknown", "quantity": qty}
        for iid, qty in agent_inv.items() if qty > 0
    ]
    return {"agent_id": agent_id, "total_items": len(items), "inventory": items}


@router.get("/agent/{agent_id}/assignments")
async def get_agent_assignments(agent_id: str, status: Optional[str] = None):
    assignments = [a for a in _assignments.values() if a.agent_id == agent_id]
    if status:
        assignments = [a for a in assignments if a.status == status]
    return {"agent_id": agent_id, "total": len(assignments), "assignments": [a.dict() for a in assignments]}


@router.get("/stats")
async def get_statistics():
    total_value = sum((i.unit_cost or 0) * i.quantity for i in _items.values())
    by_category: Dict[str, Any] = {}
    for item in _items.values():
        cat = item.category.value
        by_category.setdefault(cat, {"count": 0, "total_qty": 0, "assigned": 0})
        by_category[cat]["count"] += 1
        by_category[cat]["total_qty"] += item.quantity
        by_category[cat]["assigned"] += item.assigned_quantity
    return {
        "total_items": len(_items),
        "total_quantity": sum(i.quantity for i in _items.values()),
        "total_assigned": sum(i.assigned_quantity for i in _items.values()),
        "total_available": sum(i.available_quantity for i in _items.values()),
        "low_stock_items": sum(1 for i in _items.values() if i.available_quantity <= i.reorder_level),
        "depleted_items": sum(1 for i in _items.values() if i.quantity <= 0),
        "by_category": by_category,
        "total_inventory_value": round(total_value, 2),
    }


@router.get("/low-stock-alerts")
async def get_low_stock_alerts():
    alerts = [
        {"item_id": i.id, "name": i.name, "sku": i.sku, "available": i.available_quantity,
         "reorder_level": i.reorder_level, "severity": "critical" if i.available_quantity == 0 else "warning"}
        for i in _items.values() if i.available_quantity <= i.reorder_level
    ]
    return {"total_alerts": len(alerts), "alerts": alerts}


@router.get("/webhook-log")
async def get_webhook_log(limit: int = Query(default=50, le=500)):
    return {"total": len(_webhook_log), "webhook_url_configured": bool(WEBHOOK_URL), "alerts": _webhook_log[-limit:]}


# ─────────────────────────────────────────────
# SECTION 2: MERCHANT PRODUCT INVENTORY (new — full product management)
# ─────────────────────────────────────────────

def _get_db():
    """Lazy import to avoid circular dependency."""
    try:
        from .config import get_db
        return get_db
    except Exception:
        return None


def _get_svc(db=None):
    try:
        from .service import InventoryManagementService
        from .config import SessionLocal
        if db is None:
            db = SessionLocal()
        return InventoryManagementService(db)
    except Exception as e:
        logger.warning(f"Could not initialize InventoryManagementService: {e}")
        return None


@router.post("/products")
async def create_product(payload: Dict[str, Any]):
    """Create a new merchant product in the inventory."""
    try:
        from .service import InventoryManagementService, ProductCreate
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        req = ProductCreate(**payload)
        product = svc.create_product(req)
        db.close()
        return {
            "id": product.id, "sku": product.sku, "name": product.name,
            "selling_price_ngn": str(product.selling_price_ngn),
            "shareable_url": product.shareable_url, "status": product.status.value,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/from-photo")
async def create_product_from_photo(payload: Dict[str, Any]):
    """
    Create a product by taking a photo — AI auto-generates name, description,
    category, tags, and suggested price. Returns shareable link immediately.
    """
    try:
        from .service import InventoryManagementService, ProductFromPhotoRequest
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        req = ProductFromPhotoRequest(**payload)
        result = svc.create_product_from_photo(req)
        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/from-photo/upload")
async def create_product_from_photo_upload(
    merchant_id: str = Query(...),
    selling_price_ngn: Optional[float] = Query(None),
    file: UploadFile = File(...),
):
    """Upload a product photo directly and auto-generate product details."""
    try:
        from .service import InventoryManagementService, ProductFromPhotoRequest
        from .config import SessionLocal
        contents = await file.read()
        image_base64 = base64.b64encode(contents).decode("utf-8")
        db = SessionLocal()
        svc = InventoryManagementService(db)
        req = ProductFromPhotoRequest(
            merchant_id=merchant_id,
            image_base64=image_base64,
            selling_price_ngn=Decimal(str(selling_price_ngn)) if selling_price_ngn else None,
        )
        result = svc.create_product_from_photo(req)
        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{merchant_id}/list")
async def get_merchant_products(
    merchant_id: str,
    category_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all products for a merchant."""
    try:
        from .service import Product, ProductStatus
        from .config import SessionLocal
        db = SessionLocal()
        q = db.query(Product).filter(Product.merchant_id == merchant_id)
        if category_id:
            q = q.filter(Product.category_id == category_id)
        if status:
            q = q.filter(Product.status == ProductStatus(status))
        products = q.offset(offset).limit(limit).all()
        db.close()
        return [
            {"id": p.id, "sku": p.sku, "name": p.name,
             "selling_price_ngn": str(p.selling_price_ngn), "status": p.status.value,
             "shareable_url": p.shareable_url, "primary_image_url": p.primary_image_url,
             "ai_detected_category": p.ai_detected_category}
            for p in products
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/by-slug/{slug}")
async def get_product_by_slug(slug: str):
    """Get a product by its shareable slug (for public storefront)."""
    try:
        from .service import Product
        from .config import SessionLocal
        db = SessionLocal()
        product = db.query(Product).filter(Product.shareable_slug == slug).first()
        db.close()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {
            "id": product.id, "name": product.name, "description": product.description,
            "short_description": product.short_description, "brand": product.brand,
            "selling_price_ngn": str(product.selling_price_ngn),
            "primary_image_url": product.primary_image_url,
            "tags": product.ai_generated_tags, "category": product.ai_detected_category,
            "shareable_url": product.shareable_url,
            "meta_title": product.meta_title, "meta_description": product.meta_description,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stock/adjust")
async def adjust_stock(payload: Dict[str, Any]):
    """Perform a stock adjustment."""
    try:
        from .service import InventoryManagementService, StockAdjustmentRequest
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        req = StockAdjustmentRequest(**payload)
        stock = svc.adjust_stock(req)
        db.close()
        return {"product_id": stock.product_id, "quantity_on_hand": stock.quantity_on_hand, "quantity_available": stock.quantity_available}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stock/transfer-location")
async def transfer_stock_location(payload: Dict[str, Any]):
    """Transfer stock between locations."""
    try:
        from .service import InventoryManagementService, StockTransferRequest
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        req = StockTransferRequest(**payload)
        result = svc.transfer_stock(req)
        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{merchant_id}/levels")
async def get_stock_levels(
    merchant_id: str,
    location_id: Optional[str] = Query(None),
    low_stock_only: bool = Query(False),
):
    """Get current stock levels for all merchant products."""
    try:
        from .service import InventoryManagementService
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        result = svc.get_stock_levels(merchant_id, location_id, low_stock_only)
        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{merchant_id}/expiring")
async def get_expiring_stock(merchant_id: str, days_ahead: int = Query(30, ge=1, le=365)):
    """Get products expiring within the specified number of days."""
    try:
        from .service import InventoryManagementService
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        result = svc.get_expiring_stock(merchant_id, days_ahead)
        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/valuation/{merchant_id}")
async def get_inventory_valuation(merchant_id: str):
    """Get comprehensive inventory valuation report."""
    try:
        from .service import InventoryManagementService
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        result = svc.get_inventory_valuation(merchant_id)
        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase-orders")
async def create_purchase_order(payload: Dict[str, Any]):
    """Create a purchase order for restocking."""
    try:
        from .service import InventoryManagementService, PurchaseOrderCreate
        from .config import SessionLocal
        from datetime import date
        db = SessionLocal()
        svc = InventoryManagementService(db)
        if isinstance(payload.get("order_date"), str):
            payload["order_date"] = date.fromisoformat(payload["order_date"])
        if payload.get("expected_delivery_date") and isinstance(payload["expected_delivery_date"], str):
            payload["expected_delivery_date"] = date.fromisoformat(payload["expected_delivery_date"])
        req = PurchaseOrderCreate(**payload)
        po = svc.create_purchase_order(req)
        db.close()
        return {"id": po.id, "po_number": po.po_number, "status": po.status.value, "total_ngn": str(po.total_ngn)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase-orders/{po_id}/receive")
async def receive_purchase_order(po_id: str, received_items: List[Dict[str, Any]]):
    """Receive goods against a purchase order and update stock levels."""
    try:
        from .service import InventoryManagementService
        from .config import SessionLocal
        db = SessionLocal()
        svc = InventoryManagementService(db)
        po = svc.receive_purchase_order(po_id, received_items)
        db.close()
        return {"id": po.id, "po_number": po.po_number, "status": po.status.value}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_data(data: Dict[str, Any]):
    """Bulk processing endpoint for agent inventory operations."""
    action = data.get("action")
    if action == "bulk_assign":
        results = []
        for assignment in data.get("assignments", []):
            req = AgentAssignment(**assignment)
            result = await assign_to_agent(req)
            results.append(result.dict())
        return {"processed": len(results), "results": results}
    elif action == "bulk_restock":
        results = []
        for restock in data.get("items", []):
            result = await restock_agent_item(restock["item_id"], restock["quantity"])
            results.append(result)
        return {"processed": len(results), "results": results}
    return {"status": "unknown_action", "action": action}
